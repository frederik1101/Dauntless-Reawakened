# Connection baseline and handoff — 9 October 2026

Target: **2.1.1**, not Mystic Paradox's UE4/1.14.7 runtime. This is an HTTP backend and TLS transport,
not an Unreal game server. No successful Dauntless login, pawn spawn or hunt is claimed.

## What changed

The prior prototype created a token but did not use it to protect account or character calls. It also
read `id` on character saves, treated service names as URL prefixes rather than real HTTP hosts, and
returned JSON on some unknown methods. The new application binds account/character access to a local
session, reads `characterId`, uses host routing and returns bodyless unknown-route responses.

SQLite transactions replace the active server's unguarded JSON-file writer. The old fixture and its
regression tests are retained, but its file is not read by the new server. There is no import-time
creation or loading of a database. CLI listener creation is all-or-nothing, and shutdown closes the database.

## Evidence, not just green tests

Primary protocol source: [Revived's 2.1.1 backend contract](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md),
read on 9 October 2026; source blob `55cdc3b6cd0ac091ab9cb27ddb696b82cfd265a2`.
Additional context: [the standalone experiment](https://mixutin.github.io/dauntless-revived/findings/awakening-2-1-1.html).

| Implemented area | Evidence and limitation |
| --- | --- |
| Login queue, features, link, session response, account info, character wire format | Upstream reports live 2.1.1 observations. Our tests validate our implementation, not a real game. |
| Entitlements, status banner and empty cohort treatments | Statically recovered upstream shapes; current values are minimal research fixtures. They are not complete game systems. |
| Research JWT subject extraction | Reproduces the documented identity-lookup approach only. No signature/issuer/audience/expiry checks; disabled by default and TLS-only. |
| SQLite, local token expiry/revocation, host validation and HTTPS | Independent implementation; exercised by actual local HTTP/TLS tests. |

## Known blockers before a complete client login

1. Recover the exact 2.1.1 maintenance-status, tags and ban-check responses. They deliberately return
   bodyless 404 today. Do not silently turn them into successful empty objects. The upstream notes say
   these were answered but do not establish the fields they read.
2. The 1.14.7 `ParadoxBackend/src/routes/login.ts` contains tags and `isBanned` response examples. Those
   are useful leads, **not verified 2.1.1 contracts**. Preserve source attribution and inspect license
   requirements before incorporating any actual upstream code.
3. Initial inventory/loadout/progression read endpoints now exist: see PLAYER_DATA_READS.md.
   Implement actual transactions, loadout saves, progression rules and presence next. Do not assert
   that initial/empty responses grant a valid full loadout or complete every player-data loader.
4. Prepare a reversible Windows client-test procedure: preserve original game files, game CA bundle,
   shared Archon config and any existing hosts entries. Never install the research CA in system trust
   or disable certificate verification globally. Protect the already-working Revived setup.
5. Test an actual client and record sanitized request order. Until then `game_compatible` stays false.
6. A dedicated UE5 game-server/runtime is a separate blocker. Do not advertise a successful match or
   an address in `IN_PROGRESS` until a compatible process actually listens and handles the session.

## Next scheduled development round

Start by reading the latest branch and CI results; do not assume this document is the latest revision.
Prioritize the blockers above over adding more standalone response helpers. Run the complete test suite,
record skips and failures, and make only changes whose scope is clear. Keep tokens, account identifiers,
certificates, databases and proprietary game files out of public logs and commits. Report any tool or
build limitation honestly. A simulated JWT test is not verification against Epic.

## Implementation references

- [Python TLS API](https://docs.python.org/3/library/ssl.html)
- [Python HTTP server caveats](https://docs.python.org/3/library/http.server.html): this development service is not a public production server.
- [PyCA certificate tutorial](https://cryptography.io/en/latest/x509/tutorial/)

The original repository's small response helpers are reused. No game SDK, game binary, upstream C++
runtime or bulk third-party source code is vendored in this change.

## Follow-up player-data integration

`backend/player_data.py` now matches the documented initial read paths, and the application enforces
session/account/character scope before answering. The two-item research inventory is stored once per
character. Active loadouts use the upstream-tested empty/default shape with `active_index: -1`; there
is no loadout-writing implementation. Progression read responses are explicitly initial fixtures.

A repeated local run exposed a timing race in the log-redaction test: the original handler could send
its response before emitting the audit entry. The log now records its fixed, redacted route **before**
writing the response; three consecutive full runs passed after the change. No sensitive data is logged.
