# Triage Flowchart

Start here when an incident is reported. Follow the decision nodes in sequence. Each leaf node points to a diagnosis checklist or runbook. You should reach an initial hypothesis within 5 minutes.

During a P1, log every decision node you traverse with a timestamp in the incident ticket. This feeds directly into the post-mortem timeline.

> [!NOTE]
> Every decision branch you follow during a P1 must be recorded with a timestamp. "14:38 — confirmed process running, checked connections" is enough. This is not bureaucracy — it's the raw material for the post-mortem timeline.

---

## Flowchart

```mermaid
flowchart TD
    A([Incident reported]) --> B{Is the PostgreSQL\nprocess running?}

    B -- "Check: pg_ctl status\nor Windows Services" --> C{Process running?}

    C -- No --> D[Check last 50 lines\nof PostgreSQL log]
    C -- Yes --> E{Can clients connect?\npsql -c 'SELECT 1'}

    D --> F{Log contains\n'no space left on device'\nor 'could not open file'?}
    F -- Yes --> G[[Runbook: pg-wal-zero-bytes-free\nsee runbooks/pg-wal-zero-bytes-free.md]]:::critical
    F -- No --> H[General crash recovery:\ncheck PostgreSQL log for FATAL/PANIC\ncheck Windows Event Log]

    E -- No --> I{Connection refused\nor authentication error?}
    E -- Yes --> J{Are queries completing\nin reasonable time?}

    I -- "Connection refused" --> K{Check max_connections:\nSELECT count\nFROM pg_stat_activity}
    I -- "Auth error" --> L[Check pg_hba.conf:\nauth method mismatch\nSCRAM vs MD5 issue\nsee escalation/protocol.md]

    K --> M{count near\nmax_connections?}
    M -- Yes --> N[[Checklist: Connection Exhaustion\nsee diagnosis/connection-exhaustion.md]]:::checklist
    M -- No --> O[Check listening socket\nnetstat -ano port 5432\ncheck pg_hba.conf\ncheck TLS registry]

    J -- No --> P{Queries hanging\nor returning errors?}
    J -- Yes --> Q{Check replication:\npg_stat_replication\npg_replication_slots}

    P -- Hanging --> R[[Checklist: Lock Contention\nsee diagnosis/lock-contention.md]]:::checklist
    P -- Errors --> S{Errors mention\ncorruption or\nchecksum failure?}

    S -- Yes --> T[[Checklist: Corruption\nsee diagnosis/corruption.md]]:::critical
    S -- No --> U[Check pg_stat_activity\nfor long-running queries\nor idle-in-transaction]

    Q --> V{Replication lag\nor inactive slot\nwith large retained WAL?}
    V -- Yes --> W[[Checklist: Replication Lag\nsee diagnosis/replication-lag.md]]:::checklist
    V -- No --> X[Database healthy.\nVerify client-side issue:\nconnection string, credentials,\napplication config]

    classDef critical fill:#c0392b,color:#fff,stroke:#922b21
    classDef checklist fill:#2471a3,color:#fff,stroke:#1a5276
```

---

## Flowchart Legend

| Symbol | Meaning |
|---|---|
| Rounded rectangle | Start / End point |
| Diamond `{ }` | Decision node — requires a check |
| Rectangle | Action to perform |
| `[[ ]]` Red | Runbook or checklist — critical path |
| `[[ ]]` Blue | Diagnosis checklist |

---

## First checks reference

When you reach a decision node, these are the exact commands to run:

**Is the process running?**
```powershell
# Windows — check service state
Get-Service -Name "postgresql*" | Select-Object Name, Status

# Or via pg_ctl (replace path with your installation)
& "C:\Program Files\PostgreSQL\15\bin\pg_ctl.exe" status -D "C:\Program Files\PostgreSQL\15\data"
```

**Can clients connect?**
```bash
psql -h localhost -p 5432 -U postgres -c "SELECT 1"
```

**Connection count vs limit:**
```sql
-- Returns: current connections / max_connections setting
SELECT count(*) AS current_connections,
       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections
FROM pg_stat_activity;
```

**Check PostgreSQL log (last 50 lines):**
```powershell
# Replace with your actual log path
Get-Content "C:\Program Files\PostgreSQL\15\data\log\postgresql-*.log" -Tail 50
```

---

## Cross-Reference

- Severity definitions: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
- If escalation is needed before you reach a leaf node: [`escalation/protocol.md`](../escalation/protocol.md)
