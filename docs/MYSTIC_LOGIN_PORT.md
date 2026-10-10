# Mystic Paradox login port — 10 October 2026

This is a **selected Python port**, not a full copy of Mystic Paradox's backend.
The goal is an opt-in, local **2.1.1 login attempt**, not playable hunts.
The baseline `backend.application.Application` remains unchanged. The new
`backend.mystic_login_port.LoginPortApplication` is enabled only by the test harness.

## Exact upstream source

[Original login.ts at fd795c6434abd63872f4af277c90747239f1ed40](https://github.com/pranav158/Mystic-Paradox/blob/fd795c6434abd63872f4af277c90747239f1ed40/ParadoxBackend/src/routes/login.ts)

Upstream file blob SHA: `3b3f95af6ac1a24f542c33a06d8f65dac83477b6`.
That commit targets **1.14.7**, not 2.1.1. Our adaptation retains copyright,
AGPL-3.0-only, additional terms and attribution (LICENSE, ADDITIONAL_TERMS.md, NOTICE.md).

| Handler | Port / adaptation | Evidence and limit |
| --- | --- | --- |
| GET auth-prod/tags | accountId from session, tags array | Translated from login.ts; 2.1.1 fields not independently verified |
| GET auth-prod/isbanned | isBanned: false | Translated from upstream's local-account stub; not an Epic ban lookup |
| POST auth-prod/accountinfo/public | requested identity, linkedAccounts and username | Translated; restricted to authenticated self instead of global account lookup |
| GET migration-prod/migration/status | flat migration_finished / migration_failed | Deliberately corrected from upstream wrapper for 2.1.1; no external save import |
| POST migration-prod/migration/trigger | same flat initial state | Port for a new local account, not a real migration engine |
| GET login-queue-prod/maintenance/status | Optional supplied JSON object | **Not ported from upstream.** Default stays 404. The probe flag tries the conjecture `{"isMaintenance":false}` |

The already implemented queue/features/account-link/session/character handlers remain
those derived from Revived's 2.1.1 research. In particular, **the upstream token-echo
shortcut is not copied**: a research EOS subject selects a stable local account and a
new expiring local token is issued. This is not signature-verified Epic authentication.

## 2.1.1 source of corrections

[Revived backend contract](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md),
blob `55cdc3b6cd0ac091ab9cb27ddb696b82cfd265a2`, sections Characters, Login and session,
and Status, migration and Gauntlet.

[Original 2.1.1 standalone attempt](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/awakening-2-1-1.md)
provides the direct original-EXE launch switches and game-specific CA-bundle approach.
That project did not obtain a controllable pawn in its 2.1.1 experiment.

## What is NOT ported

No UE4 SDK, fixed hook offsets, DLL, launcher branding, Epic token echo, accounts of
other players, invented matchmaking success or game-server address. No game files.
Copying those runtime offsets would not make the UE5 2.1.1 executable compatible.
Inventory transactions, gameplay progression and a UE5 game server remain separate work.

## Validation

The 40 new tests were executed locally and passed with no skips. They cover the
ported routes, session enforcement, account isolation, default-off maintenance,
TLS with certificate verification, synthetic JWT rotation with persistent character
data, and reversible file/config changes. They do **not** establish a successful login
with the real Dauntless client. GitHub Actions separately validates the full repository.

## Next real observation

Use the bounded Windows login probe described in LOGIN_PROBE.md. Record which
fixed route labels the real client actually calls and whether it accepts the replies.
The maintenance candidate may be wrong and must be changed based on evidence, not
renamed 'verified' because a server-side unit test passes.
