# On-demand host development attempt — 11 October 2026

## Outcome

The user requested the nightly development work immediately, aiming for a real local Ramsgate connection test. The work was performed in the active conversation; the nightly schedule was not moved or independently rerun by the scheduler.

The reviewed native branch head was `b004c69004dcb7e7d5868a9cfbb50c1c2409384a`, with main `da9ccd004a4984ec203f4f35ff192f8a2e7943b3`. PR #2 remains draft. The existing backend, native bindings and world attachment are not a runnable complete game host.

An experimental native bootstrap was drafted locally. A GitHub tool security control blocked the attempted publication of the native runtime implementation. That implementation was NOT committed to this branch, was NOT compiled or tested on Windows, and is NOT a user-ready artifact. No attempt was made to encode or reroute that blocked publication through another mechanism. Some support-file Git tree objects had been created before the denial; no ref was advanced to those objects.

This documentation commit contains the outcome only. It does not add or enable a host runtime, alter the login probe, change matchmaking readiness or make the user able to connect to Ramsgate.

## Checks actually performed before the blocked publication

The already supplied game executable remained available in the working container. It was read, not executed or modified. Its SHA256 remains `934325acecf64e19a01f70f72dcdcebd68cfb12f11a812cd551c608ac16cea34` and size is 151448856 bytes.

Eight additional static checks matched: the command-line getter entry, the known LoadMap call, its world/URL argument setup, both PreInit flag stores, the has-driver net-mode immediate, the Winsock bind import ordinal, and the PE entry-point metadata. These are static observations, not live world or network tests.

Seven new pure Python helper tests passed locally, and a portable C++ test program compiled and passed 24 encoding/protocol checks. These drafts are not the committed project's new test suite. They do not test a running game, Windows process initialization, native driver creation, client admission, world ticks or player control. No successful Windows bootstrap build is claimed.

No game binary, private player log, token, account record, database or private key was uploaded to GitHub. No live host was started in the working environment.

## State retained

The last previously verified implementation remains the code documented in RAMSGATE_HANDOFF_VALIDATION.md: native world attachment and an opt-in CITY matchmaker whose only production provider is UnavailableHost. Its earlier successful CI runs do not validate the uncommitted bootstrap draft.

There is no new Windows test package from this on-demand round. Do not tell the user to replace the login probe, repeat login or connect to an invented local destination. A completed native host, ongoing network/world operation, admission and a real player connection remain unverified.

## Follow-up constraints

Respect the denied tool operation. Do not re-encode, split or route the blocked native publication through artifacts, another tool or an automation to evade that control. Continue permitted server work separately and report its actual limits. Do not call an arbitrary listener or a rendered city a working gameplay host.

Keep proprietary game files private, preserve existing backups and configuration, and keep draft/code, compilation, synthetic tests and actual game evidence distinct. The normal nightly schedule remains in place.
