# Post-Mortem: pg_wal Disk Exhaustion — Orphaned Replication Slot

*This is a worked example of the post-mortem template using a realistic incident. Details have been anonymized. Use this as a reference when filling your first post-mortem — the level of detail, the tone, and the structure here are the target.*

---

## Incident Metadata

| Field | Value |
|---|---|
| **Title** | pg_wal disk exhaustion — orphaned replication slot `backup_legacy_subscriber` |
| **Severity** | P1 |
| **Incident opened** | 2025-03-14 09:47 BRT |
| **Incident resolved** | 2025-03-14 10:31 BRT |
| **Total duration** | 0:44 |
| **Affected systems** | PostgreSQL 15 primary — production ERP cluster, Client A |
| **Affected clients** | Client A (fiscal operations fully blocked) |
| **Primary responder** | Victor M. |
| **Secondary responders** | None — resolved without escalation |

---

## Executive Summary

At 09:47, Client A reported that their ERP system was displaying database connection errors across all terminals. Investigation confirmed that the PostgreSQL database had shut itself down because the disk volume hosting the data directory had reached 100% utilization. The root cause was a replication slot that had been left active in PostgreSQL's catalog after a subscriber was decommissioned six days earlier, during which time it retained 47 GB of WAL segments that could not be deleted. Service was restored at 10:31 by freeing sufficient disk space to restart the database and then dropping the orphaned slot, which allowed PostgreSQL to reclaim the retained WAL. No data was lost. Client A's fiscal operations resumed without requiring any data recovery.

---

## Incident Timeline

| Time | Event | Source | Action Taken |
|---|---|---|---|
| 09:47 | Client A reports all ERP terminals showing "could not connect to server" | Client phone call | Opened incident as P1. De-escalation script delivered. Client informed of 15-min callback. |
| 09:49 | Confirmed PostgreSQL service stopped on Client A's server | Windows Services remote check | Attempted `pg_ctl start` to see startup errors live |
| 09:51 | `pg_ctl` log shows: `FATAL: could not write to file "pg_wal/0000000100000025": No space left on device` | pg_startup_log.txt | Identified pg_wal as cause. Opened WizTree to assess disk usage. |
| 09:53 | WizTree confirms: pg_wal = 47.2 GB, total disk = 50.0 GB, free = 0 bytes | WizTree scan | Began identifying safe sources of disk space to free |
| 09:55 | Found 1.8 GB of PostgreSQL application logs older than 14 days on same volume | WizTree | Deleted logs after confirming with team lead that they were beyond retention policy |
| 09:58 | First client callback — confirmed database still down, shared that cause was identified (disk full), estimated 15 more minutes | Phone call to Client A | Client accepted timeline. Second callback scheduled for 10:15. |
| 10:02 | `pg_ctl start` succeeded after freeing 1.8 GB. Database online. | pg_startup_log.txt | Connected immediately to run slot diagnosis query |
| 10:04 | Query confirms: slot `backup_legacy_subscriber` inactive, retaining 47.1 GB WAL, `active = false` | `pg_replication_slots` query | Identified slot as orphaned. Checked with team lead on which subscriber this belonged to. |
| 10:07 | Confirmed with team lead: this slot was for a legacy reporting subscriber decommissioned on 2025-03-08. Subscriber confirmed no longer in use. | Internal Slack | Received confirmation to drop the slot. |
| 10:09 | `SELECT pg_drop_replication_slot('backup_legacy_subscriber')` executed | psql | Slot dropped successfully. Began monitoring pg_ls_waldir() size. |
| 10:11 | WAL directory size dropping: 47 GB → 38 GB. PostgreSQL reclaiming segments. | `pg_ls_waldir()` query | Continued monitoring. Notified client that resolution was in progress. |
| 10:21 | WAL directory size stabilized at 890 MB. Disk free: 41 GB. | `pg_ls_waldir()` query | Ran VACUUM on top 3 tables by dead tuple count. Confirmed all client connections working. |
| 10:31 | Client A confirmed all ERP terminals operational. Fiscal operations resumed. | Client phone call | Closed P1. Began post-mortem. |

---

## Technical Root Cause

**Proximate cause:** The `pg_wal` directory reached 100% disk utilization (47.2 GB on a 50 GB volume), preventing PostgreSQL from writing new WAL segments and causing the database service to shut down.

**Contributing cause:** Replication slot `backup_legacy_subscriber` had been inactive since 2025-03-08, when the subscriber (a legacy reporting tool) was decommissioned and its server reconfigured. The slot was never dropped from PostgreSQL's catalog. PostgreSQL retained every WAL segment written after the slot's `restart_lsn` (approximately 2025-03-08 14:30), accumulating 47 GB over 6 days at an average WAL generation rate of ~7.8 GB/day on this client's cluster.

**Systemic cause:** No monitoring existed for inactive replication slots with retained WAL above a threshold. The disk utilization alert was configured at 90% utilization, which on a 50 GB volume triggered at 45 GB used — only 5 GB before exhaustion, and 2 GB of that was consumed in less than 8 hours. The subscriber decommissioning process had no documented step for dropping associated replication slots.

---

## 5-Whys Analysis

1. **Why did the database stop accepting writes?** The disk volume reached 0 bytes free and PostgreSQL could not write new WAL segments.
2. **Why was the disk full?** The `pg_wal` directory had grown to 47 GB, consuming almost the entire 50 GB data volume.
3. **Why did `pg_wal` grow to 47 GB?** Replication slot `backup_legacy_subscriber` was retaining all WAL since 2025-03-08 because its subscriber was decommissioned without the slot being dropped.
4. **Why was the slot not dropped when the subscriber was decommissioned?** The decommissioning procedure did not include a step to check and drop associated replication slots. The person who decommissioned the subscriber was not aware that the slot needed to be explicitly dropped.
5. **Why was there no such step in the procedure?** Replication slot lifecycle management was not part of the documented operational procedures for managing database client environments. The knowledge existed informally but was not codified.

---

## Communication Review

| Field | Value |
|---|---|
| **First client contact** | 09:47 — phone call. Script used: *"Client A, I have your incident open. I can confirm the database has been unreachable since approximately 09:45 — that's about 2 minutes. I don't have a diagnosis yet, and I'm not going to guess. I'm running the initial checks right now. I'll call you back in 15 minutes with confirmed findings. If anything changes before that, I'll contact you immediately."* |
| **First client update** | 09:58 — phone call. *"I've confirmed the cause: the disk hosting the database filled up completely. I've freed space and the database is starting now. I expect to have full service restored within 15 minutes. I'll call you immediately when it's confirmed."* |
| **Update cadence followed** | Updates at 09:47, 09:58, 10:11 (text), 10:31 (call). P1 cadence maintained. |
| **Escalation history** | No external escalation. Team lead consulted at 10:04 to confirm slot ownership before dropping. |
| **Client's sentiment at resolution** | Client expressed frustration at the duration of the outage and asked what would prevent recurrence. Accepted the explanation and the preventive measures proposed. No cancellation threat. |

**Communication quality assessment:**

- De-escalation script followed on first contact: **Yes**
- Update cadence (every 30 min) maintained: **Yes**
- Premature diagnosis or reassurance communicated before confirmation: **No** — first update at 09:58 was delivered only after startup was confirmed and cause was identified

---

## Corrective Actions

| Action | Owner | Due Date | Status |
|---|---|---|---|
| Dropped orphaned slot `backup_legacy_subscriber` | Victor M. | 2025-03-14 | Done |
| Confirmed Client A database operational and fiscal operations resumed | Victor M. | 2025-03-14 | Done |
| Verified no remaining inactive slots with >1 GB retained WAL on Client A cluster | Victor M. | 2025-03-14 | Done |

---

## Preventive Actions

| Action | Owner | Due Date | Status |
|---|---|---|---|
| Add monitoring query for inactive slots with retained WAL > 5 GB to daily health check schedule | Victor M. | 2025-03-21 | Pending |
| Add "drop replication slots" step to subscriber decommissioning checklist | Victor M. | 2025-03-21 | Pending |
| Lower disk utilization alert threshold from 90% to 80% on all client PostgreSQL data volumes | Victor M. | 2025-03-28 | Pending |
| Document `max_slot_wal_keep_size` configuration recommendation and add to new cluster provisioning checklist | Victor M. | 2025-03-28 | Pending |

---

## Lessons Learned

The technical resolution was straightforward once the database was accessible. The 44-minute total duration was dominated by two periods: freeing disk space (9 minutes, 09:51–10:02) and confirming slot ownership before dropping it (7 minutes, 10:04–10:11). Neither was avoidable given the information available.

What would have prevented this incident entirely: a monitoring query that alerts when an inactive slot retains more than 5 GB. This query costs nothing to run and would have flagged the problem on day 2 instead of day 6. The cost of this incident — 44 minutes of client downtime, one P1 call, and likely a difficult renewal conversation — is far larger than the cost of adding one query to a health check schedule.

The decommissioning procedure gap was the more significant finding. The person who decommissioned the subscriber knew how to do it at the application level but did not know that the PostgreSQL replication slot needed to be explicitly dropped. This is not a knowledge failure — it is a procedure gap. The knowledge is now documented. The next decommissioning will follow a checklist that includes this step.

Communication held throughout. The de-escalation script worked exactly as intended on the first call. The client's initial frustration de-escalated after the 09:58 update — having a confirmed cause and a specific timeline ("15 more minutes") was more effective than any amount of reassurance without information.

---

## Cross-Reference

- Full recovery procedure: [`runbooks/pg-wal-zero-bytes-free.md`](../runbooks/pg-wal-zero-bytes-free.md)
- How orphaned slots are detected during monitoring: [`diagnosis/replication-lag.md`](../diagnosis/replication-lag.md)
- Communication framework used: [`communication/nvc-incident-communication.md`](../communication/nvc-incident-communication.md)
- Post-mortem template: [`template.md`](./template.md)
