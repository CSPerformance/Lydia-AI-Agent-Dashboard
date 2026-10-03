# Lydia AI Agent Dashboard

> Experimental, heavily AI-assisted (“vibe coded”) homelab project under active development.

Lydia is a local-first AI operations assistant and dashboard. The project explores how a conversational assistant can coordinate local models, specialist workers, infrastructure tools, voice I/O, web research, and verification without treating model output as proof that work actually happened.

This repository is the **public-facing documentation and dashboard project**. Private operational source, credentials, network topology, runtime state, and machine-specific configuration are intentionally kept out of the public repository.

## What Lydia is trying to do

Lydia is designed to:

- converse through text and voice;
- use local GPU-backed models for everyday work;
- route harder jobs to specialist workers;
- inspect and operate authorized systems through controller-owned tools;
- research unfamiliar problems;
- recover from ordinary failures;
- verify results independently before claiming completion;
- keep useful non-secret operational knowledge;
- expose worker health, progress, jobs, and telemetry through a dashboard.

## High-level architecture

```text
Human operator
      |
    Lydia
 local controller
      |
      +----------------+----------------+----------------+
      |                |                |                |
 local model        primary worker   auxiliary worker  code/review worker
      |                |                |                |
      +----------------+----------------+----------------+
                       |
                controller verification
                       |
                  final result
```

The worker identities currently used in the project include **Adam** (primary worker), **Barbara** (auxiliary worker), and **Otho** (maintenance/scheduling helper). OpenCode-based workers are also used for bounded repository/code review tasks.

## Design principles

1. **Lydia remains the controller.** Workers are subordinate tools/collaborators.
2. **Model claims are not execution evidence.** Real tools and independent checks matter.
3. **Local-first when practical.** Private/local work should stay local when possible.
4. **Routing should be explicit.** The system is evolving toward a single structured request/route decision layer.
5. **Failures should trigger recovery, not immediate surrender.**
6. **Private state stays private.** Credentials, internal addresses, logs, voice profiles, runtime databases, and machine-specific configuration do not belong in this repository.

## Current areas of work

- controller and routing reliability;
- worker delegation and health tracking;
- evidence-backed task completion;
- Voice V2 and interruption handling;
- OpenCode integration for repository/code work;
- local weather and dashboard integrations;
- recovery, watchdog, and self-repair workflows;
- reducing monolithic routing logic and improving modularity.

## Public documentation

- [Architecture](docs/architecture.md)
- [Security and publication boundary](docs/security.md)
- [Current public status](docs/status.md)
- [Roadmap](docs/roadmap.md)

## What is intentionally not published

This repository does **not** publish private addresses, private DNS names, SSH targets, credentials, account data, runtime databases, job payloads, private camera/device addressing, voice recordings, speaker profiles, internal topology handoffs, or the authoritative private operational repository.

## Project status

Lydia is a working experimental system, but it is still in active hardening and is not a turnkey production product. Features that pass unit tests may still require live acceptance on the actual hardware or service involved.

## License

See [LICENSE](LICENSE).
