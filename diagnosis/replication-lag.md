# Replication Lag

**Symptom:** A replica is falling behind the primary, replication lag is reported in monitoring, or replication has stopped entirely. In the specific case of an orphaned replication slot, disk space on the primary fills gradually as WAL accumulates.

**Confirmation query:**

```sql
-- Returns replication lag per connected standby.
-- write_lag: time to write WAL to standby disk
-- flush_lag: time to flush WAL to standby disk
-- replay_lag: time to apply WAL on standby
-- All three should be under 1 second on a healthy low-traffic system.
SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn,
       write_lag, flush_lag, replay_lag,
       pg_size_pretty(pg_wal_lsn_diff(sent_lsn, replay_lsn)) AS total_lag_bytes
FROM pg_stat_replication
ORDER BY replay_lag DESC NULLS LAST;
```

---

## Lag Classification

| Lag Amount | Status | Action |
|---|---|---|
| Under 1 MB | Normal | None |
| 1 MB – 100 MB | Watch it | Monitor every 5 minutes. Check for network saturation or I/O bottleneck on replica. |
| 100 MB – 1 GB | Investigate now | Begin diagnosis. Notify team lead. |
| Over 1 GB | P2 if standby is available; **P1 if the WAL directory is on the same volume as data** | Escalate. If disk fill is possible, treat as P1 immediately. |

---

## Step 1 — Check replication slot status

Run this before anything else. An orphaned slot is the most common cause of unexplained disk growth on the primary.

```sql
-- Returns all replication slots with how much WAL each one is retaining.
-- A slot with active = false and a large retained_wal value is orphaned.
-- PostgreSQL will not delete any WAL older than restart_lsn for inactive slots.
SELECT slot_name, plugin, slot_type, database, active, invalidation_reason,
       pg_size_pretty(
           pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
       ) AS retained_wal,
       restart_lsn,
       confirmed_flush_lsn
FROM pg_replication_slots
ORDER BY pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) DESC;
```

**Reading the output:**

- `active = true` — a subscriber is currently connected and consuming WAL. Normal.
- `active = false` AND `retained_wal` is small (under 100 MB) — slot exists but subscriber temporarily disconnected. Watch it.
- `active = false` AND `retained_wal` is large (hundreds of MB or GB) — **this slot is orphaned.** The subscriber has been decommissioned or is permanently disconnected, but the slot was never dropped. PostgreSQL is retaining all WAL since `restart_lsn`. If the disk is full or filling, this is the culprit.
- `invalidation_reason = 'wal_removed'` — `max_slot_wal_keep_size` was hit and the slot was automatically invalidated. The subscriber can no longer resume — it must be fully resynced.

If you find an orphaned slot, proceed to [`runbooks/pg-wal-zero-bytes-free.md`](../runbooks/pg-wal-zero-bytes-free.md) for the full recovery procedure.

---

## Step 2 — Check pg_wal directory size

```sql
-- Returns the total size of the pg_wal directory.
-- On a healthy system this is typically under 1 GB.
-- Over 5 GB warrants investigation. Over 10 GB is an active problem.
SELECT pg_size_pretty(sum(size)) AS total_wal_size,
       count(*) AS wal_segment_count
FROM pg_ls_waldir();
```

```sql
-- Check data directory location and the volume it sits on.
SHOW data_directory;
```

---

## Step 3 — Active lag (standby is running but falling behind)

If `pg_stat_replication` shows an active standby with growing lag:

**3a. Network saturation check:**

```sql
-- Compare sent_lsn vs replay_lsn rate over 60 seconds.
-- Run this twice with a 60-second gap and compare the diff.
SELECT client_addr,
       pg_size_pretty(pg_wal_lsn_diff(sent_lsn, replay_lsn)) AS current_lag,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn)) AS unsent_wal
FROM pg_stat_replication;
```

If `unsent_wal` is growing, the primary cannot send WAL fast enough — network saturation between primary and replica.

**3b. I/O bottleneck on replica:**

The standby is receiving WAL faster than it can apply it. This appears as: `flush_lag` is small but `replay_lag` is large.

Check disk I/O on the standby host. Consider increasing `wal_receiver_timeout` if the standby is frequently disconnecting.

**3c. High write amplification on primary:**

The primary is generating WAL faster than the standby can keep up with. Common causes: `autovacuum` running on many large tables simultaneously, a bulk load operation, or a poorly optimized batch job.

```sql
-- Check for active autovacuum workers.
-- Many simultaneous autovacuum workers generate heavy WAL.
SELECT pid, relid::regclass AS table_name, phase, heap_blks_total, heap_blks_scanned
FROM pg_stat_progress_vacuum
WHERE backend_type = 'autovacuum worker';
```

---

## Preventive measures

**Monitor inactive slots proactively:**

```sql
-- Add this to your regular health check schedule.
-- Alert if any inactive slot retains more than 5 GB.
SELECT slot_name, active,
       pg_size_pretty(
           pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
       ) AS retained_wal
FROM pg_replication_slots
WHERE NOT active
  AND pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) > 5 * 1024^3;
```

**Set a WAL retention limit (PostgreSQL 13+):**

```sql
-- Limits how much WAL a single slot can retain before being invalidated.
-- When exceeded, the slot is marked invalid rather than filling the disk.
-- Tradeoff: the subscriber will need a full resync (pg_basebackup for physical,
-- subscription re-creation for logical). Use this as a safety valve, not a substitute
-- for monitoring.
ALTER SYSTEM SET max_slot_wal_keep_size = '10GB';
SELECT pg_reload_conf();
```

**Disk free space alerting:**

Set an alert at 20% free space remaining on the PostgreSQL data volume. WAL accumulation from an orphaned slot can consume many gigabytes per day on a busy system, so 20% gives you time to diagnose and act.

---

## Cross-Reference

- If the disk is full or nearly full due to WAL accumulation: [`runbooks/pg-wal-zero-bytes-free.md`](../runbooks/pg-wal-zero-bytes-free.md)
- If the replica is more than 24 hours behind: [`escalation/protocol.md`](../escalation/protocol.md)
- Severity classification: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
