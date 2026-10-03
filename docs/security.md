# Publication safety

This repository is intentionally separated from Lydia's private operational repository.

## Appropriate public material

Public content should stay at the level of architecture, logical worker roles, generic hardware capabilities, controller design, non-sensitive feature descriptions, reviewed screenshots, placeholder configuration examples, design goals, limitations, and roadmap items.

## Material that stays private

Keep environment-specific addressing, detailed topology, trusted access paths, account-specific information, runtime databases, job payloads, conversation history, voice-profile data, private-device details, backup contents, and internal operational handoff material out of this repository.

## Source publication

Private source should not be copied wholesale into this repository. Review each candidate module for environment-specific addresses, user-specific paths, account identifiers, machine-specific assumptions, and embedded operational data.

Where publication is useful, environment-specific values should be replaced with configuration variables or documented placeholders.

## Review before merge

Before merging a public update:

1. review the complete diff;
2. scan for environment-specific addresses and names;
3. scan for personal account information;
4. scan for private absolute paths;
5. confirm no generated state or runtime files were added;
6. keep anything uncertain in the private repository.

The private repository remains the authoritative operational source.
