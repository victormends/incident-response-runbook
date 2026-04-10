# Post-Mortem: Connection Pool Exhaustion — ORM Leak on Error Path

*Second worked example. The WAL incident post-mortem ([`example-pg-wal-incident.md`](./example-pg-wal-incident.md)) covers infrastructure failure. This one covers application-layer failure — a connection pool leak triggered by an unhandled exception path. Different class of problem, same framework.*

---

## Incident Metadata

| Field | Value |
|---|---|
| **Title** | Connection pool exhaustion — idle-in-transaction leak from unhandled ORM exception |
| **Severity** | P2 → escalated to P1 at 11:14 |
| **Incident opened** | 2025-01-22 10:53 BRT |
| **Incident resolved** | 2025-01-22 11:47 BRT |
| **Total duration** | 0:54 |
| **Affected systems** | PostgreSQL 15 primary — production ERP cluster, Client B |
| **Affected clients** | Client B (report generation unavailable; core ERP operational via separate connection pool) |
| **Primary responder** | Victor M. |
| **Secondary responders** | None |

---

## Executive Summary

At 10:53, Client B reported that all report generation in their ERP system was timing out. The core ERP functions (invoice entry, fiscal transmission) were operational. Investigation confirmed that 48 of 50 available PostgreSQL connections were held by idle-in-transaction sessions from the report generation service. The root cause was an unhandled exception in the reporting ORM that caused transactions to be opened but never committed or rolled back, leaving the connections checked out from the pool indefinitely. Service was restored at 11:47 by terminating the idle-in-transaction sessions and applying an `idle_in_transaction_session_timeout` setting. The ORM bug was identified and escalated to the client's development team for a code-level fix.

---

## Incident Timeline

| Time | Event | Source | Action Taken |
|---|---|---|---|
| 10:53 | Client B reports "report module completely frozen — all reports timing out" | Phone call | Opened as P2. De-escalation script delivered. Callback in 15 minutes. |
| 10:55 | Confirmed database reachable: `psql -c "SELECT 1"` succeeds | Direct check | Began connection audit |
| 10:56 | Connection count query: 48/50 connections in use (96%). `pct_used = 96%` | `pg_stat_activity` | Connection exhaustion confirmed. Began Step 1 of checklist. |
| 10:58 | Breakdown by state: 46 connections in `idle in transaction`, all from IP `10.0.0.82`, application_name `report_generator` | `pg_stat_activity` GROUP BY | Identified leak source as report service. |
| 11:01 | Oldest idle-in-transaction session: open for 47 minutes. `xact_start` = 10:14 | `pg_stat_activity` | Confirmed leak is not from current incident — started before first report. |
| 11:03 | Called client back: confirmed cause (connection leak from report service), shared plan (terminate sessions, apply timeout), requested permission to terminate | Phone call to Client B | Client confirmed reports had been failing since approximately 10:15. |
| 11:05 | Reclassified to P1: client's business hours end at 12:00, all reports needed before then. Notified team lead. | Internal assessment | Escalation logged. |
| 11:08 | Terminated 46 idle-in-transaction sessions using `pg_terminate_backend()` | psql | Connections freed. `pct_used` dropped to 4%. |
| 11:09 | Report module restarted by client's IT team | Client action | New connections established normally. First report completed in 23 seconds. |
| 11:14 | Applied `idle_in_transaction_session_timeout = '5min'` as immediate safeguard | `ALTER SYSTEM` + `pg_reload_conf()` | Prevents recurrence until code fix is deployed. |
| 11:18 | Confirmed 4 reports completed successfully in the 9 minutes since restart | Client callback | Client operational. |
| 11:22 | Identified last query before each leaked connection: `SELECT * FROM relatorio_fiscal WHERE periodo = $1` — consistently preceded by unhandled exception in aggregation step | `pg_stat_activity` query history | Root query identified. Escalated to client dev team with evidence. |
| 11:47 | Client confirmed all pending reports generated. Incident closed. | Phone call | Post-mortem opened. |

---

## Technical Root Cause

**Proximate cause:** 46 PostgreSQL connections were held in `idle in transaction` state, leaving only 4 connections available for all other operations. The report generation service was unable to acquire new connections.

**Contributing cause:** The report generation service's ORM (SQLAlchemy) opened a transaction before executing each report query. An unhandled exception in the post-query aggregation step caused the request handler to exit without committing or rolling back the transaction. The ORM returned the connection to the pool without closing the transaction — a known SQLAlchemy behavior when session cleanup is not handled in the `finally` block of the request lifecycle. Each failed report left one connection permanently stuck in `idle in transaction`.

**Systemic cause:** No `idle_in_transaction_session_timeout` was configured. Without this setting, PostgreSQL allows a session to remain idle-in-transaction indefinitely. The connection pool had no mechanism to detect or reclaim these sessions. This class of leak had no monitoring alert — connection count was tracked but not connection state distribution.

---

## 5-Whys Analysis

1. **Why were clients unable to connect to the report module?** All available PostgreSQL connections were occupied.
2. **Why were all connections occupied?** 46 connections were stuck in `idle in transaction` state for up to 47 minutes each.
3. **Why were they stuck idle-in-transaction?** The report service ORM opened transactions that were never committed or rolled back due to unhandled exceptions in the aggregation step.
4. **Why did unhandled exceptions leave transactions open?** The SQLAlchemy session was not managed with a `try/finally` pattern in the request handler — exceptions bypassed the session cleanup code.
5. **Why was there no cleanup pattern?** The report module was written without a global exception handler or context manager for session lifecycle management. This is a code review gap — the pattern was not enforced as a standard.

---

## Communication Review

| Field | Value |
|---|---|
| **First client contact** | 10:53 — phone call. Script: *"Client B, I have your incident open. I can confirm your report module is experiencing connectivity issues. I don't have a diagnosis yet. I'll call you back in 15 minutes with confirmed findings."* |
| **First client update** | 11:03 — phone call. *"I've confirmed the cause: the report service has accumulated 46 open database transactions that were never closed, filling up the connection pool. I can terminate those sessions now, which will immediately restore report access. This is safe — no data is at risk. Can I proceed?"* |
| **Update cadence followed** | Updates at 10:53, 11:03, 11:18, 11:47. P1 cadence (every 30 min) maintained from reclassification at 11:05. |
| **Escalation history** | Team lead notified at 11:05 on P1 reclassification. No technical escalation required. |
| **Client sentiment at resolution** | Client satisfied with speed of resolution. Expressed concern about recurrence. Accepted the `idle_in_transaction_session_timeout` safeguard and confirmed their dev team would address the ORM bug. |

**Communication quality assessment:**

- De-escalation script followed on first contact: **Yes**
- Update cadence maintained: **Yes**
- Premature diagnosis or reassurance before confirmation: **No** — first update at 11:03 was delivered after connection state analysis was complete and cause confirmed
- Notable: asking explicit permission before terminating sessions ("Can I proceed?") — this was the correct move. The client confirmed the sessions were safe to terminate; if they had said no, the investigation would have continued differently.

---

## Corrective Actions

| Action | Owner | Due Date | Status |
|---|---|---|---|
| Terminate 46 idle-in-transaction sessions to restore connections | Victor M. | 2025-01-22 | Done |
| Apply `idle_in_transaction_session_timeout = '5min'` on production cluster | Victor M. | 2025-01-22 | Done |
| Provide client dev team with the specific query and stack trace identifying the ORM bug | Victor M. | 2025-01-22 | Done |

---

## Preventive Actions

| Action | Owner | Due Date | Status |
|---|---|---|---|
| Add connection state distribution alert: if `idle in transaction` count exceeds 20% of max_connections, trigger warning | Victor M. | 2025-01-29 | Pending |
| Add `idle_in_transaction_session_timeout = '5min'` to standard cluster provisioning checklist | Victor M. | 2025-01-29 | Pending |
| Client dev team: wrap all SQLAlchemy sessions in `try/finally` with explicit rollback on exception | Client dev team | TBD | Pending (client responsibility) |
| Add `idle in transaction` state count to daily health check query | Victor M. | 2025-01-29 | Pending |

---

## Lessons Learned

The technical diagnosis was fast — 5 minutes from first query to confirmed root cause. The delay was almost entirely in communication: confirming permission to terminate sessions, coordinating the service restart with the client's IT team, waiting for reports to complete to confirm resolution.

The reclassification to P1 at 11:05 was correct. A 54-minute incident affecting a client's ability to generate end-of-day reports during business hours is a P1 by impact even if the database itself is technically available. The severity matrix's "fiscal process blocked" escalation trigger applies here.

The `idle_in_transaction_session_timeout` setting deserves to be in every cluster's default configuration. Its absence is the systemic cause. The ORM bug is the contributing cause — but even with the bug, a 5-minute timeout would have capped the blast radius at 5 bad connections rather than 46.

The communication pattern that worked: asking permission before a destructive action (session termination) rather than doing it and informing. This takes 60 seconds and eliminates the scenario where you terminate a session the client was depending on for something you didn't know about.

---

## Cross-Reference

- Diagnosis checklist used: [`diagnosis/connection-exhaustion.md`](../diagnosis/connection-exhaustion.md)
- Communication framework: [`communication/nvc-incident-communication.md`](../communication/nvc-incident-communication.md)
- Severity classification: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
- Post-mortem template: [`template.md`](./template.md)
