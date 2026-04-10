# ★ Runbook: pg_wal Zero Bytes Free

> [!IMPORTANT]
> **Severity: P1.** This incident prevents the database from starting or causes it to shut down mid-operation.
> **Estimated recovery time: 20–45 minutes** if this runbook is followed exactly.
> **Prerequisites:** OS-level access to the PostgreSQL host, PostgreSQL superuser credentials.

The `pg_wal` directory has consumed all available disk space. PostgreSQL cannot write new WAL segments. The database has shut down or refuses to start. This is not a data loss event — it is a disk space event. If you follow this runbook without deviating, recovery is predictable and complete.

The root cause is almost always one of two things:
- **(a) An orphaned replication slot** retaining WAL indefinitely because its subscriber was decommissioned without dropping the slot. This is the most common cause and what this runbook addresses.
- **(b) `archive_command` failing silently** for an extended period, causing WAL to accumulate. If you see `archive_command` errors in the log, this runbook covers the space recovery but the archive failure requires separate investigation.

---

## Pre-Recovery Checklist

Before touching anything:

- [ ] Note the current time — your post-mortem timeline starts now.
- [ ] If the database is still running: connect immediately and run the slot query below. Save the output.
- [ ] Check OS logs for PostgreSQL entries.
- [ ] Confirm `pg_wal` is the problem: identify the largest directory under the PostgreSQL data directory.

**Confirm disk exhaustion and locate pg_wal:**

```bash
# Linux / macOS
df -h $(psql -U postgres -tAc "SHOW data_directory")

# Find the data directory if psql is unavailable
psql -U postgres -tAc "SHOW data_directory"
# Then check disk usage of pg_wal specifically:
du -sh /var/lib/postgresql/15/main/pg_wal
```

```powershell
# Windows — use WizTree (free, much faster than Explorer for large directories)
# Or via PowerShell:
$dataDir = psql -U postgres -tAc "SHOW data_directory"
Get-ChildItem "$dataDir\pg_wal" | Measure-Object -Property Length -Sum |
  Select-Object @{N='TotalGB';E={[math]::Round($_.Sum/1GB,2)}}
```

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

The database needs approximately 100–300 MB of free space to start (enough to write a checkpoint). Free this space without risking data corruption.

**Safe space sources (zero risk of corruption — try these first):**

1. Application logs on the same volume. Delete anything older than your retention policy.
2. Temp files, CSV exports, report files left by operations or ETL jobs.
3. Old backup files (`.dump`, `.sql`, `.tar`) already confirmed good — check with the team before deleting.
4. `pg_wal/archive_status/` subdirectory contents — these are metadata files (`.ready`, `.done`), not WAL data. Safe to delete.

**Check and free space on Linux/macOS:**

```bash
# Find large files on the same partition as pg_wal
df -h /var/lib/postgresql/15/main/pg_wal

# Find top consumers on that partition
du -sh /var/lib/postgresql/15/main/* | sort -rh | head -20

# Check archive_status directory (safe to clear)
ls -lh /var/lib/postgresql/15/main/pg_wal/archive_status/
rm /var/lib/postgresql/15/main/pg_wal/archive_status/*.ready 2>/dev/null
rm /var/lib/postgresql/15/main/pg_wal/archive_status/*.done 2>/dev/null
```

**Target: free 500 MB minimum before attempting to start the database.**

> [!WARNING]
> **Do not delete WAL files arbitrarily.** PostgreSQL requires a contiguous WAL chain to start. Deleting random files will corrupt the database and convert a recoverable disk-full incident into a data loss incident. If you are not certain which WAL files are oldest, do not delete any. Free space from another source first.

**If you must delete WAL segments (last resort):**

WAL files are named with hex LSN values — lower hex = older. Deleting from the oldest end minimizes risk.

```bash
# Linux/macOS — list WAL files sorted oldest-first (lowest name = oldest)
ls /var/lib/postgresql/15/main/pg_wal/ | grep -v '\.history\|archive_status' | sort | head -35

# Each WAL segment is 16 MB by default.
# Deleting 32 files frees ~500 MB.
# Delete the oldest 32 — adjust the count to your situation:
ls /var/lib/postgresql/15/main/pg_wal/ | grep -v '\.history\|archive_status' | \
  sort | head -32 | xargs -I{} rm /var/lib/postgresql/15/main/pg_wal/{}
```

```powershell
# Windows — list WAL files oldest-first
Get-ChildItem "C:\Program Files\PostgreSQL\15\data\pg_wal" -File |
  Where-Object { $_.Name -notmatch '\.history$' } |
  Sort-Object Name | Select-Object -First 32 | Select-Object Name, Length
# Review the list, then delete:
# Get-ChildItem ... | Sort-Object Name | Select-Object -First 32 | Remove-Item
```

Keep a list of what you deleted. Add it to the post-mortem.

---

## Step 2 — Start the database (watch live output)

Starting via `pg_ctl` or equivalent — not through the service manager — lets you watch startup errors in real time.

**Linux / macOS:**

```bash
# As the postgres OS user:
sudo -u postgres pg_ctl start \
  -D /var/lib/postgresql/15/main \
  -l /tmp/pg_startup.log

# Watch the log live in a second terminal:
tail -f /tmp/pg_startup.log

# Alternative: start and check journal (systemd)
sudo systemctl start postgresql@15-main
journalctl -u postgresql@15-main -f --no-pager
```

**Windows:**

```cmd
"C:\Program Files\PostgreSQL\15\bin\pg_ctl.exe" start ^
  -D "C:\Program Files\PostgreSQL\15\data" ^
  -l "C:\pg_startup_log.txt"
```

```powershell
# Watch log live in a second window:
Get-Content "C:\pg_startup_log.txt" -Wait
```

**Expected output on successful start:**

```
LOG:  database system was shut down at 2025-03-14 09:23:41 UTC
LOG:  database system is ready to accept connections
```

**If the log shows:**
```
FATAL:  could not write to file "pg_wal/...": No space left on device
```
Not enough space was freed. Go back to Step 1.

**If the log shows:**
```
FATAL:  invalid data in file "pg_wal/..."
```
A WAL file is corrupted. Stop here. See [`diagnosis/corruption.md`](../diagnosis/corruption.md) and escalate via [`escalation/protocol.md`](../escalation/protocol.md).

---

## Step 3 — Identify and drop the orphaned slot

Once the database is running:

```sql
-- The orphaned slot will have active = false and the largest retained_wal.
SELECT slot_name, plugin, slot_type, database, active,
       pg_size_pretty(
           pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
       ) AS retained_wal
FROM pg_replication_slots
ORDER BY pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) DESC;
```

Note the `slot_name`. **Before dropping, confirm with the client or team:**

> "I'm about to drop the replication slot `[slot_name]`. This allows PostgreSQL to reclaim the retained WAL. If this slot is still in use by a replication consumer, that consumer will need a full resync. Please confirm it's safe to drop."

```sql
-- Drop the slot. Replace 'slot_name_here' with the actual name.
SELECT pg_drop_replication_slot('slot_name_here');
```

**Verify WAL reclamation has begun:**

```sql
-- Run this, wait 60 seconds, run again — size should be decreasing.
SELECT pg_size_pretty(sum(size)) AS total_wal_size,
       count(*) AS segment_count
FROM pg_ls_waldir();
```

You should see the size drop within 60 seconds as the checkpoint process reclaims old segments.

---

## Step 4 — Verify full recovery

1. Wait 5 minutes. Re-run the `pg_ls_waldir()` size check. Expect under 1 GB for a non-replicated database.
2. Confirm clients can connect: `psql -c "SELECT 1"`
3. Check `pg_stat_replication` — confirm no remaining consumers depended on the dropped slot.
4. Return the database to normal service management:

```bash
# Linux — hand back to systemd
sudo -u postgres pg_ctl stop -D /var/lib/postgresql/15/main
sudo systemctl start postgresql@15-main
systemctl status postgresql@15-main
```

```powershell
# Windows — stop pg_ctl process (Ctrl+C), then start via Services
Start-Service -Name "postgresql-x64-15"
```

5. Run VACUUM on the most active tables:

```sql
-- Find tables with the most accumulated dead tuples after the outage.
SELECT schemaname, relname AS table_name, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;
-- Then: VACUUM ANALYZE <table_name>;
```

---

## Preventive Measures

**Monitor inactive slots — add to your daily health check:**

```sql
-- Alert if any inactive slot retains more than 5 GB.
SELECT slot_name, active,
       pg_size_pretty(
           pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
       ) AS retained_wal
FROM pg_replication_slots
WHERE NOT active
  AND pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) > 5 * 1024 * 1024 * 1024;
```

**Disk free space alert:**

```bash
# Linux — add to cron or monitoring system
# Alert when pg_wal partition is below 20% free
df -h /var/lib/postgresql/15/main/pg_wal
```

Set the alert threshold at **20% remaining** on the PostgreSQL data volume. On a system generating 2 GB of WAL per day, 20% gives you several days to respond.

**Limit replication slots:**

```sql
-- Minimum slots you actually use. Prevents accumulation of forgotten slots.
-- Requires restart.
ALTER SYSTEM SET max_replication_slots = 5;
```

**Set `max_slot_wal_keep_size` (PostgreSQL 13+):**

This limits how much WAL a single slot can retain before being automatically invalidated. When the limit is hit, the slot is **invalidated** (`invalidation_reason = 'wal_removed'`) — not paused. The subscriber can no longer resume and must be fully resynced (physical standbys need `pg_basebackup` again; logical subscribers need subscription recreation). Use this as a safety valve, not a substitute for monitoring.

```sql
ALTER SYSTEM SET max_slot_wal_keep_size = '10GB';
SELECT pg_reload_conf();
```

---

## Cross-Reference

- How orphaned slots are discovered during lag monitoring: [`diagnosis/replication-lag.md`](../diagnosis/replication-lag.md)
- How to communicate during this recovery: [`communication/nvc-incident-communication.md`](../communication/nvc-incident-communication.md)
- Post-mortem template: [`post-mortem/template.md`](../post-mortem/template.md)
- Worked example post-mortem for this incident: [`post-mortem/example-pg-wal-incident.md`](../post-mortem/example-pg-wal-incident.md)
