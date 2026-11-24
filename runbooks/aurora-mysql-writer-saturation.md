# Runbook: Aurora MySQL Writer CPU and Connection Saturation

> [!IMPORTANT]
> **Severity: P1/P2.** Latency spikes and timeouts cascade across API services because writes and read-after-write queries stall on the single writer instance.
> **Target triage time: 5 to 10 minutes.**
> **Prerequisites:** AWS Console/CLI access to RDS Performance Insights and CloudWatch, MySQL client read/admin access (`PROCESS` and `CONNECTION_ADMIN` or master role).

The Aurora MySQL writer hits >90% CPU or exhausts `max_connections` (often alongside flat or low reader load). Dropping replicas or restarting app pods blindly makes connection storms worse because reconnection loops immediately re-saturate the writer.

---

## Pre-Triage Checklist

- [ ] Record incident start time and active deployment window.
- [ ] Confirm writer vs reader instance IDs before running any session kills.
- [ ] Open AWS Performance Insights on the **writer** instance (`Top SQL` and `Top Waits`).
- [ ] Check whether connection count or active threads jumped alongside a batch job, migration, or deploy.

**Check live threads and wait states on the writer:**

```sql
SHOW GLOBAL STATUS WHERE Variable_name IN (
  'Threads_connected',
  'Threads_running',
  'Max_used_connections',
  'Aborted_connects'
);

SELECT id, user, host, db, command, time, state, LEFT(info, 120) AS query_prefix
FROM information_schema.processlist
WHERE command <> 'Sleep'
ORDER BY time DESC
LIMIT 25;
```

**Aggregate noisy clients by user/host/command:**

```sql
SELECT user, SUBSTRING_INDEX(host, ':', 1) AS client_host, command,
       COUNT(*) AS conn_count, MAX(time) AS max_sec
FROM information_schema.processlist
GROUP BY user, client_host, command
ORDER BY conn_count DESC;
```

---

## Common Root Causes

- **Unbatched write bursts:** Workers executing row-by-row `INSERT` or `UPDATE` statements with `autocommit=1`, inflating InnoDB commit/fsync overhead and `synch/mutex/innodb` or `io/table/sql/handler` waits while CPU hits 90%+.
- **Uncapped application connection pools:** Multiple microservices scaling pods independently without shared bounds, saturating `max_connections` even at moderate QPS.
- **Runaway analytical `SELECT` queries hitting the writer:** Reporting or ad-hoc queries scanning tables on the writer instead of an Aurora reader endpoint, holding metadata locks or buffer pool pages.

---

## Step 1: Immediate Mitigation (5 to 10 minutes)

Choose the mitigation matching the dominant signature in `SHOW FULL PROCESSLIST` and Performance Insights:

1. **If unbatched background writers are saturating CPU:**
   - Scale down or pause the background consumer/batch worker deployment rather than restarting web APIs.
   - Verify writer CPU drops and `Threads_running` stabilizes below vCPU count x 2.
2. **If analytical `SELECT` queries are hogging CPU or holding metadata locks:**
   - Terminate only long-running read queries after confirming query ID and digest:
   ```sql
   -- Verify exact query in processlist first; never kill DDL/ALTER/migration transactions blindly.
   KILL QUERY <process_id>;
   ```
3. **If `Threads_connected` is near `max_connections` from idle pool bloat:**
   - Inspect per-host connection counts above; scale back noisy non-critical workers or temporarily tighten idle pool timeouts on services keeping idle sessions open.
   - Do **not** drop connections from stateful migration jobs without checking open transaction age in `information_schema.innodb_trx`:
   ```sql
   SELECT trx_id, trx_state, trx_started, trx_mysql_thread_id, trx_rows_modified
   FROM information_schema.innodb_trx
   ORDER BY trx_started ASC;
   ```

> [!WARNING]
> Avoid failing over the Aurora cluster just to "clear load" during an unbatched write storm. The new writer will immediately inherit the same write traffic plus cold buffer pool penalty and trigger a brief write outage during promotion.

---

## Step 2: Verification of Recovery

Confirm all four signals return to baseline for at least 5 consecutive minutes:

- [ ] `Threads_running` stays low and stable without growing queue backlogs.
- [ ] Writer `CPUUtilization` drops below alert threshold (typically <70%).
- [ ] `innodb_trx` shows no stalled transactions blocking DDL or row updates.
- [ ] Upstream service 5xx error rates and P95 write latency return to normal.

---

## Step 3: Durable Fix (Post-Incident Actions)

- Batch background `INSERT`/`UPDATE` workloads (e.g., 100 to 1,000 rows per transaction or staged upsert) instead of single-row `autocommit` loops.
- Enforce per-service connection pool upper bounds (`pool_size` + `max_overflow`) sized against total `max_connections` across max pod count.
- Place high-churn microservices behind **AWS RDS Proxy** to multiplex short-lived sessions and isolate database failovers.
- Route heavy read/reporting queries explicitly to the Aurora **reader endpoint**.
- Codify composite saturation alerts (correlating writer `CPUUtilization` with `DatabaseConnections` / `Threads_running`) in infrastructure as code so alerts trigger before client timeouts cascade.
