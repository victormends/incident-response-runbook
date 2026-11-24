# Runbook: Linux systemd Boot Race and Silent Timer Failures

> [!IMPORTANT]
> **Severity: P2.** Service fails immediately after a VM reboot (before networking or mounts are ready) or scheduled jobs stop running silently with no alert emitted.
> **Target triage time: 5 minutes.**
> **Prerequisites:** SSH/SSM access to the Linux host, `sudo` privileges for `systemctl` and `journalctl`.

A host reboot returns SSH access normally, yet a managed daemon is in `failed` state with zero upstream reachability at timestamp `boot+1s`, or a scheduled `systemd` timer stopped producing fresh data hours ago because failures went unreported.

---

## Pre-Triage Checklist

- [ ] Check failed units and recent boots before restarting the unit (restarting manually often hides the boot race until the next kernel patch).
- [ ] Inspect boot ordering and exact failure exit status.
- [ ] Verify downstream target endpoints and disk mounts are actually ready.

**Inspect failed units, boot timeline, and failure journal:**

```bash
systemctl --failed
systemctl status <unit>.service --no-pager
journalctl -u <unit>.service -b -n 80 --no-pager
systemd-analyze critical-chain <unit>.service
```

**Verify timer history and next scheduled trigger:**

```bash
systemctl list-timers --all --no-pager
```

---

## Common Root Causes

- **`After=network.target` instead of `network-online.target`:** On Linux, `network.target` only means the network stack started initializing; DNS and DHCP/cloud routes may still be down when the unit launches.
- **Missing or weak restart policy:** Unit fails once during boot transient DNS outage and stays `failed` because `Restart=on-failure` is unset or `StartLimitIntervalSec` trips too early.
- **Silent unit or timer failures:** `OnFailure=` hook is missing and no external deadman switch alerts when a scheduled run misses two consecutive intervals.

---

## Step 1 — Immediate Mitigation

1. **Check unit state and underlying resource health:**
   - Verify DNS resolution, target DB/API connectivity, and disk mounts (`df -h`, `findmnt`) before restarting.
2. **Start the failed unit and verify steady state:**
   ```bash
   sudo systemctl start <unit>.service
   systemctl is-active <unit>.service
   journalctl -u <unit>.service -n 30 --no-pager
   ```
3. **If a timer is stuck because the previous run hung indefinitely:**
   - Inspect `ExecMainStartTimestamp` and child PIDs (`systemctl status <unit>.service`); add `TimeoutStartSec=` before re-enabling so a dead HTTP client cannot stall future ticks forever.

---

## Step 2 — Durable Fix (Unit Drop-In & Failure Alerting)

Create an explicit drop-in override rather than editing vendor files directly:

```bash
sudo systemctl edit <unit>.service
```

Recommended hardening for network-dependent services:

```ini
[Unit]
Wants=network-online.target
After=network-online.target
OnFailure=ops-notify-failure@%n.service

[Service]
Restart=on-failure
RestartSec=10s
StartLimitIntervalSec=300
StartLimitBurst=5
TimeoutStartSec=90s
```

Verify that the distribution's wait-online service is enabled so `network-online.target` actually blocks until an interface has routable connectivity:

```bash
systemctl is-enabled systemd-networkd-wait-online.service NetworkManager-wait-online.service 2>/dev/null || true
```

For scheduled ETL/sync timers, do not rely solely on `OnFailure=` (which cannot fire if cron/timer triggers stop firing or if the host itself freezes): pair the job with an external deadman watchdog alerting when no heartbeat or fresh artifact arrives within `2 x expected_interval`.

---

## Verification

- [ ] Reload units cleanly and inspect effective configuration:
  `sudo systemctl daemon-reload && systemctl cat <unit>.service`
- [ ] Verify simulated failure triggers `OnFailure=` notification handler without exposing credentials in `journalctl` or drop-ins (load webhook tokens via `EnvironmentFile=` with `0600` root permissions or cloud secret manager / SSM at runtime).
- [ ] Validate reboot resilience in staging or during scheduled maintenance window (`systemctl --failed` stays empty).
