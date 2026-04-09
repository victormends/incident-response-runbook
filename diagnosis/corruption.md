# Data Corruption

> [!WARNING]
> If you suspect data corruption, do not attempt to modify any data before completing this checklist. Take a filesystem snapshot or database backup immediately if one is not already running. Every action you take from this point forward should be logged with a timestamp.

This document covers initial triage only. It does not attempt to guide full corruption recovery — that requires a senior engineer and a case-by-case assessment. This checklist ends with a firm escalation.

---

## Symptom Signatures

Look for these patterns in the PostgreSQL log:

```
ERROR:  invalid page in block 42 of relation base/16384/2619
ERROR:  could not read block 1024 in file "base/16384/16385"
WARNING:  page verification failed, calculated checksum 12345 but expected 54321
PANIC:  could not write to file "pg_wal/000000010000000000000001": No space left on device
ERROR:  invalid memory alloc request size 18446744073709551615
```

Any of these patterns in the log is a P1. Do not proceed with normal operations. Stop here and follow this checklist.

---

## Checklist

**Before running any query, note the current timestamp.** Your post-mortem timeline starts now.

- [ ] Confirm no writes are actively occurring on the suspect tables. If possible, put the application in read-only mode.
- [ ] Take a filesystem snapshot of the data directory if your infrastructure supports it. This preserves the state for forensic analysis.
- [ ] Check if a recent backup exists and when it was taken. You need to know your recovery point before anything else.

---

## Verification Queries

Run these in order. Stop at the first error — do not continue to the next query.

**1. Catalog integrity check:**

```sql
-- A simple check that the system catalogs are readable.
-- If this fails, the corruption is in core system tables — this is severe.
-- Expected: a list of table names. Any error here is critical.
SELECT schemaname, tablename
FROM pg_catalog.pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
LIMIT 10;
```

**2. Index integrity check (requires btree indexes only):**

```sql
-- Uses the amcheck extension to verify btree index structure.
-- Returns nothing on success. Any row returned indicates index corruption.
-- Only works on btree indexes — will error on other index types (hash, gin, gist).
-- If the amcheck extension is not installed, skip this query.
SELECT bt_index_check(c.oid::regclass)
FROM pg_class c
JOIN pg_am am ON am.oid = c.relam
WHERE am.amname = 'btree'
  AND c.relkind = 'i'
  AND c.relnamespace NOT IN (
      SELECT oid FROM pg_namespace WHERE nspname IN ('pg_catalog', 'information_schema')
  );
```

**3. Table-level verification via VACUUM:**

```sql
-- Running VACUUM VERBOSE on a suspect table will surface storage-level errors.
-- Replace 'your_table_name' with the table mentioned in the error log.
-- Do NOT run this on all tables — only the specific one from the error.
VACUUM VERBOSE your_table_name;
```

Expected output on a healthy table: `INFO: vacuuming "public.your_table_name"` followed by statistics. An error during VACUUM confirms the problem.

**4. Check data directory for checksum errors (PostgreSQL 12+):**

```sql
-- If data checksums are enabled, this shows if any blocks have failed verification.
SHOW data_checksums;
```

If checksums are enabled and you're seeing checksum failures in the log, the physical blocks on disk are corrupt. This is a hardware or filesystem problem, not a PostgreSQL bug.

---

## Escalation Decision

If any query above returns an error, or if the log contains any of the symptom signatures listed above:

1. **Stop all write operations** on the affected database if possible.
2. **Do not attempt recovery steps from memory.** Recovery from corruption requires knowing the exact type: is it a WAL segment, a heap file, an index, a system catalog?
3. **Escalate immediately** — see [`escalation/protocol.md`](../escalation/protocol.md).
4. **Preserve all logs** — copy the PostgreSQL log files to a safe location before they rotate.
5. **Open the post-mortem** — see [`post-mortem/template.md`](../post-mortem/template.md) and begin filling the timeline.

This is a P1. If a recent backup exists, recovery from backup is almost always faster and safer than attempting in-place corruption repair.

---

## Cross-Reference

- Escalation procedure: [`escalation/protocol.md`](../escalation/protocol.md)
- Post-mortem template: [`post-mortem/template.md`](../post-mortem/template.md)
- Severity classification: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
