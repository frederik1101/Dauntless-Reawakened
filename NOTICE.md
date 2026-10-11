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

## Post-login response port — 11 October 2026

backend/post_login_contracts.py adapts three tuning response shapes and selected
store response fields from Mystic Paradox tuning.ts/store.ts at revision
386302c1333fe3dfcb2baf176edc101e200f5081. Original copyright and Section 7 terms
remain applicable to that material. Identity mapping follows mixutin's Revived
social.md (blob 4ea2ddf4444f0c018b109e6c0aaba15545ca6f64), distinguishing its 1.4.4
parser evidence and 2.1.1 request observation. The implementation scopes mappings
to a local session's own external/Phoenix identity, corrects linkedAccounts,
uses a read-only local SQLite balance snapshot, and reports no creator affiliation.
The tuning defaults and negative creator state are experiments, not recovered
final 2.1.1 gameplay data or proof of client acceptance. Sources, modifications,
validation boundaries and complete running instructions: docs/POST_LOGIN_FIXES.md.

## Local source update — login reset trace, 11 October 2026

The three existing game-tuning response ports now use a string `code` for the
2.1.1 reader while keeping their object payloads and research defaults unchanged.
This is not a recovered official 2.1.1 data set or a proven login repair.
New protocol metadata and owned-child stdout filtering are original Reawakened
helpers; they do not import a native runtime, perform injection or bypass Epic.
See docs/LOGIN_CONTINUITY.md for the two-log review, evidence and validation limits.

## Reawakened local continuity change — 11 October 2026

login-continuity-20261011.4 includes the previously source-only type/trace
corrections, an independent wsproto-based presence transport experiment, and
byte-identical local character-save retry handling. No original game files or
Mystic native runtime are included. Presence source evidence is the public
2.1.1 static contract; its relevance to the real-client reset is unverified.
See docs/LOGIN_CONTINUITY.md and THIRD_PARTY_NOTICES.md.
