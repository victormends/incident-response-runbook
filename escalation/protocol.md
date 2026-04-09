# Escalation Protocol

Escalation is not a failure. The most common escalation anti-pattern is a solo engineer spending 2–3 hours on a P1 without asking for help because they don't want to "look bad." An engineer who escalates at the right moment with complete information is more valuable than one who stays silent and misses the resolution window.

The rule is simple: if you have followed the relevant diagnosis checklist and the incident is not resolved or stabilized within the time limits below, escalate.

| Severity | Escalate if not stabilized within |
|---|---|
| P1 | **20 minutes** from incident open |
| P2 | **60 minutes** from incident open |
| P3 | **48 hours** from incident open — review for upgrade, not escalation |

---

## Information to Gather Before Escalating

Escalating without complete information wastes the time of the person you're escalating to. Before making the escalation call or message, have all of the following ready:

- [ ] **Current severity classification** and why (reference [`severity-classification/matrix.md`](../severity-classification/matrix.md))
- [ ] **Incident timeline so far** — timestamps of key events, what was observed, what was tried
- [ ] **Current system state** — exact output of `pg_stat_activity`, relevant log lines (exact text, not paraphrased), any error messages
- [ ] **Hypotheses tested** — what you have already ruled out and how
- [ ] **Stabilization attempts** — what actions you have taken and their results
- [ ] **Client communication log** — what you told the client, when, and their response

If you cannot answer all of the above in 2 minutes, spend 2 more minutes filling in the gaps before escalating. A complete handoff takes 5 minutes. An incomplete one takes 20.

---

## Escalation Matrix

| Condition | Escalation Level | Contact Method | Maximum Response Time |
|---|---|---|---|
| P1 — data loss or corruption suspected | Immediate | Direct call to senior engineer AND account manager | Senior engineer: 10 minutes. Account manager: 30 minutes. |
| P1 — database unreachable, not stabilized in 20 minutes | Tier 1 | Ticket update + direct call to team lead | 15 minutes |
| P1 — fiscal integration blocked (NF-e, CT-e, payroll) during business hours | Immediate | Direct call, regardless of severity classification | 10 minutes |
| P2 — not resolved in 4 hours | Tier 1 | Ticket update + team lead notification | 30 minutes |
| P2 — client verbally states operations are fully stopped | Immediate reclassification to P1 | Reclassify, then follow P1 escalation | Immediately |
| Any incident — client mentions cancellation | Immediate | Account manager notified regardless of technical severity | 15 minutes |
| P3 — not resolved in 48 hours | Review | Team lead reviews for P2 upgrade | Next business day |

---

## What to Say When Escalating

Use observation language. Your escalation message is the basis for the escalating engineer's first actions — make it factual and complete.

**Template for team lead escalation:**

```
"Escalating [incident ID] to P1. Database has been unreachable for [X] minutes.
Confirmed cause: [specific observation — e.g., 'pg_wal directory at 100%, orphaned slot identified'].
I have freed [X] MB of disk space. Database start attempt [succeeded/failed with error: <exact error>].
Client [A] has been notified at [time]. Next update due at [time].
I need [specific ask — e.g., 'a second set of eyes on the WAL directory' or 'confirmation that slot X is safe to drop'].
Can you join in [5/10] minutes?"
```

**Template for account manager notification:**

```
"Client [A] is experiencing a P1 — database unreachable since [time].
Technical team is working the incident. Current status: [one sentence].
Client contact is [name]. They have been updated at [time] and expect a callback at [time].
No data loss confirmed. I wanted you informed in case the client contacts you directly."
```

---

## Client Escalation Management

When the client's manager escalates above you — calls your manager directly, or threatens cancellation — do not match their urgency with defensiveness. The pattern that works:

1. **Acknowledge the impact** (observation): "I understand your operations have been stopped for [X] minutes."
2. **Name what is happening technically** (observation, no evaluation): "The database became unavailable due to a disk capacity issue. We have identified the cause."
3. **Make a specific request**: "I'm escalating this to our senior engineering team now. I will have them contact you directly within 15 minutes. In the meantime, I will continue working the recovery."

Do not apologize for things that have not been confirmed as your fault. Do not promise timelines you cannot meet. Do not speculate about causes in front of a client who is already escalating.

---

## Post-Escalation

When the incident is resolved, the escalating engineer retains ownership of:

1. Completing the post-mortem — the escalating party fills the template, the escalated party reviews
2. Closing the client communication loop — the client hears from the same person who opened the incident
3. Logging the escalation in the post-mortem's communication review section

If escalation was triggered by the 20-minute P1 rule and the incident resolved before the escalated party joined, document that in the post-mortem. The escalation was still the right call.

---

## Cross-Reference

- Severity definitions: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
- NVC-based communication during escalation: [`communication/nvc-incident-communication.md`](../communication/nvc-incident-communication.md)
- Post-mortem template (include escalation history): [`post-mortem/template.md`](../post-mortem/template.md)
- War room management after escalation: [`war-room/etiquette.md`](../war-room/etiquette.md)
