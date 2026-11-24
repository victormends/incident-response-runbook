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

## Step 1: Visualize the lock wait chain

This query shows active blocking pairs (who is blocking whom, and what the blocking session is doing), adapted from the **PostgreSQL Wiki (`Lock_Monitoring`)** guide.

Using PostgreSQL 9.6+ `pg_blocking_pids(blocked.pid)` captures **relation, tuple, advisory, and `transactionid` locks** in a single query without missing non-transaction locks:

```sql
-- Adapted from PostgreSQL Wiki (Lock_Monitoring) using pg_blocking_pids() (PostgreSQL 9.6+).
-- Captures relation, tuple, advisory, and transactionid lock waits.
-- blocker_pid: a session holding a conflicting lock
-- blocked_pid: the session waiting for it
-- blocker_last_query: what the blocking session last ran (may be empty or stale if idle-in-transaction)
-- Copy-paste safe (no modifications needed for standard PostgreSQL 9.6+).
SELECT
    blocker.pid AS blocker_pid,
    blocker.usename AS blocker_user,
    blocker.state AS blocker_state,
    blocked.pid AS blocked_pid,
    blocked.usename AS blocked_user,
    now() - blocked.query_start AS wait_duration,
    left(blocker.query, 120) AS blocker_last_query,
    left(blocked.query, 120) AS blocked_query
FROM pg_stat_activity blocked
CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS blocker_pid
JOIN pg_stat_activity blocker ON blocker.pid = blocker_pid
WHERE blocked.wait_event_type = 'Lock'
ORDER BY wait_duration DESC;
```

> [!NOTE]
> For legacy PostgreSQL versions older than 9.6 (before `pg_blocking_pids()` existed), see the **PostgreSQL Wiki (`Lock_Monitoring`)** `pg_locks` self-join query, which matches across `locktype`, `database`, `relation`, `page`, `tuple`, `virtualxid`, `transactionid`, `classid`, `objid`, and `objsubid` rather than `transactionid` alone.

**Reading the output:**

- `blocker_state = 'idle in transaction'`: the blocking session opened a transaction, ran a query, and stopped. It is not actively doing anything. This is almost always a leaked transaction from an application that crashed or lost its connection. Safe to terminate.
- `blocker_state = 'active'`: the blocking session is in the middle of a long-running query. Do not terminate without understanding the operation.
- Multiple `blocked_pid` rows with the same `blocker_pid`: a single session is blocking many others. Terminating the blocker will unblock all of them simultaneously.

---

## Step 2: Deadlock vs Long-Running Lock Waits

It's critical to differentiate between a **deadlock** and a **long-running lock wait** (lock contention).

*   **Lock Contention (Queueing):** Session A holds a lock on Row 1. Session B wants a lock on Row 1, so it queues and waits until Session A finishes. This can go on for hours. You can diagnose this live using the query from Step 1 above.
*   **Deadlock (Circular Dependency):** Session A holds a lock on Row 1 and waits for Row 2. Session B holds a lock on Row 2 and waits for Row 1. Neither can move. PostgreSQL detects this automatically, kills one session (the "victim") instantly, and lets the other proceed.

**You cannot catch a deadlock live with `pg_stat_activity` because PostgreSQL resolves it in milliseconds.** If you suspect a deadlock, you must look at the logs:

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

Deadlocks are almost always an application-level issue: two code paths acquire locks on the same tables in different orders. The fix is to standardize the lock acquisition order in the application code, not to change PostgreSQL configuration or terminate sessions.

```sql
-- Post-mortem: After a deadlock occurs, check pg_stat_activity for the surviving session 
-- (the one that wasn't killed as the victim) to understand what operation succeeded.
SELECT pid, usename, state, left(query, 150) AS query
FROM pg_stat_activity
WHERE pid IN (12345, 11111);  -- replace with actual PIDs from the log
```

---

## Step 3: Emergency unlock

> [!WARNING]
> Before terminating any session, confirm that it is not in the middle of a fiscal write operation. A session inserting NF-e records, processing payroll, or updating tax tables that is terminated mid-transaction will have its work rolled back (the data will be safe, but the client's operation will need to be retried). Always ask: "Is this session doing something the client needs to re-run if we terminate it?"

**Soft cancel (interrupts the current query, does not close the connection):**

```sql
-- Sends SIGINT to the backend. The session continues to exist but the current
-- query is cancelled. Use this first (it is less disruptive than termination).
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
