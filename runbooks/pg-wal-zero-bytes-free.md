# ★ Runbook: pg_wal Zero Bytes Free

> [!IMPORTANT]
> **Severity: P1.** This incident prevents the database from starting or causes it to shut down mid-operation.
> **Estimated recovery time: 20–45 minutes** if this runbook is followed exactly.
> **Prerequisites:** Windows administrative access, PostgreSQL superuser credentials.

The `pg_wal` directory has consumed all available disk space. PostgreSQL cannot write new WAL segments. The database has shut down or refuses to start. This is not a data loss event — it is a disk space event. If you follow this runbook without deviating, recovery is predictable and complete.

The root cause is almost always one of two things:
- **(a) An orphaned replication slot** retaining WAL indefinitely because its subscriber was decommissioned without dropping the slot. This is the most common cause and what this runbook addresses.
- **(b) `archive_command` failing silently** for an extended period, causing WAL to accumulate. If you see `archive_command` errors in the log, this runbook covers the space recovery but the archive failure requires separate investigation.

---

## Pre-Recovery Checklist

Before touching anything:

- [ ] Note the current time — your post-mortem timeline starts now.
- [ ] If the database is still running: connect immediately and run the slot query below. Save the output.
- [ ] Open Windows Event Viewer → Application log → filter source "PostgreSQL" — save the last 20 entries.
- [ ] Confirm `pg_wal` is the problem. Open WizTree as Administrator (free, much faster than Windows Explorer for large directories). Scan the PostgreSQL data directory. If `pg_wal` is the largest subdirectory and disk free space is near zero, proceed.

**If the database is still running, run this immediately:**

```sql
-- Save this output. It identifies the orphaned slot that caused the incident.
-- retained_wal is how much disk space is being held hostage by this slot.
SELECT slot_name, plugin, slot_type, database, active,
       pg_size_pretty(
           pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
       ) AS retained_wal,
       restart_lsn,
       confirmed_flush_lsn
FROM pg_replication_slots
ORDER BY pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) DESC;
```

---

## Why This Happened

PostgreSQL writes a WAL record for every change to the database. Under normal conditions, old WAL is deleted once it has been applied by replicas and archived (if archiving is configured). A replication slot changes this: it tells PostgreSQL "do not delete WAL until this subscriber has consumed it." This is the correct behavior — it prevents a standby from falling irreversibly behind.

The problem occurs when the subscriber is decommissioned — removed, reconfigured, or simply abandoned — without dropping its replication slot. PostgreSQL sees the slot as still active in its catalog. Nobody is consuming WAL. The slot's `restart_lsn` never advances. PostgreSQL keeps every WAL segment written since the subscriber disconnected.

On a busy system generating 1–5 GB of WAL per day, a slot orphaned for a week can retain 7–35 GB. On a system with a 50 GB data volume, this fills the disk completely.

This is not a PostgreSQL bug. The fix is `pg_drop_replication_slot()`. The challenge is getting the database started first so you can run it.

---

## Step 1 — Create enough free space to start the database

The database needs approximately 100–300 MB of free space to start (enough to write a checkpoint). You must free this space without risking data corruption.

**Safe space sources (try these first — zero risk of corruption):**

1. Application logs on the same volume — PostgreSQL application logs, IIS logs, event log exports. Delete anything older than 7 days.
2. Temp CSV exports or report files — anything in temp folders, Downloads, Desktop that your team placed there.
3. Old backup files (`.dump`, `.sql`, `.tar`) that have already been confirmed good — check with the team before deleting.
4. `pg_wal/archive_status/` subdirectory contents — these are metadata files (`.ready`, `.done` extensions). They are not WAL data. Typically only a few kilobytes but safe to delete.

**Target: free 500 MB minimum before attempting to start the database.**

If you cannot free 500 MB from safe sources, you must delete WAL segments. Read the warning below carefully before proceeding:

> [!WARNING]
> **Do not delete WAL files arbitrarily.** PostgreSQL requires a contiguous WAL chain to start. Deleting random files will corrupt the database and convert a recoverable disk-full incident into a data loss incident. If you are not certain which WAL files are oldest, do not delete any. Free space from another source.

**If you must delete WAL segments (last resort):**

WAL files are named with hex LSN values. Lower hex = older. Open `pg_wal` in WizTree. Sort by name. The files with the lowest hex names (e.g., `000000010000000000000001`) are the oldest. Delete 30–32 files from the lowest end to free approximately 500 MB (each WAL segment is 16 MB by default).

Keep a list of what you deleted. Add it to the post-mortem.

---

## Step 2 — Start the database via `pg_ctl` (not Windows Services)

When PostgreSQL starts via the Windows service, startup output goes to the Event Log and you cannot see errors in real time. Starting via `pg_ctl` in a CMD window lets you watch the log live.

**Open CMD as Administrator. Run:**

```cmd
"C:\Program Files\PostgreSQL\15\bin\pg_ctl.exe" start -D "C:\Program Files\PostgreSQL\15\data" -l "C:\pg_startup_log.txt"
```

Adjust the path to match your PostgreSQL version and data directory.

**In a second CMD window, watch the log:**

```cmd
powershell -Command "Get-Content 'C:\pg_startup_log.txt' -Wait"
```

**Expected output on successful start:**

```
LOG:  database system was shut down at 2025-03-14 09:23:41 BRT
LOG:  entering standby mode
LOG:  database system is ready to accept read-only connections
```
or for a primary:
```
LOG:  database system is ready to accept connections
```

**If the log shows:**
```
FATAL:  could not write to file "pg_wal/...": No space left on device
```
Not enough space was freed. Go back to Step 1 and free more space.

**If the log shows:**
```
FATAL:  invalid data in file "pg_wal/..."
```
A WAL file was corrupted (possibly during the WAL deletion step). Stop here. This is now a different incident. See [`diagnosis/corruption.md`](../diagnosis/corruption.md) and escalate via [`escalation/protocol.md`](../escalation/protocol.md).

---

## Step 3 — Identify and drop the orphaned slot

Once the database is running, connect and run:

```sql
-- Identifies the orphaned slot. The culprit will have active = false
-- and the largest retained_wal value.
SELECT slot_name, plugin, slot_type, database, active,
       pg_size_pretty(
           pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
       ) AS retained_wal
FROM pg_replication_slots
ORDER BY pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) DESC;
```

Note the `slot_name` of the orphaned slot.

**Before dropping, confirm with the client:**

"I'm about to drop the replication slot named `[slot_name]`. This will allow PostgreSQL to clean up the retained WAL and restore normal disk usage. If this slot was actively being used by a running replication consumer, that consumer will need to be reconfigured and resynced from scratch. Can you confirm this slot is no longer in use?"

Wait for confirmation before proceeding.

```sql
-- Drop the orphaned slot.
-- Replace 'slot_name_here' with the actual slot name from the query above.
SELECT pg_drop_replication_slot('slot_name_here');
```

**Immediately verify WAL cleanup has begun:**

```sql
-- Run this query, wait 60 seconds, run it again.
-- The total_wal_size should be decreasing as PostgreSQL reclaims WAL segments.
SELECT pg_size_pretty(sum(size)) AS total_wal_size,
       count(*) AS segment_count
FROM pg_ls_waldir();
```

You should see the size decreasing within 60 seconds as the checkpoint process reclaims old WAL segments.

---

## Step 4 — Verify full recovery

1. Wait 5 minutes. Re-run the `pg_ls_waldir()` size check. On a non-replicated database, expect this to settle under 1 GB.
2. Confirm clients can connect and run queries: `psql -c "SELECT 1"`
3. Check `pg_stat_replication` — confirm no remaining active replication consumers depended on the dropped slot.
4. Stop the `pg_ctl` process (Ctrl+C in the first CMD window).
5. Start the database via Windows Services (normal startup path):

```powershell
Start-Service -Name "postgresql-x64-15"  # adjust service name for your version
```

6. Run a `VACUUM` on the most active tables to ensure autovacuum catches up:

```sql
-- Run VACUUM on the tables with the most activity.
-- Identifies candidates: tables with the most dead tuples accumulated.
SELECT schemaname, relname AS table_name, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;
```

---

## Preventive Measures

**Monitor inactive slots as part of your daily health check:**

```sql
-- Alert if any inactive slot retains more than 5 GB.
-- Add this to your monitoring schedule.
SELECT slot_name, active,
       pg_size_pretty(
           pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
       ) AS retained_wal
FROM pg_replication_slots
WHERE NOT active
  AND pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) > 5 * 1024 * 1024 * 1024;
```

**Limit the number of replication slots:**

```sql
-- Check current setting.
SHOW max_replication_slots;

-- Set to the minimum number you actually use. This forces cleanup discipline.
-- Requires restart.
ALTER SYSTEM SET max_replication_slots = 5;
```

**Set max_slot_wal_keep_size (PostgreSQL 13+):**

This limits how much WAL a single slot can retain before being automatically invalidated. Important: when the limit is hit, the slot is not paused — it is **invalidated** (`invalidation_reason = 'wal_removed'`). The subscriber can no longer resume from where it left off. Physical standbys need a full `pg_basebackup`; logical subscribers need the subscription recreated. This is acceptable as a safety valve to prevent disk exhaustion, but it is not a substitute for the monitoring query above.

```sql
ALTER SYSTEM SET max_slot_wal_keep_size = '10GB';
SELECT pg_reload_conf();
```

**Disk free space alert:** set an alert at 20% remaining free space on the PostgreSQL data volume. On a system generating 2 GB of WAL per day, 20% gives you several days to respond.

---

## Cross-Reference

- How orphaned slots are discovered during lag monitoring: [`diagnosis/replication-lag.md`](../diagnosis/replication-lag.md)
- How to communicate during this recovery: [`communication/nvc-incident-communication.md`](../communication/nvc-incident-communication.md)
- Post-mortem template: [`post-mortem/template.md`](../post-mortem/template.md)
- Worked example of this incident as a post-mortem: [`post-mortem/example-pg-wal-incident.md`](../post-mortem/example-pg-wal-incident.md)
