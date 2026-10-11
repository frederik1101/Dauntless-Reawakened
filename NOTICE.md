# Notices and modification record

Dauntless Reawakened is an independent, modified interoperability research project,
not an official release of Mystic Paradox, Undaunted, Dauntless Revived or Dauntless.
The combined source is distributed under AGPL-3.0-only (LICENSE). The original
Mystic Paradox Section 7 terms are retained in ADDITIONAL_TERMS.md and apply to
that project's material only. No warranty is provided. No game assets, SDK,
proprietary runtime, credentials or game-client files are distributed here.

> Mystic Paradox's Dauntless 1.12.0 port and related modifications were
> developed by Pranav Karande. See NOTICE.md for contribution
> and provenance information.

## Upstream works

- Original work Copyright (C) 2026 gwog :3 / Gregory Morford (SyST3MDeV/Undaunted).
  https://github.com/SyST3MDeV/Undaunted
- Modified work Copyright (C) 2026 MysticFox / Pranav Karande (pranav158/Mystic-Paradox).
  https://github.com/pranav158/Mystic-Paradox
- The upstream provenance notice is available at the pinned source:
  https://github.com/pranav158/Mystic-Paradox/blob/fd795c6434abd63872f4af277c90747239f1ed40/NOTICE.md

## Reawakened modification — 10 October 2026

backend/mystic_login_port.py translates the selected tags, ban-check,
public-account and migration handlers from Mystic Paradox's login.ts into Python,
with explicit local session checks, single-account scoping, an opt-in test profile
and the flat migration reply recovered for 2.1.1. It does not port the upstream
launcher authentication or token-echo shortcut. Source file:
https://github.com/pranav158/Mystic-Paradox/blob/fd795c6434abd63872f4af277c90747239f1ed40/ParadoxBackend/src/routes/login.ts

The maintenance candidate and reversible test harness are independent experimental
additions, not a claim that upstream implemented or verified those parts.
The existing 2.1.1 response helpers remain based on the public research documented
by mixutin/dauntless-revived, credited in docs/CONNECTION_BASELINE.md.
The gameplay runtime, launcher artwork and branding of upstream projects are not copied.

Corresponding source, tests and build instructions:
https://github.com/frederik1101/Dauntless-Reawakened

## Reawakened modification — 11 October 2026

backend/inventory_migration.py and the inventory branch of LoginPortApplication
adapt the inventory migration gate from Mystic Paradox inventory.ts. The NONE
response is retained; local session/character ownership, bounded parsing and
empty-body restrictions are added. No inventory transaction implementation or
runtime is imported. The existing Section 7 terms and attribution apply to this
upstream material too. Source:
https://github.com/pranav158/Mystic-Paradox/blob/fcf915cb918edbe9f030d03b62c94f4879dc655a/ParadoxBackend/src/routes/inventory.ts

See docs/INVENTORY_MIGRATION_PORT.md for evidence, differences, tests and limitations.
