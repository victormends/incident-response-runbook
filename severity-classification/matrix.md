# Severity Classification Matrix

This document defines severity levels for all incidents affecting PostgreSQL environments. Every response procedure in this runbook references these definitions. When an incident is reported, classify it here first — the classification determines your response SLA, escalation path, and communication cadence.

If two engineers independently classify the same incident, they should agree 90% of the time. If the definitions feel ambiguous for a specific case, default to the higher severity and reassess after initial stabilization.

> [!NOTE]
> **Adapt SLAs to your team's capacity.** The SLA values below (15-minute P1 response, 4-hour resolution) assume a dedicated on-call engineer with access to all systems. A solo engineer covering 500+ clients during business hours has different operational realities than a 24/7 NOC. The *structure* of the matrix — classification criteria, escalation triggers, communication cadence — transfers directly. The *numbers* should be calibrated to whatever your actual SLA contract or operational agreement states. If you have no formal SLA, these defaults are a reasonable starting point.

---

## Severity Matrix

| Severity | Name | Definition | Business Impact | Initial Response SLA | Resolution SLA | Escalation Path | Communication Cadence |
|---|---|---|---|---|---|---|---|
| **P1** | Critical | Database completely unreachable; OR confirmed data loss or corruption; OR a running fiscal process (NF-e transmission, payroll, CT-e) is blocked with no workaround available | Client operations fully stopped. Revenue impact is active and measurable. | **15 minutes** | **4 hours** or formal workaround with client sign-off | Primary responder + team lead notified immediately. Account manager notified within 30 minutes. | Every **30 minutes** to client. Every 15 minutes internally until stabilized. |
| **P2** | Major | Database reachable but a critical function is failing: report generation returning errors, ETL pipeline failing, replication lag exceeding 1 GB, or a subset of users unable to connect due to authentication or connection limit issues | Significant portion of client operations degraded. Critical functions unavailable but core database accessible. | **1 hour** | **8 hours** | Primary responder + team lead notified within 30 minutes of classification. | Every **2 hours** to client. |
| **P3** | Moderate | A feature behaves incorrectly but the client can continue operations. Performance degraded but not at a level blocking work. Non-critical integration failing. Anomalous log entries without confirmed impact. | Client operational but with friction. No active revenue impact. | **4 hours** | **Next business day** | Primary responder owns it. Team lead notified only if SLA risk emerges. | **Daily update** until resolved. |
| **P4** | Low | Cosmetic issues, documentation requests, configuration questions, non-impacting anomalies. Incidents confirmed to have no operational impact. | No operational impact. | **Next business day** | **Next sprint or maintenance window** | Primary responder owns it. No escalation required. | **On resolution** only. |

---

## Severity Escalation Triggers

These conditions automatically upgrade an incident to a higher severity, regardless of initial classification. Review these before finalizing any classification:

- A P2 incident affecting a fiscal integration (NF-e, CT-e, NFC-e) **during an open transmission window** (business hours, month-end close, tax deadlines) is immediately reclassified as **P1**.
- A P3 incident not resolved within **48 hours** is reviewed for upgrade to P2 by the team lead.
- Any P3 or P4 incident where **data integrity cannot be confirmed** is immediately reclassified as **P1** pending verification.
- A P2 where the client verbally states that their business operations are fully stopped is reclassified as **P1** — client-reported impact overrides technical classification when in doubt.
- A P2 where the primary responder has been working the issue for more than 2 hours without stabilization is reviewed for P1 escalation.
- **Replication lag exceeding 5 GB** on a production primary is automatically P1, regardless of current standby availability.

---

## Severity Downgrade Protocol

An incident may be downgraded only when all of the following are true:

1. The condition that triggered the original severity is no longer active (e.g., database is reachable again, fiscal process has resumed).
2. A workaround is in place and confirmed stable for at least 15 minutes.
3. The client contact has been informed of the downgrade and has not objected.

Downgrade is a **bilateral decision** — the engineer proposes it, the client confirms it. An engineer cannot unilaterally close or downgrade a P1 without client acknowledgment.

Document the downgrade time and rationale in the incident ticket.

---

## Cross-Reference

- For initial classification decisions: see [`triage/flowchart.md`](../triage/flowchart.md)
- When escalation is required: see [`escalation/protocol.md`](../escalation/protocol.md)
