![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![ITIL-aligned](https://img.shields.io/badge/ITIL-aligned-blue)
![NVC-integrated](https://img.shields.io/badge/NVC-integrated-purple)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)

# incident-response-runbook

A production-grade incident response framework for PostgreSQL environments that treats communication failure as a first-class technical problem.

---

## The Problem This Solves

Most P1 incidents are resolved slowly for one of three reasons.

The first: the technical diagnosis loop gets corrupted by emotional escalation. A client calls in a panic, the engineer feels pressured to give an answer before they have one, they guess wrong, and now 20 minutes are gone on a false hypothesis while the client grows angrier.

The second: responders work from memory instead of structure. An engineer who has resolved five connection exhaustion incidents has a mental checklist. An engineer facing their second P1 at 2am does not. The difference in resolution time is not talent — it is the existence of a written path to follow.

The third: post-mortem actions get written and never reviewed. The incident closes, the corrective actions are logged in a ticket, and three months later the same class of incident recurs because the systemic cause was identified but the preventive fix was never implemented.

This runbook addresses all three.

---

## What's in This Repo

| Document | Category | Description |
|---|---|---|
| [`severity-classification/matrix.md`](severity-classification/matrix.md) | Classification | P1–P4 definitions, SLAs, escalation paths, and communication cadences |
| [`triage/flowchart.md`](triage/flowchart.md) | Triage | Mermaid decision tree from "incident reported" to the correct checklist |
| [`diagnosis/connection-exhaustion.md`](diagnosis/connection-exhaustion.md) | Diagnosis | Step-by-step diagnosis for max_connections exhaustion |
| [`diagnosis/replication-lag.md`](diagnosis/replication-lag.md) | Diagnosis | Replication lag, orphaned slot detection, WAL retention monitoring |
| [`diagnosis/lock-contention.md`](diagnosis/lock-contention.md) | Diagnosis | Lock wait chain visualization, deadlock diagnosis, emergency unlock |
| [`diagnosis/auth-failure.md`](diagnosis/auth-failure.md) | Diagnosis | Authentication failures: SCRAM/MD5 mismatch, pg_hba.conf rules, peer auth, TLS |
| [`diagnosis/corruption.md`](diagnosis/corruption.md) | Diagnosis | Initial corruption triage — symptoms, verification queries, escalation |
| ★ [`runbooks/pg-wal-zero-bytes-free.md`](runbooks/pg-wal-zero-bytes-free.md) | Runbook | Full step-by-step recovery for pg_wal disk exhaustion (Linux, macOS, Windows) |
| ★ [`communication/nvc-incident-communication.md`](communication/nvc-incident-communication.md) | Communication | NVC four-step framework applied to incident communication |
| [`post-mortem/template.md`](post-mortem/template.md) | Post-mortem | Reusable template with 5-whys, communication review, corrective/preventive actions |
| [`post-mortem/example-pg-wal-incident.md`](post-mortem/example-pg-wal-incident.md) | Post-mortem | Worked example: WAL disk exhaustion from orphaned replication slot |
| [`post-mortem/example-connection-exhaustion.md`](post-mortem/example-connection-exhaustion.md) | Post-mortem | Worked example: connection pool exhaustion from ORM transaction leak |
| [`escalation/protocol.md`](escalation/protocol.md) | Escalation | When to escalate, what to prepare, escalation matrix, client management |
| [`war-room/etiquette.md`](war-room/etiquette.md) | War room | Roles, the three rules, time-boxing decisions, post-war-room capture |

★ Flagship documents — start here if you're reading this for the first time.

---

## Quick Start

**Step 1:** Bookmark [`severity-classification/matrix.md`](severity-classification/matrix.md). When a ticket comes in, classify it before anything else. The classification determines your SLA, escalation path, and communication cadence.

**Step 2:** Drill [`triage/flowchart.md`](triage/flowchart.md) until you can follow it without reading the instructions at the top. During an active P1, you need to reach an initial hypothesis within 5 minutes — the flowchart is the path.

**Step 3:** Read [`communication/nvc-incident-communication.md`](communication/nvc-incident-communication.md) before your next P1. Specifically, memorize the de-escalation script. The 90 seconds after you pick up a client's P1 call determine whether the next hour goes well or poorly. That script is the most immediately useful artifact in this repo.

---

## Platform Support

All runbooks and checklists include commands for **Linux**, **macOS**, and **Windows**. The SQL queries are platform-independent — they run against any PostgreSQL instance regardless of OS.

The auth failure diagnosis covers the SCRAM-SHA-256 / MD5 mismatch that affects every PostgreSQL 14+ upgrade. The WAL runbook covers `pg_ctl`, `systemctl`, and Windows Services. The triage flowchart includes `journalctl`, `tail`, `Get-Content`, and `sc query` equivalents.

---

## The NVC Angle

Nonviolent Communication (NVC) was developed by Marshall Rosenberg and published in *Nonviolent Communication: A Language of Life* (1999). It was designed for conflict resolution. Its four-step structure — Observation, Feeling, Need, Request — maps almost exactly onto what incident communication requires.

NVC is not soft skills appended to a technical process. It is a precision tool that eliminates the most expensive failure mode in incident response: miscommunication under stress.

The structural parallel is direct. In conflict resolution, two people have different perceptions of the same event. In incident response, an engineer and a client have different information about the same system failure. The failure mode is identical — evaluation masquerading as observation, leading to defensive communication, leading to a loop that consumes time without producing information.

The NVC four-step structure breaks this loop at the first step. An engineer who stays in observation language under pressure — "the database has been unreachable for 12 minutes since the 14:30 deployment" rather than "the database is broken" — has already made the next 30 minutes more productive than they would have been otherwise.

---

## Repo Structure

```
incident-response-runbook/
  severity-classification/
    matrix.md
  triage/
    flowchart.md
  diagnosis/
    connection-exhaustion.md
    replication-lag.md
    lock-contention.md
    auth-failure.md
    corruption.md
  runbooks/
    pg-wal-zero-bytes-free.md
  communication/
    nvc-incident-communication.md
  post-mortem/
    template.md
    example-pg-wal-incident.md
    example-connection-exhaustion.md
  escalation/
    protocol.md
  war-room/
    etiquette.md
  LICENSE
  README.md
```

---

## License

MIT — see [LICENSE](LICENSE).
