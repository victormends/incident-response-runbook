# Connection Exhaustion

**Symptom:** Clients report they cannot connect to the database. Error messages include:

- `FATAL: remaining connection slots are reserved for non-replication superuser connections`
- `FATAL: sorry, too many clients already`
- Application timeout errors with no other apparent cause

**Confirmation query** — run this first:

```sql
-- Returns current connection count vs the configured limit.
-- If current_connections is at or near max_connections, this is your problem.
SELECT count(*) AS current_connections,
       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections,
       round(100.0 * count(*) / (SELECT setting::int FROM pg_settings WHERE name = 'max_connections'), 1) AS pct_used
FROM pg_stat_activity;
```

If `pct_used` is above 90%, proceed with the steps below.

---

## Step 1 — Immediate stabilization

Do this before root cause analysis. The goal is to create enough free slots for diagnostic connections and to stop the bleeding.

**1a. Understand who is holding connections:**

```sql
-- Returns connection count grouped by state and client address.
-- Look for large counts of 'idle' or 'idle in transaction' from a single source.
SELECT state,
       client_addr,
       count(*) AS connections,
       min(state_change) AS oldest_state_change
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
GROUP BY state, client_addr
ORDER BY connections DESC;
```

Expected output on a healthy system: a small number of `active` connections and a few `idle` connections with recent `state_change` timestamps. On an exhausted system, you will typically see dozens or hundreds of `idle` or `idle in transaction` connections from one or two client addresses.

**1b. Identify idle connections that have been sitting for more than 10 minutes:**

```sql
-- Returns connections in 'idle' state unchanged for more than 10 minutes.
-- These are the safest candidates for termination — they are not mid-transaction.
SELECT pid, client_addr, application_name, state, state_change,
       now() - state_change AS idle_duration
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < now() - interval '10 minutes'
  AND pid <> pg_backend_pid()
ORDER BY idle_duration DESC;
```

**1c. Emergency relief — terminate idle connections:**

> [!WARNING]
> This terminates active sessions. Any client that is idle but was about to send a query will receive a disconnection error. Confirm with your team lead before running in production. Never run this without knowing which application owns these connections.

```sql
-- Terminates all connections idle for more than 10 minutes.
-- Returns the count of terminated sessions.
SELECT count(pg_terminate_backend(pid))
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < now() - interval '10 minutes'
  AND pid <> pg_backend_pid();
```

After running this, wait 30 seconds and re-run the confirmation query from the top. If `pct_used` has dropped below 80%, the system has stabilized. Proceed to root cause analysis.

If connections fill back up within 2 minutes, the application is actively creating new connections. This is a connection pool misconfiguration or a leak — proceed to Step 2.

---

## Step 2 — Root cause analysis

**Query 2a: Connections broken down by state and wait event:**

```sql
-- Full breakdown of what every connection is doing right now.
-- 'idle in transaction' with a large wait_event is often the sign of a leaked transaction.
SELECT pid, usename, application_name, client_addr,
       state, wait_event_type, wait_event,
       now() - query_start AS query_duration,
       left(query, 80) AS current_query
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
ORDER BY query_start ASC NULLS LAST;
```

**Query 2b: Connections broken down by application:**

```sql
-- If one application_name dominates, that is the leak source.
SELECT application_name, state, count(*) AS connections
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
GROUP BY application_name, state
ORDER BY connections DESC;
```

**Query 2c: Long-running idle-in-transaction sessions:**

```sql
-- 'idle in transaction' means the application opened a transaction and stopped sending queries.
-- The transaction is still open, holding any locks it acquired.
-- Sessions here longer than 5 minutes are almost always a bug in the application.
SELECT pid, usename, client_addr, application_name,
       now() - xact_start AS transaction_duration,
       left(query, 100) AS last_query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND xact_start < now() - interval '5 minutes'
ORDER BY transaction_duration DESC;
```

---

## Common root causes

**1. Connection pool misconfiguration**

The application's connection pool is configured with more connections than `max_connections` allows. Each application instance opens its maximum pool size on startup.

- How to confirm: the `application_name` column in `pg_stat_activity` shows the same app name across most connections.
- Fix: reduce the pool size in the application config, or increase `max_connections` in `postgresql.conf` (requires restart) and add `pgBouncer` in front.

**2. Application not returning connections to the pool**

The connection pool exists but connections are being checked out and not returned (common in error handling paths that skip the `finally` block).

- How to confirm: connections from the app IP keep accumulating even after idle termination, and `application_name` is consistent.
- Fix: review the application's connection handling in error paths. Add connection timeout (`connect_timeout`) in the connection string.

**3. Idle-in-transaction leak**

Transactions are opened but not committed or rolled back, often due to application crashes or missing transaction management.

- How to confirm: Query 2c above returns sessions.
- Fix (immediate): `SELECT pg_terminate_backend(pid)` for the offending sessions. Fix (permanent): set `idle_in_transaction_session_timeout = '5min'` in `postgresql.conf` — PostgreSQL will automatically close these sessions.

**4. Runaway background job**

A scheduled job is spawning a new database connection for each record it processes instead of reusing a single connection.

- How to confirm: connections spike sharply at a specific time (check `backend_start` timestamps for clustering).
- Fix: refactor the job to reuse a single long-lived connection.

---

## Preventive measures

```sql
-- Check current idle_in_transaction_session_timeout setting.
-- If 0, it is disabled — sessions can stay idle in transaction indefinitely.
SHOW idle_in_transaction_session_timeout;
```

```sql
-- Check current statement_timeout setting.
SHOW statement_timeout;
```

Recommended settings for production (add to `postgresql.conf`, requires reload):
```
idle_in_transaction_session_timeout = '5min'
statement_timeout = '30min'
```

For per-user connection limits:
```sql
-- Limit a specific role to 20 connections maximum.
ALTER ROLE app_user CONNECTION LIMIT 20;
```

Consider `pgBouncer` in transaction pooling mode if the application opens many short-lived connections. Transaction pooling can support hundreds of application threads with a fraction of the actual PostgreSQL connection count.

---

## Cross-Reference

- If stabilization queries do not reduce connection count within 5 minutes: [`escalation/protocol.md`](../escalation/protocol.md)
- For severity classification: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
- Return to triage: [`triage/flowchart.md`](../triage/flowchart.md)
