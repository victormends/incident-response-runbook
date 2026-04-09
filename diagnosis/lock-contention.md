# Lock Contention

**Symptom:** Queries hang indefinitely, application reports timeouts with no resource exhaustion, `lock_timeout` errors appear in logs, or `deadlock detected` entries appear in the PostgreSQL log.

**Confirmation query:**

```sql
-- Returns connections that are currently waiting for a lock.
-- Any rows here mean lock contention is active right now.
SELECT pid, usename, application_name, state, wait_event_type, wait_event,
       now() - query_start AS wait_duration,
       left(query, 100) AS waiting_query
FROM pg_stat_activity
WHERE wait_event_type = 'Lock'
ORDER BY wait_duration DESC;
```

If this returns rows, proceed with the steps below.

---

## Step 1 — Visualize the lock wait chain

This query shows the full blocking chain: who is blocking whom, and what the blocking session is doing.

```sql
-- Returns the lock wait chain. Each row shows a blocked session and its blocker.
-- blocker_pid: the session holding the lock
-- blocked_pid: the session waiting for it
-- blocker_query: what the blocking session last ran (may be empty if it's idle-in-transaction)
-- Copy-paste safe — no modifications needed for standard PostgreSQL.
WITH RECURSIVE lock_chain AS (
    SELECT
        blocked.pid AS blocked_pid,
        blocked.usename AS blocked_user,
        blocked.query AS blocked_query,
        blocker.pid AS blocker_pid,
        blocker.usename AS blocker_user,
        blocker.query AS blocker_query,
        blocker.state AS blocker_state,
        now() - blocked.query_start AS wait_duration
    FROM pg_stat_activity blocked
    JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
    JOIN pg_locks blocker_locks ON blocked_locks.transactionid = blocker_locks.transactionid
                                AND blocker_locks.granted = true
                                AND blocked_locks.granted = false
    JOIN pg_stat_activity blocker ON blocker_locks.pid = blocker.pid
    WHERE NOT blocked.pid = blocker.pid
)
SELECT blocker_pid, blocker_user, blocker_state,
       blocked_pid, blocked_user,
       wait_duration,
       left(blocker_query, 120) AS blocker_last_query,
       left(blocked_query, 120) AS blocked_query
FROM lock_chain
ORDER BY wait_duration DESC;
```

**Reading the output:**

- `blocker_state = 'idle in transaction'` — the blocking session opened a transaction, ran a query, and stopped. It is not actively doing anything. This is almost always a leaked transaction from an application that crashed or lost its connection. Safe to terminate.
- `blocker_state = 'active'` — the blocking session is in the middle of a long-running query. Do not terminate without understanding the operation.
- Multiple `blocked_pid` rows with the same `blocker_pid` — a single session is blocking many others. Terminating the blocker will unblock all of them simultaneously.

---

## Step 2 — Deadlock diagnosis

A deadlock means two sessions are each waiting for a lock held by the other. PostgreSQL detects this automatically and terminates one session (the victim). You will see this in the log:

```
ERROR:  deadlock detected
DETAIL: Process 12345 waits for ShareLock on transaction 67890; blocked by process 11111.
        Process 11111 waits for ShareLock on transaction 12345; blocked by process 12345.
HINT:  See server log for query details.
```

**What matters in the deadlock log entry:**

- The two PIDs involved
- The query each was running at the time (logged immediately below the deadlock line)
- The tables involved

Deadlocks are almost always an application-level issue: two code paths acquire locks on the same tables in different orders. The fix is to standardize the lock acquisition order in the application, not to change PostgreSQL configuration.

```sql
-- After a deadlock, check pg_stat_activity for the surviving sessions
-- to understand what operation was being performed.
SELECT pid, usename, state, left(query, 150) AS query
FROM pg_stat_activity
WHERE pid IN (12345, 11111);  -- replace with actual PIDs from the log
```

---

## Step 3 — Emergency unlock

> [!WARNING]
> Before terminating any session, confirm that it is not in the middle of a fiscal write operation. A session inserting NF-e records, processing payroll, or updating tax tables that is terminated mid-transaction will have its work rolled back — the data will be safe, but the client's operation will need to be retried. Always ask: "Is this session doing something the client needs to re-run if we terminate it?"

**Soft cancel (interrupts the current query, does not close the connection):**

```sql
-- Sends SIGINT to the backend. The session continues to exist but the current
-- query is cancelled. Use this first — it is less disruptive than termination.
SELECT pg_cancel_backend(pid);  -- replace pid with the blocker's PID
```

**Hard termination (closes the connection entirely):**

```sql
-- Sends SIGTERM to the backend. The session is disconnected immediately.
-- Any open transaction is rolled back. Use when cancel does not work within 30 seconds.
SELECT pg_terminate_backend(pid);  -- replace pid with the blocker's PID
```

After termination, re-run the lock chain query from Step 1 to confirm the blocked sessions have resumed.

---

## Preventive measures

**Set a lock timeout to prevent indefinite waits:**

```sql
-- Prevents any session from waiting more than 30 seconds for a lock.
-- Sessions that exceed this are cancelled with a lock_timeout error.
-- Add to postgresql.conf for system-wide enforcement, or set per-role.
ALTER SYSTEM SET lock_timeout = '30s';
SELECT pg_reload_conf();
```

**Set idle-in-transaction timeout to prevent leaked transactions from holding locks:**

```sql
-- Automatically terminates sessions that stay idle-in-transaction for more than 5 minutes.
-- This is the single most effective preventive measure against lock accumulation.
ALTER SYSTEM SET idle_in_transaction_session_timeout = '5min';
SELECT pg_reload_conf();
```

**Application-level retry logic:** clients that receive a `lock_timeout` error should retry the operation with exponential backoff rather than failing immediately. Most ORMs support this natively.

**Index strategy:** missing indexes on join columns or filter columns in high-concurrency tables increase the duration of row-level locks, because queries take longer to complete. A query that holds a row lock for 10 seconds instead of 100 milliseconds causes 100x more contention.

---

## Cross-Reference

- Severity classification: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
- If the blocking session cannot be identified or terminated: [`escalation/protocol.md`](../escalation/protocol.md)
- Return to triage: [`triage/flowchart.md`](../triage/flowchart.md)
