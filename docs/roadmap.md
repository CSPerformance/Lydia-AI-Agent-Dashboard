# Roadmap

## Near term

- consolidate routing into one structured request/decision layer;
- reduce duplicated routing logic between voice and web chat;
- improve worker selection using measured availability, latency, capability, and task fit;
- improve progress reporting for longer-running worker jobs;
- strengthen independent verification after delegated work;
- continue Voice V2 acceptance and interruption testing;
- expand failure-recovery and stale-result regression coverage.

## Medium term

- make the project easier to install without lab-specific assumptions;
- move machine-specific settings into explicit configuration;
- improve worker performance telemetry and historical scoring;
- support safer parallel investigation by multiple workers;
- improve durable learning while preventing stale or contradictory knowledge;
- separate more controller components from the large central application module.

## Public-release path

Before publishing operational source code broadly, remove private infrastructure assumptions, replace host-specific values with configuration, add reproducible setup documentation, provide safe example configuration, add automated checks for accidental private-data exposure, review licensing, and define a supported installation profile.

The private operational environment remains the proving ground; public releases should contain only portable and safe material.
