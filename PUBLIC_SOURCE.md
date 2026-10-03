# Public source release status

This branch contains the first reviewed source release from Lydia's private operational repository.

## Included in this release

The current public-source branch includes:

- conversational intent and follow-up helpers;
- bounded tool-free conversation handling;
- portal bug-report persistence and redaction;
- isolated capability-test reporting;
- Voice V2 runtime, audio contracts, transport, and session orchestration;
- agent support and scoped audio self-repair helpers;
- auxiliary-worker, candidate-planner, and correction-memory modules;
- host-observation and operator acceptance/model helpers;
- planner capacity/core modules;
- project coordinator and dispatcher modules;
- peer recovery and read-only worker helpers;
- research self-repair and web research modules;
- team design, memory, research, and review modules;
- Tempest weather provider and interactive setup utility;
- self-contained public regression tests for the published helpers and Voice V2 pieces.

## Portability changes

Public-facing code is published only after review for environment-specific data.

The Tempest provider's default configuration path was changed from a private deployment path to an environment-configurable/public-safe path. The private repository remains the authoritative source for the live deployment.

## Not included yet

The following remain private until their machine-specific assumptions are extracted into configuration and their content passes a public-release audit:

- the main `lydia.py` controller;
- Adam/Hermes transport and worker execution internals;
- the full infrastructure runtime/planner modules;
- PowerMox/Otho/sandbox deployment helpers;
- worker registry/watchdog modules whose live deployment paths still need a clean publication path;
- private handoff and acceptance documents;
- tests containing real lab addresses, personal account details, or environment-specific fixtures.

The private portability branch already makes the worker status/watchdog state directory configurable without changing the live default. Those changes can be integrated separately before a later public release.

## Publication rule

A private module is copied public only after review for:

- embedded addresses and hostnames;
- user-specific paths;
- credentials or secret locations;
- personal account data;
- private device identifiers;
- runtime state and job data;
- environment-specific assumptions that should become configuration.

The private repository remains the authoritative operational source while the public tree is generalized.
