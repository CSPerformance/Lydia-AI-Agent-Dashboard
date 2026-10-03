# Public project status

Status: active development.

## Working themes

The project currently has functioning or actively tested implementations for local conversational inference, a web dashboard/chat surface, primary and auxiliary worker delegation, worker status and watchdog logic, controller-side verification, voice capture/recognition/synthesis/interruption work, bounded code/repository review through OpenCode, research and recovery workflows, local weather integration, and regression tests across routing, workers, voice, research, and controller behavior.

## Reliability work

Recent engineering has focused on preventing failed worker/tool calls from being counted as success, stopping stale asynchronous responses from overwriting newer replies, canceling clearly runaway autonomous jobs, improving worker lifecycle visibility, preserving the original user goal through recovery loops, making explicit target selection outrank accidental keyword matches in pasted content, and requiring independent verification after mutations.

## Still experimental

Universal hands-free voice reliability, generalized self-repair, fully unified routing across text and voice, automatic multi-worker arbitration, unattended recovery from every infrastructure failure, portable installation on arbitrary hardware, and public release of the private operational source remain active engineering work.

A green test suite does not by itself prove that a live remote worker, GPU, audio route, or external service is currently healthy.
