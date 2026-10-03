# Public architecture overview

This document describes roles and control flow without exposing the private lab topology.

## Controller

Lydia is the primary controller and conversation surface. The controller owns request classification and routing, local tool invocation, worker delegation, authorization boundaries, evidence requirements, verification, and final user-facing synthesis.

The intended lifecycle is:

```text
request
 -> classify
 -> inspect
 -> plan
 -> act or delegate
 -> verify independently
 -> report
 -> retain useful non-secret lessons
```

A worker response cannot mark its own work complete.

## Local inference

The main workstation uses a local GPU for fast conversational and technical workloads. GPU-first operation is preferred for workloads intended to run locally. Exact model choices may change as better candidates are tested; worker identity remains separate from model identity.

## Workers

**Adam** is the primary delegated worker for heavier reasoning, infrastructure investigation, coding/analysis, and longer-running work.

**Barbara** is the auxiliary/overflow worker for parallel investigation, secondary opinions, and smaller delegated workloads.

**Otho** is a maintenance/scheduling helper intended to improve continuity for operations and recurring coordination tasks.

**OpenCode** is used as a bounded code/repository specialist. It can review source and propose changes, but Lydia retains controller authority and is expected to verify relevant findings.

## Evidence model

Lydia distinguishes proposal, execution evidence, independent verification, and durable registration of reusable results. Those distinctions are core reliability requirements.

## Dashboard

The dashboard is intended to expose worker identity and availability, current task/phase, progress and heartbeat state, GPU/worker telemetry, jobs, lifecycle information, and voice/collaboration controls.

Exact private endpoints and machine addresses are intentionally omitted.
