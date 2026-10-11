# 2.1.1 upstream reuse audit (research branch)

Status: **reference-only**; no gameplay runtime or authenticated Ramsgate server has been ported. This document deliberately does not modify the running backend while other work is in progress.

## Pinned sources and credit

- Dauntless Revived / mixutin, `dauntless-revived` branch: [2.1.1 standalone findings](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/awakening-2-1-1.md), [backend contract](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md), [client internals](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/client-internals.md), [credits and AGPL-3.0 terms](https://mixutin.github.io/dauntless-revived/legal.html).
- Undaunted by gwog and contributors: https://github.com/SyST3MDeV/Undaunted (working **1.4.4**, not a drop-in **2.1.1** runtime).
- Mystic Paradox by Pranav Karande: already attributed and narrowly ported in `NOTICE.md`, `docs/MYSTIC_LOGIN_PORT.md`, `docs/INVENTORY_MIGRATION_PORT.md`. Keep its additional terms.

This audit summarizes independently documented interoperability facts; it copies **no game files, UE SDK, client binaries, credentials, private keys or injected DLL**. Any later copied/adapted AGPL code needs retained copyright, license, attribution and an explicit source commit/file reference. Confirm compatibility of all additional terms before merging.

## What is immediately reusable, and what is not

| Component | Evidence | Existing Reawakened state | Safe next action |
|---|---|---|---|
| Phoenix host-based routing / flat vs wrapped JSON | Revived backend contract, 2.1.1 live/static | `backend/application.py`, `backend/protocol_211.py` already implement a subset | Add contract comparisons and tests; avoid duplicate handlers |
| Login queue: exactly five fields, `state=OPEN` | Revived 2.1.1 live | `backend/contract.py` helper | Test exact shape and number types |
| Epic account link and `epiceos` session exchange | Revived 2.1.1 live | baseline plus opt-in `backend/mystic_login_port.py`; unverified EOS subject is **not** signature-verified authentication | Trace response shape, session continuity, and client errors without logging tokens |
| `GET/PUT/POST /character` and `updateVersion` | Revived 2.1.1 live | SQLite character storage already present | Test roundtrip and reject invalid/stale versions; do not add version twice |
| Inventory migration gate | Mystic Paradox 1.12/1.14-derived; 2.1.1 effect unverified | Already narrowly ported with safeguards | Real-client observation before broadening |
| Progression/loadout/entitlements | Revived mostly static 2.1.1 shapes | Research/bootstrap reads, not actual game mechanics | Tests for response envelopes, types and session ownership |
| Direct Ramsgate map override | Revived 2.1.1 **rendered city**, no pawn | No verified local map boot in this repo | Separate reversible client-only experiment; do not claim game-server success |
| Ramsgate game-server DLL / multiplayer | Undaunted works on UE4 **1.4.4** | No verified UE5 2.1.1 server | Architectural reference only; UE4 offsets and SDK are incompatible |
| Matchmaking/travel, UDP replication, player pawn | Revived 2.1.1 static; Undaunted 1.4.4 live | Not implemented | Requires a genuine compatible UE5 gameplay process, not a fabricated UDP listener |

## Important caveats from the upstream 2.1.1 experiment

1. The old research booted Ramsgate by setting `GameDefaultMap=/Game/Maps/ramsgate/ramsgate_01_persistent` in a user `Engine.ini`. The scene rendered, but **account id was empty and no controllable pawn spawned**. Do not confuse this with a successful city join.
2. The normal city path is matchmade. A real gameplay server must authenticate/bind a player, replicate the world, and spawn/possess a pawn.
3. The retail 2.1.1 executable is a client-only UE5 build. The stock `UWorld::Listen` entry point is stubbed; Undaunted's UE4 1.4.4 injected runtime cannot simply be copied.
4. The older successful `probe.log` reached character and an inventory POST; the newer `probe(1).log` did not reach login-queue or session exchange. Neither heartbeat 404s nor a redacted mailbox 404 proves the root cause. See `docs/LOGIN_REPORT.md`.
5. The project's present EOS-subject extraction is a local **research lookup**, not a validated Epic login. Never claim production-grade identity verification.

## Recommended integration sequence (separate changes, tests before merge)

1. **No-code diagnostic baseline:** collect the bounded read-only login report from a known test attempt and compare the last reached stage.
2. **Contract parity tests:** compare exact login queue, account-link, session envelope, character list, and versioned character save to the documented 2.1.1 shapes.
3. **Only after a real client reaches them:** port missing progression/inventory routes with bounded parsing, ownership checks, and original source attribution. No unconditional 200 for unknown routes.
4. **Separate reversible map-load experiment:** show Ramsgate rendering without claiming a pawn or network server.
5. **UE5 gameplay research branch:** identify a genuine server runtime and end-to-end connection path before any matchmaking claims.
6. **Merge only independently validated changes** after checking concurrent Pro work and GitHub branch head.

## Review checklist

- [ ] No proprietary client content or Epic secrets committed
- [ ] Source provenance, AGPL notices and any additional terms preserved
- [ ] Version-specific evidence tagged 2.1.1 vs 1.4.4 vs 1.12/1.14
- [ ] All new endpoints protected by existing session/ownership rules
- [ ] Real-client evidence distinguished from automated unit tests
- [ ] No assertion that Ramsgate, pawn, hunt or complete login works without a real test
