# Lydia-AI-Agent-Dashboard
###DISCLAIMER - THIS HAS BEEN ALL VIBE CODED

POWERLYDIA / LYDIA HOMELAB
COMPREHENSIVE ENGINEERING DOCUMENT OUTLINE
Status date: 2026-10-03
Owner: Chris
Primary objective: Build a resilient, hands-free AI operations environment in which Lydia can converse, inspect systems, plan work, delegate to specialized workers, execute authorized technical tasks, verify results, recover from ordinary failures, and retain durable operational knowledge.

===============================================================================
1. EXECUTIVE SUMMARY
===============================================================================

The PowerLydia lab is a multi-node AI and infrastructure automation environment centered on Lydia, a local workstation assistant running on Linux Mint with an Intel Arc A770 16 GB GPU. Lydia is intended to function as the primary operator and coordinator for the lab rather than as a simple chat interface. Her responsibilities include natural-language interaction, local model inference, technical planning, infrastructure inspection, delegated execution, web research when appropriate, worker supervision, evidence-based verification, voice interaction, and self-repair within defined safety boundaries.

The current architecture combines several distinct compute and control roles. PowerLydia is the interactive control plane and local AI workstation. PowerMox is a Lenovo System x3650 M5 running Proxmox VE and hosts GPU-backed worker systems. Adam is the primary delegated AI worker associated with the TITAN Xp environment on VM202. Barbara is the auxiliary GTX 1070 worker. Otho is a smaller Debian node intended to act as a scheduler, maintenance coordinator, and persistence helper. Additional infrastructure includes Tailscale for private remote access, a web-based Lydia portal, NUT-based UPS monitoring, hourly/weekly backup services, Jellyfin-related migration work, Baseus camera integration work, Tempest weather-station plans, and several voice/audio services.

The design philosophy is increasingly moving toward a controller/worker architecture. Lydia remains the owner of each task. Workers such as Adam, Barbara, and OpenCode may provide execution or second-opinion analysis, but Lydia is expected to independently evaluate evidence and remain responsible for final conclusions. This distinction has become especially important during recent OpenCode integration work.

The local AI stack is built around Ollama and GPU-first execution. PowerLydia's Intel Arc A770 is the preferred local inference device, with CPU fallback intentionally discouraged for normal model workloads. Recent Lydia runtime configuration has used qwen3.5:4b for conversational work, with larger Hermes/Qwen-family models available for fallback or specialist use. PowerMox provides NVIDIA-backed remote worker capacity, with Adam using the TITAN Xp and Barbara using the GTX 1070.

The portal is reachable locally on 127.0.0.1:8765 and remotely through Tailscale Serve. It now supports direct target selection for Lydia, Adam, Barbara, and OpenCode, plus an independent OpenCode Assist mode. Worker state, heartbeat, task lifecycle, and watchdog data are surfaced through shared worker-status infrastructure. Recent work has also added bounded autonomous-job cancellation for clearly runaway Lydia jobs.

A major current engineering theme is routing correctness. Lydia has accumulated multiple intent classifiers, fast paths, worker selectors, infrastructure gates, research gates, and autonomous-agent entry points. These are still largely implemented as ordered predicates and regex-based routing logic inside a very large lydia.py. Recent failures showed that quoted or pasted content can accidentally trigger an unintended route, even when the user's explicit instruction says to use OpenCode. This led to a verified routing-precedence fix: explicit OpenCode delegation now outranks the broader team-design classifier. Regression tests were added and the broader routing/team-design suite passes.

OpenCode integration has advanced significantly. OpenCode can now be selected directly or enabled as a second-opinion collaborator. The selected model is configurable, with opencode/space-bunny-free used in recent testing. Direct bounded repository reviews have succeeded. Failure classification was hardened so OpenCode timeouts can no longer be counted as successful evidence. OpenCode progress streaming, bounded review prompts, shared prompt construction, and post-review Lydia verification have been added or are being validated. However, long-running OpenCode requests still occasionally hit the 180-second timeout, and the most recent unified bounded-prompt/progress-throttling changes still require a complete live validation pass.

The lab's reliability work is substantial. Lydia's backup service has been hardened against tar's "file changed as we read it" behavior and validated under file mutation. Autonomous-job cancellation was implemented and successfully stopped a runaway planning loop. Worker watchdog behavior distinguishes current worker readiness from historical task failure. Stale-response suppression prevents older asynchronous work from overwriting newer interactive responses. Voice and web-chat routing have received multiple fixes for barge-in, response ownership, and remote access behavior.

The next major architecture step should be consolidation of routing into a structured request envelope and a single route-decision layer shared by webchat and voice. This would reduce duplicated decision logic, preserve explicit user target selection, record route reasons, and provide a durable basis for execution authority and evidence requirements. The lab is functional and increasingly resilient, but still in an active hardening phase rather than a finished production state.

===============================================================================
2. ENGINEERING GOALS AND OPERATING PRINCIPLES
===============================================================================

2.1 Primary goals
- Hands-free workstation assistant with natural voice and text interaction.
- Local-first AI inference on the Intel Arc A770 whenever practical.
- Ability to inspect, diagnose, configure, and repair routine technical issues.
- Delegation of suitable work to PowerMox workers.
- Evidence-based verification before claiming successful completion.
- Persistent operational learning and correction of bad assumptions.
- Remote access through Tailscale without exposing the control plane publicly.
- Clear visibility into worker activity, health, ownership, and progress.
- Ability to recover from ordinary planner, worker, or execution failures.
- Preserve existing system configuration and avoid destructive changes unless explicitly authorized.

2.2 Authority model
- Lydia is the primary controller and task owner.
- Adam and Barbara are subordinate execution/advisory workers.
- OpenCode is a specialist code/repository reviewer and may be used directly or through OpenCode Assist.
- Otho is intended as a scheduler/maintenance coordinator, not the primary decision-maker.
- Workers may provide evidence or advice but do not own final task completion.
- High-impact or security-reducing actions remain subject to explicit controls.
- Routine dependency installation/configuration is within Lydia's standing authority when necessary to complete an authorized task and when the change is not destructive.

2.3 Evidence doctrine
- A failed tool call is not completion evidence.
- Model claims are not automatically authoritative.
- Live machine state should be established using appropriate real-system tools.
- Local/private code questions should be grounded in local source.
- Public/current facts should use web research when actually required.
- For local OpenCode reviews, OpenCode findings should be independently checked by Lydia before final publication.

===============================================================================
3. PHYSICAL AND COMPUTE INVENTORY
===============================================================================

3.1 PowerLydia workstation
Role:
- Primary interactive control plane.
- Local conversation and planning.
- Web portal host.
- Voice capture/playback.
- Local AI inference.
- Worker orchestration.
- Shared status/watchdog controller.

Operating system:
- Linux Mint Cinnamon.

Primary GPU:
- Intel Arc A770 16 GB.
- Preferred device for local model workloads.
- GPU-first policy; normal local AI workloads should not silently fall back to CPU.

Storage:
- Samsung 970 EVO Plus 500 GB NVMe.
- Samsung 980 500 GB NVMe.
- External Toshiba "Storage" NTFS device used for backup.
- Backup mount point: /mnt/toshiba.

Audio:
- Dell WL3024 headset.
- Persistent Kokoro TTS and Whisper STT services.
- Browser/remote voice path remains an active integration area.

3.2 PowerMox
Role:
- Main virtualization and remote AI worker host.
- Heavy or long-running delegated workloads.
- GPU passthrough environment.

Hardware:
- Lenovo System x3650 M5.
- 2 x Intel Xeon E5-2630 v3.
- Approximately 125 GiB RAM.
- Proxmox VE 9.1.x.

GPUs:
- NVIDIA TITAN Xp 12 GB.
- NVIDIA GTX 1070 8 GB.
- Matrox G200eR2 BMC graphics.

Networking:
- Dual fiber NICs bridged through vmbr0.
- Catalyst 3650-24PS switching.
- STP backup blocking has been observed.
- Tailscale installed and used for private management access.

3.3 Adam / VM202
Role:
- Primary PowerMox AI worker.
- User-facing identity: Adam.
- Hermes remains a backend/legacy alias.

Hardware:
- VM202 "Titan-LLM-Text".
- TITAN Xp passthrough.

Known runtime:
- lydia-hermes-qwen35-4b:64k observed as an active backend during recent work.
- Hermes/Ollama-based worker stack.

3.4 Barbara / VM105
Role:
- Auxiliary/overflow AI worker.
- Intended for parallel subtasks and secondary opinions.

Hardware:
- VM105 "Yolo-Ai".
- GTX 1070 passthrough.

Runtime:
- Native Ollama tools.
- Worker readiness must be checked live before assignment.
- Tighter 8 GB VRAM capacity makes model-size selection important.

3.5 Otho
Role:
- Scheduler / maintenance / coordination node.
- Intended to "keep the team moving".

Hardware / OS:
- Riverbed appliance.
- Debian 13 (trixie).
- Intel Xeon, 4 cores / 4 threads.
- About 4 GB RAM.
- ext4 root on /dev/sdb2.

Access:
- SSH operational.
- Tailscale joined.
- User chris with sudo configured.
- Lydia SSH key access verified.

3.6 Other systems / targets
- Jellymox: intended destination for Jellyfin/data migration.
- Tiny11 VM102.
- OMV-Powermox VM108.
- PowerAlien: Alienware Linux workstation intended for trusted RustDesk-assisted work.
- Baseus S1UA00 camera at the PowerMox location.
- Tempest weather station integration requested.

===============================================================================
4. NETWORK AND REMOTE ACCESS ARCHITECTURE
===============================================================================

4.1 Tailscale
Purpose:
- Private management overlay.
- Remote portal access.
- Remote worker and node connectivity.
- Avoid direct public exposure of internal control services.

4.2 Lydia web portal
Backend:
- 127.0.0.1:8765.

Remote access:
- Tailscale Serve proxies the Lydia portal.
- An additional Tailscale-served endpoint has also been observed on port 9119.

Portal capabilities:
- Text chat.
- Target selector.
- Worker status indicators.
- Emergency stop.
- OpenCode model selector.
- OpenCode Assist toggle.
- Job/status display.
- Voice integration work in progress.

4.3 Remote helper access
- RustDesk is used/planned for trusted external helpers on PowerAlien.
- Helper workstation access should remain a distinct trust boundary from privileged Lydia credentials and services.

===============================================================================
5. LOCAL AI / MODEL STACK
===============================================================================

5.1 Ollama
- Installed on PowerLydia.
- Model directory: /mnt/lydia/ollama/models.
- GPU acceleration on Intel Arc A770 has been verified through Vulkan.
- Ollama version observed around 0.34.2 during recent work.

5.2 Conversation / planner models
Recent environment:
- LYDIA_CONVERSATION_MODEL=qwen3.5:4b
- Context approximately 16K for the primary conversation model.
- Fallback/specialist models include Hermes/Qwen-family models with larger context windows.
- qwen3:14b Q4_K_M was previously validated at 100% A770 GPU usage.
- `/set nothink` has been used for latency-oriented testing.

5.3 Model role separation
Recommended ongoing distinction:
- Conversation model: fast interaction and synthesis.
- Planner/reasoning model: complex autonomous tasks.
- Adam: remote specialist / delegated execution.
- Barbara: overflow/parallel specialist.
- OpenCode: repository/code review and software architecture assistance.
- Web research: external/current knowledge only when required.

===============================================================================
6. LYDIA CORE SOFTWARE ARCHITECTURE
===============================================================================

6.1 Repository
Primary repository:
- /mnt/lydia/agents/lydia

Primary application:
- /mnt/lydia/agents/lydia/lydia.py

Supporting modules include:
- worker_status.py
- worker_watchdog.py
- operator_runtime.py
- project_planner.py
- planner_capacity.py
- hermes_worker.py
- worker_dispatch.py
- tool_execution.py
- research_workflows.py
- web_research.py
- audio_self_repair.py
- voice_capture.py
- team_design.py
- peer_recovery.py
- project_coordinator.py
- project_dispatcher.py

6.2 Current architectural concern
- lydia.py has grown into a very large monolithic control file.
- Routing, transport, UI behavior, worker delegation, evidence enforcement, voice behavior, and autonomous-agent logic are tightly coupled.
- Webchat and voice contain overlapping or duplicated decision chains.
- Priority ordering is frequently implicit in physical code order.

6.3 Current routing model
Routing is composed from multiple independent predicates and gates, including:
- Manual target selection.
- Explicit worker/delegate detection.
- Local status and deterministic fast paths.
- Conversation fast path.
- Local-source detection.
- Public-research detection.
- Team-design detection.
- Infrastructure routing.
- GPU/host targeting.
- Autonomous-agent loop entry.
- Evidence requirements.
- Worker-specific dispatch.

6.4 Recommended future routing model
Target architecture:

Raw Request
    -> RequestEnvelope
       - owner
       - source
       - requested_target
       - intent
       - subject_scope
       - local/public source
       - read_only / mutation
       - authority
       - worker/collaborator preferences
       - OpenCode Assist state/model
       - evidence requirements
    -> Central route_request()
    -> Durable RouteDecision
       - selected lane
       - selected target
       - reason codes
       - authority
       - evidence requirements
       - fallback policy
    -> Execution
    -> Verification
    -> Final response

This routing object should be shared by webchat and voice rather than independently re-derived.

===============================================================================
7. AUTONOMOUS AGENT LOOP
===============================================================================

7.1 Responsibilities
- Preserve original user goal.
- Select evidence actions.
- Execute real tools.
- Reject unsupported completion.
- Recover from ordinary failures.
- Delegate when appropriate.
- Verify state after modifications.
- Produce final synthesis only after requirements are satisfied.

7.2 Evidence tracking
Tracked concepts include:
- used_tools
- successful_tools
- successful_results
- state_change_seen
- post_change_verified
- completion_rejections
- task evidence requirements
- local-source requirements
- web-required evidence
- remote-host requirements

7.3 Runaway protection
Implemented:
- Per-job stop events.
- Generic autonomous-job cancellation endpoint.
- Broad STOP THINKING handling.
- Watchdog authority to cancel clearly runaway Lydia jobs.

Validated runaway threshold:
- Generic Lydia autonomous job.
- Age >= approximately 300 seconds.
- Planner calls >= approximately 20.
- Watchdog cancels the job rather than restarting services or killing unrelated processes.

Observed validation:
- A runaway planning loop was automatically cancelled at roughly 303 seconds and 23 planner calls.

===============================================================================
8. WORKER STATUS, HEARTBEAT, AND WATCHDOG
===============================================================================

8.1 Shared worker state
Module:
- worker_status.py

State:
- /mnt/lydia/agents/lydia/state/worker_status.json

Workers:
- lydia
- adam
- barbara
- opencode

Tracked concepts:
- ready / working / error state
- phase
- task ID
- owner
- model
- PID
- progress summary
- heartbeat
- last error
- circuit state

8.2 Watchdog
Module:
- worker_watchdog.py

State:
- /mnt/lydia/agents/lydia/state/worker_watchdog.json

Classification:
- READY
- WORKING
- QUIET
- WAITING
- STALLED
- ERROR
- OFFLINE
- UNKNOWN

Policy:
- Primarily observational.
- Does not broadly restart, kill, retry, or reroute workers.
- Has one bounded recovery authority for clearly runaway generic Lydia autonomous jobs.

===============================================================================
9. OPENCODE INTEGRATION
===============================================================================

9.1 Runtime
CLI:
- /home/chris/.opencode/bin/opencode

Wrapper:
- /usr/local/bin/lydia-opencode-run

Version observed:
- 2.0.22

Current test model:
- opencode/space-bunny-free

9.2 Portal integration
Implemented:
- Direct "Talk to -> OpenCode" target.
- Live model selector.
- Independent OpenCode Assist ON/OFF toggle.
- Independent OpenCode Assist model selector.
- Browser localStorage persistence for model/toggle selection.

9.3 Direct and Assist modes
Direct:
- Explicit instructions such as "have OpenCode review..." invoke OpenCode through the controller.

Assist:
- Lydia inspects local source first for local/private implementation questions.
- OpenCode provides a specialist second opinion.
- Lydia should independently verify relevant claims before final publication.

9.4 Failure handling
Resolved:
- OPENCODE_ERROR results are recognized as failed tool results.
- Timeout/cancel/error states no longer satisfy successful-evidence requirements.
- Earlier defect in which a timeout was accepted as successful evidence has been fixed.

9.5 Prompt bounding
Recent design:
- Shared `_build_opencode_review_prompt(...)`.
- Explicit OpenCode and OpenCode Assist should use the same bounded review contract.
- Local reviews are intended to be read-only, repository-scoped, concise, and separated into verified findings vs inference/recommendations.

9.6 Progress streaming
Implemented / under validation:
- stdout/stderr streaming replaces purely blocking output collection.
- OpenCode activity is converted into human-readable progress summaries.
- Visible updates targeted at roughly 10-second intervals.
- Worker/job status updated during execution.
- Recent patch throttles status/job persistence to prevent a write storm.

9.7 Timeout behavior
- Hard execution ceiling remains 180 seconds.
- Direct bounded review succeeded in about 33 seconds.
- Integrated bounded review previously succeeded in about 81 seconds.
- Large pasted critique requests have still reached the 180-second limit.
- Latest unified bounded-prompt/progress-throttle patch still requires final live validation.

===============================================================================
10. ROUTING PRECEDENCE AND REGRESSION TESTING
===============================================================================

10.1 Verified routing bug
Failure:
- User explicitly requested "have opencode review..."
- Pasted content itself contained words that satisfied team-design classification.
- `is_team_design()` intercepted the request before OpenCode.

Root cause:
- Broad payload classification outranked explicit user delegation.

Fix:
- Team-design call site now checks:
  `is_team_design(text) and not _explicit_opencode_request(text)`

10.2 Local OpenCode review classification
Added:
- `_opencode_local_review_request(text)`

Purpose:
- Detect explicit OpenCode review requests concerning Lydia/PowerLydia's own system, architecture, codebase, repository, planner, routing, configuration, or implementation.

10.3 Post-OpenCode verification
Added:
- `opencode_local_verify_required`
- `opencode_postcheck_due`
- successful marker `opencode_verified`

Intended rule:
- OpenCode success alone must not complete a local architecture/code review.
- Lydia must perform a successful local-source cross-check afterwards.

10.4 Regression coverage
Current focused regression tests verify:
- Explicit OpenCode outranks team-design payload collisions.
- Explicit OpenCode local architecture requests are recognized.
- External/third-party OpenCode reviews do not automatically gain local-system inspection requirements.
- OpenCode success alone cannot satisfy local-review completion.
- Completion is allowed only after `opencode_verified`.

Latest routing/team-design suite:
- 14 tests.
- 14 passed.

===============================================================================
11. ADAM / HERMES WORKER ARCHITECTURE
===============================================================================

11.1 Identity
- User-facing worker name: Adam.
- Hermes is the backend/legacy identity.

11.2 Role
- Primary PowerMox delegated worker.
- Infrastructure advice/execution as authorized.
- Heavy reasoning/work where remote GPU is appropriate.

11.3 Reliability goals
- Accept Lydia work orders consistently.
- Continue through ordinary failures.
- Report evidence, not unsupported claims.
- Maintain clear boundaries between guest, host, container, and controller state.
- Escalate real capability gaps rather than silently failing.

11.4 Worker capability development
When Adam lacks a required capability:
- Lydia should establish the exact gap.
- Identify the correct host/VM/container ownership.
- Provision routine dependencies when appropriate.
- Validate the repaired capability.
- Store reusable operating knowledge.
- Re-delegate a concrete verification task to Adam.
- Continue the original goal after proof of recovery.

===============================================================================
12. BARBARA AUXILIARY WORKER
===============================================================================

12.1 Role
- Secondary worker for overflow and parallel tasks.
- GTX 1070-backed.

12.2 Constraints
- 8 GB VRAM.
- Model selection must account for tighter memory.
- Readiness should be verified live.
- Avoid treating "known to exist" as equivalent to currently available.

12.3 Strategic use
- Independent second opinions.
- Parallel diagnosis.
- Smaller specialized workloads.
- Overflow while Adam is busy.

===============================================================================
13. OTHO SCHEDULER / MAINTENANCE NODE
===============================================================================

13.1 Current state
- Debian 13 installed.
- SSH working.
- Tailscale online.
- sudo configured.
- System updates completed.

13.2 Intended role
- Scheduled maintenance.
- Long-lived orchestration support.
- Health/status checks.
- Escalation requests.
- Durable task scheduling that does not depend entirely on the interactive Lydia process.

13.3 Architectural limitation
- Otho should not become a competing planner/controller.
- Lydia remains the task owner.
- Otho may request escalation or schedule work but should not silently redefine goals or authority.

===============================================================================
14. VOICE AND AUDIO
===============================================================================

14.1 Services
- lydia-kokoro.service
- lydia-whisper.service
- related voice capture and playback components

14.2 Local voice behavior
- Wake word: "Lydia".
- Kokoro TTS.
- Whisper STT.
- Voice arbitration and barge-in logic have received several fixes.

14.3 Remote voice goal
Desired:
- User can open Lydia webchat through Tailscale from phone or PC.
- Browser can capture microphone audio.
- Lydia can play voice responses remotely.

Current status:
- Text webchat works remotely.
- Remote audio capture/playback has historically been unreliable.
- Multiple browser recorder, playback, voice-owner, and barge-in fixes have been implemented.
- Full remote voice behavior remains an area requiring continued end-to-end validation.

===============================================================================
15. BACKUP AND RECOVERY
===============================================================================

15.1 Backup service
Service:
- powerlydia-backup.service

Timer:
- Hourly.

Script:
- /usr/local/sbin/powerlydia-backup.sh

Backup target:
- Toshiba external drive.
- Label: Storage.
- Mount: /mnt/toshiba.

15.2 Policy
Hourly:
- Critical data.
- Excludes model blobs and virtual environments.

Weekly:
- Full backup including larger model/weight content.

15.3 Reliability features
- flock locking.
- Drive detection by label.
- Mount verification.
- Sentinel file.
- ACL/xattr/numeric-owner preservation.
- tar integrity verification.

15.4 Resolved failure
Problem:
- tar exited with code 1 because active files changed while being read.

Fix:
- warning handling for file-changed events.
- explicit treatment of tar exit behavior.
- archive integrity validation retained.

Validation:
- Multiple successful backup runs.
- Tests included deliberate file mutation.
- Service returned success after hardening.

===============================================================================
16. POWER, UPS, AND SHUTDOWN INFRASTRUCTURE
===============================================================================

16.1 UPS
- CyberPower USB UPS attached to PowerLydia.

16.2 NUT
Services:
- nut-server
- nut-monitor

Known issue history:
- ACCESS-DENIED and communication-loss events occurred during setup.

Current direction:
- NUT services enabled.
- UPS monitoring should be included in future reliability/health dashboards.

===============================================================================
17. STORAGE, MIGRATION, AND MEDIA SERVICES
===============================================================================

17.1 Jellyfin / Jellymox
Goal:
- Migrate Jellyfin application/data and related storage from PowerMox to Jellymox.

Status:
- Migration remains planned/in progress.
- Requires explicit inventory, data-path verification, transfer method, permissions, service cutover, and rollback plan.

17.2 Workstation migration / PowerAlien
- Files were migrated from Windows to Linux Mint on an Alienware system.
- System named/considered "PowerAlien".
- Intended to allow trusted users such as Ryan and Tom to connect through RustDesk for local-network work.

===============================================================================
18. CAMERA AND SENSOR INTEGRATIONS
===============================================================================

18.1 Baseus camera
Model:
- S1UA00.

Goal:
- Private live camera feed embedded in Lydia chat for the owner.

Status:
- Integration remains unresolved.
- Packet capture/protocol investigation has been performed.
- Authentication/protocol/live-stream extraction still requires engineering work.

18.2 Tempest weather station
Goal:
- Integrate Tempest data into Lydia.

Status:
- Requested but not yet fully implemented.

===============================================================================
19. DISPLAY / DESKTOP ENVIRONMENT
===============================================================================

19.1 Vizio 4K display
Target:
- 3840 x 2160 @ 60 Hz.

Connection:
- HDMI port 5.

Recent result:
- A custom 3840x2160 60 Hz KMS mode was successfully active in xrandr.
- Cable and TV settings were investigated as part of achieving reliable 4K60 operation.

19.2 Chrome keyring
Issue:
- Chrome repeatedly requested the Linux keyring password.

Goal:
- Remove repetitive default-keyring prompt on the Mint desktop.

===============================================================================
20. SECURITY AND TRUST BOUNDARIES
===============================================================================

20.1 General principles
- Prefer Tailscale for management exposure.
- Avoid unnecessary public listeners.
- Do not weaken security for convenience without explicit decision.
- Track which component owns each secret, credential, or privileged capability.
- Keep worker advice distinct from controller authority.

20.2 OpenCode containment
Current concern:
- OpenCode has repository/filesystem inspection capability.
- Prompt instructions currently provide an important boundary but should not be the only containment mechanism.

Potential hardening:
- Explicit filesystem allowlist.
- Read-only execution wrapper.
- Command allowlist or capability profile for review jobs.
- Durable execution receipts.
- Provenance metadata for each OpenCode result.
- Clear separation between review-only and mutation-capable modes.

20.3 External helper access
- PowerAlien/RustDesk access should be treated as a separate trust domain.
- Prefer individual accounts and auditable access.
- Avoid sharing Lydia's privileged credentials unnecessarily.

===============================================================================
21. OBSERVABILITY AND OPERATOR EXPERIENCE
===============================================================================

21.1 Dashboard goals
Display:
- Lydia state.
- Adam state.
- Barbara state.
- OpenCode state.
- GPU utilization.
- Current task owner.
- Current phase.
- Active model.
- Runtime duration.
- Blockers/errors.

21.2 Progress expectations
User requirement:
- Long-running work should not remain silent.
- Roughly 10-15 second meaningful progress updates are preferred during long operations.
- Updates should describe actual phase/activity rather than repeating generic "working" text.

21.3 Current progress system
- Worker heartbeat.
- Worker progress summary.
- Autonomous-job progress.
- Webchat progress events.
- Request timing logs.
- Watchdog classification.

21.4 Remaining work
- Improve phase extraction so repeated OpenCode activity remains useful.
- Avoid persistence floods.
- Ensure UI displays progress events consistently.
- Distinguish heartbeat/liveness from actual task advancement.

===============================================================================
22. TESTING AND VALIDATION STRATEGY
===============================================================================

22.1 Unit/regression testing
Existing tests cover:
- Intent routing.
- Team design.
- Deterministic operations.
- Planner and operator behavior.
- Worker inventory.
- Verification/blocker semantics.
- Native planner recovery.
- Plan ingestion.

22.2 Recent routing regression suite
Added cases for:
- Explicit OpenCode precedence.
- Local OpenCode review classification.
- OpenCode verification requirement.

Latest relevant suite:
- tests.test_intent_routing
- tests.test_team_design
- 14 tests passing.

22.3 Live acceptance testing
Required in addition to unit tests:
- Portal request path.
- Voice request path.
- Local repository inspection.
- OpenCode collaboration.
- OpenCode timeout/failure path.
- Post-OpenCode Lydia cross-check.
- Autonomous cancellation.
- Worker status/UI state transitions.

===============================================================================
23. RECOMMENDED NEAR-TERM ENGINEERING ROADMAP
===============================================================================

Phase 1 - Finish current OpenCode validation
- Restart Lydia with the latest unified prompt/persistence-throttle code.
- Re-run large pasted critique case.
- Confirm explicit OpenCode is invoked.
- Confirm bounded prompt is used.
- Confirm progress appears approximately every 10-15 seconds.
- Confirm no job-persistence storm.
- Confirm OpenCode finishes under the 180-second ceiling.
- Confirm Lydia performs local verification.
- Confirm successful_tools includes `opencode_verified`.
- Confirm final response clearly separates verified findings from OpenCode inference.

Phase 2 - Central routing abstraction
- Introduce RequestEnvelope.
- Introduce RouteDecision.
- Move route selection into one pure/testable function.
- Make explicit target/delegate intent authoritative.
- Separate payload content from control instructions.
- Attach reason codes to every route.
- Persist route decision with autonomous job/operation record.
- Reuse identical route decision from webchat and voice.

Phase 3 - Execution policy normalization
- Define capability profiles for Lydia local terminal, Adam, Barbara, OpenCode, Otho, and public web.
- Normalize timeouts, receipts, cancellation, evidence status, and provenance.

Phase 4 - Worker and planner resilience
- Bound retries.
- Avoid automatic web research for failures that concern private/local state.
- Prevent repeated OpenCode retries after a known timeout unless materially changing the attempt.
- Add explicit fallback semantics.
- Continue watchdog hardening.

Phase 5 - Voice completion
- Complete browser microphone path.
- Complete remote audio output.
- Validate phone/desktop Tailscale usage.
- Ensure barge-in and wake-word behavior remain stable.

Phase 6 - Infrastructure projects
- Jellyfin -> Jellymox migration.
- Camera integration.
- Tempest integration.
- Otho scheduled orchestration.
- Barbara production hardening.
- GPU/hardware upgrade planning.

===============================================================================
24. RECENTLY RESOLVED OR SUBSTANTIALLY RESOLVED PROBLEMS
===============================================================================

24.1 OpenCode timeout counted as successful evidence
Status: RESOLVED.
- `_tool_result_failed()` now recognizes `OPENCODE_ERROR`.
- Timeout, cancel, and failed states are treated as failures.
- Failed OpenCode attempts no longer satisfy completion evidence.

24.2 Explicit OpenCode request swallowed by team-design classifier
Status: RESOLVED IN CODE AND TESTS.
- Explicit OpenCode now outranks the team-design fast path.
- Regression test reproduces the payload-collision scenario.
- Relevant routing/team-design test suite passes 14/14.

24.3 OpenCode Assist follow-up never dispatched after initial terminal action
Status: RESOLVED.
- Follow-up dispatch moved to a mechanism that runs after prior tool actions rather than only when tool_actions == 0.
- Live test confirmed OpenCode was delegated after local inspection.

24.4 Autonomous planner runaway
Status: RESOLVED / GUARDED.
- Per-job stop events added.
- Watchdog can cancel a clearly runaway generic Lydia autonomous job.
- Live runaway cancellation was successfully demonstrated.

24.5 Historical worker failure contaminating current readiness
Status: RESOLVED.
- Worker watchdog semantics distinguish historical task failure from present worker availability.

24.6 Stale interactive responses
Status: SUBSTANTIALLY RESOLVED.
- Newer interactive requests supersede older response publication.
- Guards added for asynchronous and local-fast response paths.
- Browser 204 handling fixed.

24.7 Backup failures caused by changing files
Status: RESOLVED.
- Backup script handles tar's file-changed condition appropriately while retaining archive integrity checks.
- Mutation tests succeeded.

24.8 OpenCode direct model selection and portal integration
Status: RESOLVED.
- Direct OpenCode target exists.
- Live model selection works.
- OpenCode Assist toggle/model are independently configurable.

24.9 Local-source requests incorrectly routed to public research
Status: RESOLVED IN ROUTING LOGIC.
- Local/private implementation requests bypass public research.
- Local source is inspected first.
- External web research remains available when explicitly required.

24.10 Local-source questions incorrectly treated as infrastructure operations
Status: RESOLVED IN ROUTING LOGIC.
- Local-source requests are excluded from the infrastructure fast path and sent through the evidence-driven local-source flow.

===============================================================================
25. PROBLEMS STILL TO RESOLVE OR STILL UNDER VALIDATION
===============================================================================

25.1 OpenCode long-request timeout
Status: OPEN / UNDER ACTIVE VALIDATION.
- Some OpenCode jobs still hit the 180-second ceiling.
- Direct bounded review succeeded in ~33 seconds.
- One integrated bounded review succeeded in ~81 seconds.
- Large pasted requests have timed out.
- Shared bounded prompt builder has now been added to unify explicit and Assist routes.
- Latest change still requires live verification.

25.2 OpenCode progress quality
Status: PARTIALLY RESOLVED.
- Streaming progress infrastructure exists.
- Progress events have been observed.
- Earlier implementation caused excessive job-persistence writes.
- Persistence has now been throttled.
- Need to confirm useful 10-15 second updates without long silent gaps.

25.3 Post-OpenCode Lydia verification
Status: IMPLEMENTED IN CODE; LIVE VALIDATION STILL REQUIRED.
- `opencode_verified` path exists.
- Evidence gate requires post-OpenCode verification for qualifying local reviews.
- Need a clean live run proving:
  OpenCode success -> terminal cross-check -> opencode_verified -> final response.

25.4 Central routing architecture
Status: NOT YET IMPLEMENTED.
- Current system still relies on many ordered predicates and regex-based routing decisions.
- RequestEnvelope / RouteDecision design is recommended but not yet built.

25.5 Voice/webchat routing duplication
Status: OPEN.
- Voice and webchat still have overlapping routing chains.
- Risk of future drift remains until a shared router is introduced.

25.6 OpenCode containment
Status: OPEN.
- Prompt-level read-only instructions exist.
- Stronger filesystem/tool restrictions and durable execution receipts should be considered.

25.7 Failure recovery after OpenCode timeout
Status: OPEN.
- Failed OpenCode attempt is now classified correctly.
- Need bounded retry/fallback semantics.
- Must avoid inappropriate public-web fallback for failures involving private/local state.
- Must avoid infinite requeue loops when OpenCode verification is required but unavailable.

25.8 Remote browser voice
Status: OPEN.
- Remote text chat works.
- Reliable microphone capture and audio playback over Tailscale still need complete end-to-end validation.

25.9 Camera integration
Status: OPEN.
- Baseus S1UA00 live feed in Lydia chat is not yet complete.

25.10 Tempest integration
Status: OPEN.
- Requested but not yet fully implemented.

25.11 Jellyfin -> Jellymox migration
Status: OPEN.
- Still requires execution, validation, and cutover.

25.12 Otho production scheduler role
Status: PARTIAL.
- Host is installed and reachable.
- Full scheduler/orchestration role remains to be implemented and validated.

25.13 Barbara production hardening
Status: PARTIAL.
- Worker exists and can be considered for auxiliary tasks.
- Capacity/readiness and production operating policy need continued validation.

25.14 OpenCode/model performance variability
Status: OPEN.
- Same general class of review can vary from ~33 seconds to >180 seconds.
- Need to distinguish model/provider latency, OpenCode tool behavior, repository traversal, prompt size, and local backend interactions.

25.15 Durable route provenance
Status: OPEN.
- Current logs show path labels and tool activity.
- A first-class durable RouteDecision with reason codes should be persisted with each job.

===============================================================================
26. ENGINEERING DEFINITION OF "DONE"
===============================================================================

The lab should be considered mature when all of the following are true:

- One shared routing layer controls webchat and voice.
- Explicit user target/delegate requests cannot be overridden by payload content.
- Every autonomous task has a durable request envelope and route decision.
- Tool failures can never satisfy evidence requirements.
- Every worker has clear capability and containment boundaries.
- Long-running tasks provide useful progress without flooding storage/logs.
- Lydia independently verifies delegated local-system conclusions.
- Worker timeouts have bounded retry/fallback behavior.
- Watchdog can detect and safely stop clear runaways.
- Local AI consistently uses the intended GPU.
- Remote voice works reliably over the private Tailscale portal.
- Backups, UPS handling, and recovery behavior are proven.
- Adam and Barbara can both be delegated useful work with evidence.
- Otho provides reliable scheduled support without becoming a competing controller.
- Camera/weather/media integrations are either operational or deliberately scoped out.
- Major architecture decisions, tests, and recovery procedures are versioned and documented.

===============================================================================
END OF ENGINEERING OUTLINE
===============================================================================
