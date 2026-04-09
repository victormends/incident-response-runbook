# Post-Mortem Template

Every P1 and significant P2 incident produces a filled copy of this template. Copy this file, rename it with the incident date and a short description (e.g., `2025-03-14-pg-wal-disk-exhaustion.md`), and fill each section.

This template is a forcing function for honest root cause analysis, not a bureaucratic exercise. The goal is to produce an artifact that prevents the same incident from recurring — not one that demonstrates the team responded well.

> [!NOTE]
> This section is not a blame log. Name behaviors and processes, not people. A post-mortem that identifies "engineer X made a mistake" is incomplete. The actionable question is: what process or monitoring gap allowed that mistake to have this impact?

---

## Incident Metadata

| Field | Value |
|---|---|
| **Title** | *(short description, e.g., "pg_wal disk exhaustion — orphaned replication slot")* |
| **Severity** | *(P1 / P2 — see [severity-classification/matrix.md](../severity-classification/matrix.md))* |
| **Incident opened** | *(timestamp: YYYY-MM-DD HH:MM BRT)* |
| **Incident resolved** | *(timestamp: YYYY-MM-DD HH:MM BRT)* |
| **Total duration** | *(HH:MM)* |
| **Affected systems** | *(e.g., "PostgreSQL 15 primary — production cluster")* |
| **Affected clients** | *(anonymized: "Client A", "Client B" — do not include client names in this file)* |
| **Primary responder** | *(name)* |
| **Secondary responders** | *(names, if any)* |

---

## Executive Summary

*(3–5 sentences written for a non-technical reader. What happened, how long it lasted, how it was resolved, and what the client experienced. This section should be readable by the client's CEO without requiring technical context.)*

Example structure: "At [time], [system] became unavailable due to [cause in plain language]. The incident lasted [duration]. The root cause was [plain language description]. Service was restored at [time] by [plain language action]. No data was lost."

---

## Incident Timeline

Record every event with a timestamp and a source. Minimum granularity during an active P1: every 5 minutes.

| Time | Event | Source | Action Taken |
|---|---|---|---|
| HH:MM | *(what happened or was observed)* | *(who observed it / what tool)* | *(what was done in response)* |
| HH:MM | | | |
| HH:MM | | | |

The timeline should feel like an audit log — factual, sourced, no interpretations. "Client reported database unreachable" is correct. "Client reported database was broken because of the update" is not — that is an evaluation.

---

## Technical Root Cause

A single incident typically has three layers of cause. Identifying all three is what separates a post-mortem from a ticket closure.

**Proximate cause** — the immediate trigger. What changed or failed at the moment the incident began?

*(e.g., "The pg_wal directory reached 100% disk utilization, preventing PostgreSQL from writing new WAL segments.")*

**Contributing cause** — the condition that made the proximate cause possible. What pre-existing state allowed this to happen?

*(e.g., "A replication slot named `backup_legacy_subscriber` had been inactive for 6 days, retaining 47 GB of WAL because its subscriber was decommissioned without dropping the slot.")*

**Systemic cause** — the process or monitoring gap that allowed the contributing cause to exist undetected.

*(e.g., "No monitoring existed for inactive replication slots with retained WAL above a threshold. The disk utilization alert was configured at 90%, which on a 50 GB volume gave less than 5 GB of warning — insufficient time to diagnose and respond before exhaustion.")*

---

## 5-Whys Analysis

Start from the proximate cause. Ask "why?" five times. Each answer becomes the starting point for the next. The analysis must terminate at something actionable — a process gap, a monitoring gap, or a configuration standard. If it terminates at "someone made a mistake," the analysis is incomplete.

1. **Why did the database stop accepting writes?** *(Proximate cause — disk full)*
2. **Why was the disk full?** *(pg_wal directory consumed all space)*
3. **Why did pg_wal grow to this size?** *(Orphaned slot retained WAL for 6 days)*
4. **Why was the slot not dropped when the subscriber was decommissioned?** *(No documented procedure for decommissioning replication subscribers)*
5. **Why was there no procedure?** *(Replication slots were not part of the standard offboarding checklist for database clients)*

---

## Communication Review

This section reviews the quality of communication during the incident, not just the technical response. It feeds directly into improving the NVC practices described in [`communication/nvc-incident-communication.md`](../communication/nvc-incident-communication.md).

| Field | Value |
|---|---|
| **First client contact** | *(time, channel — phone/email/ticket, and the exact message sent)* |
| **First client update** | *(time and content of first substantive update — what was confirmed, what the timeline was)* |
| **Update cadence followed** | *(e.g., "Updates at HH:MM, HH:MM, HH:MM — every 30 minutes as per P1 protocol")* |
| **Escalation history** | *(who was notified, when, and what they were asked to do)* |
| **Client's sentiment at resolution** | *(e.g., "Client confirmed operations restored, expressed frustration about duration but accepted explanation and preventive measures")* |

**Communication quality assessment:**

- Did the first client contact follow the de-escalation script from the NVC chapter? *(Y/N — if N, note what was said instead)*
- Were client updates sent on the P1 cadence (every 30 minutes)? *(Y/N — if N, note the gaps)*
- Was premature diagnosis or reassurance communicated before confirmation? *(Y/N — if Y, note what was said)*

---

## Corrective Actions

Tactical fixes for this specific incident.

| Action | Owner | Due Date | Status |
|---|---|---|---|
| *(e.g., "Drop orphaned replication slot `backup_legacy_subscriber`")* | | | |
| *(e.g., "Restore client database access and confirm operations")* | | | |
| | | | |

---

## Preventive Actions

Systemic improvements that prevent the class of incident, not just this instance. Corrective actions fix the wound. Preventive actions close the gap that allowed it.

| Action | Owner | Due Date | Status |
|---|---|---|---|
| *(e.g., "Add monitoring query for inactive slots with retained WAL > 5 GB")* | | | |
| *(e.g., "Document and add slot cleanup to client decommissioning checklist")* | | | |
| *(e.g., "Set disk utilization alert threshold from 90% to 80% on data volume")* | | | |
| | | | |

---

## Lessons Learned

*(Free-form. Write honestly. Name behaviors and processes, not people. What would you do differently? What worked well that should be preserved? What do you now know that you didn't before?)*

---

## Cross-Reference

- Severity definitions: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
- Escalation protocol followed: [`escalation/protocol.md`](../escalation/protocol.md)
- For WAL incidents: [`runbooks/pg-wal-zero-bytes-free.md`](../runbooks/pg-wal-zero-bytes-free.md)
- NVC communication review: [`communication/nvc-incident-communication.md`](../communication/nvc-incident-communication.md)
