# Public source release status

This branch contains the first reviewed code subset from Lydia's private operational repository.

## Included

The first release intentionally starts with portable modules that do not require private host addressing or trusted management paths:

- conversational intent helpers;
- bounded tool-free conversation handling;
- portal bug-report persistence and redaction;
- isolated capability-test reporting;
- Voice V2 runtime/arbitration primitives;
- Voice V2 transport/audio/session interfaces.

## Not included yet

The following remain private until their machine-specific assumptions are extracted into configuration and their content passes a public-release audit:

- the main `lydia.py` controller;
- Adam/Hermes transport and worker execution internals;
- infrastructure planner/controller modules;
- PowerMox/Otho/sandbox deployment helpers;
- worker registry/watchdog modules with private runtime paths;
- private handoff and acceptance documents;
- tests containing real lab addresses or environment-specific fixtures.

This is not an attempt to hide architecture. It is a staged publication process intended to keep the public tree useful and reproducible without exposing private infrastructure.

## Publication rule

A private module is copied public only after review for:

- embedded addresses and hostnames;
- user-specific paths;
- credentials or secret locations;
- personal account data;
- private device identifiers;
- runtime state and job data;
- environment-specific assumptions that should become configuration.

The private repository remains the authoritative operational source while this public tree is generalized.
