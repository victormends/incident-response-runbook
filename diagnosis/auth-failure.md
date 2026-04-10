# Authentication Failure

**Symptom:** Clients can reach the PostgreSQL port but cannot authenticate. Error messages include:

- `FATAL: password authentication failed for user "postgres"`
- `FATAL: pg_hba.conf rejects connection for host "x.x.x.x", user "postgres", database "mydb"`
- `FATAL: SCRAM authentication requires libpq version 10 or above`
- `error: SASL authentication failed` (from application drivers)
- `fe_sendauth: no password supplied`
- Connection appears to hang briefly then drops without an error (common with `peer` or `ident` auth mismatch)

**Confirmation query — check what pg_hba.conf is enforcing:**

```sql
-- Returns the current authentication rules being applied.
-- Compare the auth_method column against what your clients are configured to use.
SELECT type, database, user_name, address, auth_method
FROM pg_hba_file_rules
ORDER BY line_number;
```

If `pg_hba_file_rules` is not available (PostgreSQL < 10), check the file directly:

```bash
# Linux — find and display pg_hba.conf
psql -U postgres -tAc "SHOW hba_file"
cat $(psql -U postgres -tAc "SHOW hba_file")
```

```powershell
# Windows
$hbaFile = psql -U postgres -tAc "SHOW hba_file"
Get-Content $hbaFile
```

---

## The SCRAM-SHA-256 / MD5 Mismatch (Most Common Fleet Incident)

This is the single most common authentication incident in PostgreSQL environments that have upgraded from PG 13 or earlier to PG 14+. PostgreSQL 14 changed the default `password_encryption` from `md5` to `scram-sha-256`. Existing passwords stored as MD5 hashes stop working when `pg_hba.conf` enforces `scram-sha-256`, because the stored hash is in the wrong format — the server cannot verify it.

**Confirm the mismatch:**

```sql
-- Check which encryption method the server is configured to use for new passwords.
SHOW password_encryption;

-- Check what hash format each user's password is actually stored in.
-- 'md5' prefix means MD5 hash. 'SCRAM-SHA-256$...' means SCRAM hash.
-- A user with an MD5 hash cannot authenticate when pg_hba.conf enforces scram-sha-256.
SELECT usename,
       CASE
         WHEN passwd LIKE 'SCRAM-SHA-256$%' THEN 'scram-sha-256'
         WHEN passwd LIKE 'md5%'            THEN 'md5'
         ELSE 'unknown or empty'
       END AS stored_format
FROM pg_shadow
ORDER BY usename;
```

**Reading the output:**

If `pg_hba.conf` has `scram-sha-256` as the auth method but a user's `stored_format` is `md5`, that user cannot log in. The fix is to reset the password (which re-hashes it in the current `password_encryption` format).

**Fix — reset the password to re-hash in SCRAM format:**

```sql
-- This re-hashes the password using whatever password_encryption is currently set to.
-- Replace 'app_user' and 'the_password' with the actual values.
ALTER USER app_user WITH PASSWORD 'the_password';

-- Confirm the hash is now in SCRAM format:
SELECT usename, LEFT(passwd, 20) AS hash_prefix FROM pg_shadow WHERE usename = 'app_user';
-- Expected: 'SCRAM-SHA-256$4096:'
```

**If you cannot change the password (legacy system, password not known):**

Bridge solution — allow MD5 for specific users or IPs while enforcing SCRAM elsewhere. Edit `pg_hba.conf`:

```
# pg_hba.conf — bridge rule for legacy client
# More specific rules must come BEFORE the general scram-sha-256 rule
host    mydb    legacy_app_user    192.168.1.45/32    md5
host    all     all                0.0.0.0/0          scram-sha-256
```

After editing:

```sql
SELECT pg_reload_conf();
```

Then verify the reload took effect:

```sql
SELECT type, database, user_name, address, auth_method
FROM pg_hba_file_rules
ORDER BY line_number;
```

> [!WARNING]
> MD5 authentication is cryptographically weak. The bridge rule is a temporary measure. Schedule a proper password rotation and migration to SCRAM within your next maintenance window.

---

## Step 2 — pg_hba.conf Rule Order Problems

`pg_hba.conf` is evaluated top-to-bottom. The first matching rule wins. A broad rule above a specific rule silently overrides it.

**Common misconfiguration:**

```
# WRONG — the broad 'trust' rule matches before the specific 'scram' rule
host    all    all    0.0.0.0/0    trust       ← matches first, bypasses auth entirely
host    all    all    10.0.0.0/8   scram-sha-256
```

**Correct:**

```
# RIGHT — specific rules first, broad rules last
host    all    all    127.0.0.1/32    scram-sha-256
host    all    all    10.0.0.0/8      scram-sha-256
host    all    all    0.0.0.0/0       reject       ← reject unknown sources
```

**Check for overly permissive rules:**

```sql
-- Flag any 'trust' rules that apply to non-loopback addresses.
-- 'trust' means no password required — dangerous on networked interfaces.
SELECT line_number, type, database, user_name, address, auth_method
FROM pg_hba_file_rules
WHERE auth_method = 'trust'
  AND address NOT IN ('127.0.0.1/32', '::1/128', '')
ORDER BY line_number;
```

---

## Step 3 — Peer / Ident Auth Mismatch (Linux)

On Linux, the default `pg_hba.conf` uses `peer` auth for local connections. `peer` means PostgreSQL checks that the OS username matches the PostgreSQL username. If your application connects as `postgres` but runs as OS user `app`, authentication fails silently — the connection drops with no useful error.

**Symptom:** `psql -U postgres` works from the postgres OS user, fails from any other OS user. Application logs show connection refused or authentication failure with no further detail.

**Diagnosis:**

```bash
# What OS user is the application running as?
ps aux | grep <your_app_process>

# What does pg_hba.conf say for local connections?
grep -E "^local" $(psql -U postgres -tAc "SHOW hba_file")
```

**Fix — change local connections to `scram-sha-256` (recommended):**

```
# pg_hba.conf
# Before (peer — requires OS username = PG username):
local   all    all    peer

# After (scram — uses PostgreSQL password, works from any OS user):
local   all    all    scram-sha-256
```

After editing, reload:

```sql
SELECT pg_reload_conf();
```

---

## Step 4 — TLS / SSL Authentication Failures

**Symptom:** `FATAL: no pg_hba.conf entry for host "x.x.x.x", user "y", database "z", SSL on` — the client is connecting with SSL but the pg_hba rule only matches non-SSL connections, or vice versa.

**Check SSL configuration:**

```sql
SHOW ssl;                    -- is SSL enabled on the server?
SHOW ssl_cert_file;          -- server certificate path
SHOW ssl_key_file;           -- server key path
```

**Check SSL status of active connections:**

```sql
-- Returns SSL state per active connection.
-- ssl = true means the connection is encrypted.
SELECT pid, usename, application_name, client_addr, ssl, version
FROM pg_stat_ssl
JOIN pg_stat_activity USING (pid)
WHERE client_addr IS NOT NULL;
```

**pg_hba.conf SSL-aware rules:**

```
# 'hostssl' — matches only SSL connections
hostssl    all    all    0.0.0.0/0    scram-sha-256

# 'hostnossl' — matches only non-SSL connections
hostnossl  all    all    127.0.0.1/32    scram-sha-256

# 'host' — matches both SSL and non-SSL
host       all    all    10.0.0.0/8      scram-sha-256
```

> [!NOTE]
> On Windows, legacy applications sometimes force TLS 1.0 via registry keys, causing SSL negotiation to fail silently. If SSL connections fail only from specific application hosts on Windows, check: `HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.0\Client` for `DisabledByDefault = 0`. This is a registry override by a legacy application, not a PostgreSQL configuration issue.

---

## Preventive Measures

**Audit password hash formats before upgrading PostgreSQL:**

```sql
-- Run this BEFORE upgrading from PG 13 to PG 14+.
-- Any user with 'md5' format will break after the upgrade if pg_hba.conf enforces scram-sha-256.
SELECT usename,
       CASE
         WHEN passwd LIKE 'SCRAM-SHA-256$%' THEN 'scram-sha-256 — OK'
         WHEN passwd LIKE 'md5%'            THEN 'md5 — WILL BREAK after upgrade'
         ELSE 'no password set'
       END AS migration_status
FROM pg_shadow
ORDER BY usename;
```

**Never use `trust` in `pg_hba.conf` on networked interfaces.** Trust means any connection claiming to be that user is accepted without a password. This is safe only for loopback connections and only in environments where OS-level access is itself secured.

---

## Cross-Reference

- Triage entry point: [`triage/flowchart.md`](../triage/flowchart.md)
- If auth failure is blocking a fiscal process during business hours — escalate immediately: [`escalation/protocol.md`](../escalation/protocol.md)
- Severity classification: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
