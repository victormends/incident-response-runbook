# Security and Operational Safety

This repository contains public incident-response templates and PostgreSQL runbooks. It does not provide emergency support, production authorization, or environment-specific recovery guarantees.

## Supported Use

Use these materials to:

- structure severity classification and triage;
- prepare PostgreSQL diagnosis checklists;
- improve incident communication and escalation;
- run post-mortems with clearer corrective actions.

Before using any command in production, adapt it to your operating system, PostgreSQL version, service manager, backup policy, and approval process.

## Safety Boundaries

Do not treat this repository as permission to perform destructive recovery work. Actions involving WAL files, service restarts, disk cleanup, failover, backup restoration, or client-facing commitments should be approved by the incident owner or incident commander.

The examples are intentionally generic and may omit details that matter in regulated or high-availability environments.

## Reporting Issues

For public issues, avoid posting:

- real client names;
- hostnames, IP addresses, or internal URLs;
- credentials, tokens, connection strings, or private keys;
- logs containing personal, financial, or regulated data;
- unpublished incident details.

Use sanitized reproduction notes and synthetic examples instead.

## Non-Goals

This repository is not:

- a substitute for vendor support;
- a complete disaster-recovery plan;
- a compliance framework;
- a replacement for tested backups and restore drills;
- legal, contractual, or regulatory advice.
