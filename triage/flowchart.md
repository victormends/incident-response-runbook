# Triage Flowchart

Start here when an incident is reported. Follow the decision nodes in sequence. Each leaf node points to a diagnosis checklist or runbook. You should reach an initial hypothesis within 5 minutes.

> [!NOTE]
> During a P1, log every decision node you traverse with a timestamp in the incident ticket. "14:38 — confirmed process running, checked connections" is enough. This feeds directly into the post-mortem timeline.

---

## Flowchart

```mermaid
flowchart TD
    A([Incident reported]) --> B{Is the PostgreSQL\nprocess running?}

    B --> C[Check: pg_ctl status\nor systemctl / Windows Services]
    C --> D{Process running?}

    D -- No --> E[Check last 50 lines\nof PostgreSQL log]
    D -- Yes --> F{Can clients connect?\nRun: psql -c 'SELECT 1'}

    E --> G{Log contains\n'no space left on device'\nor 'could not open file'?}
    G -- Yes --> H[[WAL runbook\nrunbooks/pg-wal-zero-bytes-free.md]]:::critical
    G -- No --> I[Check log for FATAL or PANIC\nCheck OS event log\nGeneral crash recovery path]

    F -- No --> J{Connection refused\nor auth error?}
    F -- Yes --> K{Queries completing\nin reasonable time?}

    J -- Connection refused --> L{Count near\nmax_connections?}
    J -- Auth error --> M[[Auth failure checklist\ndiagnosis/auth-failure.md]]:::checklist

    L -- Yes --> N[[Connection exhaustion\ndiagnosis/connection-exhaustion.md]]:::checklist
    L -- No --> O[Check listening socket\nnetstat / ss -tlnp\nCheck pg_hba.conf\nCheck TLS config]

    K -- No --> P{Queries hanging\nor returning errors?}
    K -- Yes --> Q[Check replication\npg_stat_replication\npg_replication_slots]

    P -- Hanging --> R[[Lock contention\ndiagnosis/lock-contention.md]]:::checklist
    P -- Errors --> S{Errors mention\ncorruption or\nchecksum failure?}

    S -- Yes --> T[[Corruption triage\ndiagnosis/corruption.md]]:::critical
    S -- No --> U[Check pg_stat_activity\nfor long-running queries\nor idle-in-transaction]

    Q --> V{Replication lag or\ninactive slot with\nlarge retained WAL?}
    V -- Yes --> W[[Replication lag\ndiagnosis/replication-lag.md]]:::checklist
    V -- No --> X([Database healthy.\nVerify client-side:\nconnection string,\napplication config])

    classDef critical fill:#c0392b,color:#fff,stroke:#922b21
    classDef checklist fill:#1a5276,color:#fff,stroke:#154360
```

---

## Flowchart Legend

| Symbol | Meaning |
|---|---|
| Rounded rectangle | Start / End |
| Diamond | Decision — requires a check |
| Rectangle | Action to perform |
| `[[ ]]` Red | Critical path — runbook or corruption |
| `[[ ]]` Blue | Diagnosis checklist |

---

## First Checks Reference

**Is the process running?**

```bash
# Linux — systemd
systemctl status postgresql
systemctl status postgresql@15-main   # Debian/Ubuntu naming

# Linux — pg_ctl
pg_ctl status -D /var/lib/postgresql/15/main

# macOS — Homebrew
brew services info postgresql@15
```

```powershell
# Windows — Services
Get-Service -Name "postgresql*" | Select-Object Name, Status

# Windows — pg_ctl
& "C:\Program Files\PostgreSQL\15\bin\pg_ctl.exe" status -D "C:\Program Files\PostgreSQL\15\data"
```

**Can clients connect?**

```bash
psql -h localhost -p 5432 -U postgres -c "SELECT 1"
```

**Connection count vs limit:**

```sql
-- Returns current connections / max_connections.
-- If pct_used is above 90%, connection exhaustion is the likely cause.
SELECT count(*) AS current_connections,
       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections,
       round(100.0 * count(*) /
         (SELECT setting::int FROM pg_settings WHERE name = 'max_connections'), 1) AS pct_used
FROM pg_stat_activity;
```

**Check PostgreSQL log (last 50 lines):**

```bash
# Linux — typical log locations
tail -50 /var/log/postgresql/postgresql-15-main.log
journalctl -u postgresql --no-pager -n 50
```

```powershell
# Windows
Get-Content "C:\Program Files\PostgreSQL\15\data\log\postgresql-*.log" -Tail 50
```

---

## Cross-Reference

- Severity definitions: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
- If escalation is needed before you reach a leaf node: [`escalation/protocol.md`](../escalation/protocol.md)
