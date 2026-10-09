# Initial player-data reads — 9 October 2026

These are **implemented read endpoints for a local research boot**, not working inventory transactions,
crafting, saved loadout changes, XP, bounties, Escalations or hunts. The backend still reports
`game_compatible: false`. A test of a response shape does not establish that the game completes its loader.

## Primary evidence

[Dauntless Revived's backend contract](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md),
source blob `55cdc3b6cd0ac091ab9cb27ddb696b82cfd265a2`, sections Loadouts, Inventory and Progression.
Read directly on 9 October 2026. The implementation uses these documented protocol facts; no upstream
runtime code, game assets, catalogue dump or client executable is included.

| Service and GET path | Implemented response | Evidence/limitation |
| --- | --- | --- |
| `dauntless-prod /inventory/{account}/{character}` | Flat `stackedItems`, `instancedItems`; two persisted research starter instances | Statically recovered 2.1.1 schema; source documents `WP_EB_TRAINING` and `LT_BASIC` for its standalone boot. Not a full catalogue or real starting loadout verification. |
| `loadout-prod /loadout/{account}/{character}/all` | Wrapped empty loadouts, typed persistent data, 1/5/0/0 slots, `active_index: -1`, `needs_migration: false` | Upstream reports this shape avoided an actual 2.1.1 loadout crash. No hand-written equipped loadout is asserted. |
| `loadout-prod /loadout/{account}/slotcount` and `.../{character}/slotcount` | Same four integer slot counts | Static 2.1.1 evidence; consistent with `/all`. |
| `progression-prod /progression/config` | String-code wrapper, `paths: []` | Initial static shape only; no real progression configuration. |
| `progression-prod /progression/{account}` and `/progression/objectives/{account}` | Integer-code wrapper, array payload | Static evidence; objectives envelope is marked likely upstream. No earned tracks or objectives. |
| `progression-prod /cooldown/{account}` | Flat `cooldowns: []` | Static evidence, partly inferred upstream. No cooldown writes. |
| `progression-prod /bounty/{account}` | Flat empty bounties and typed draft-data fields | Static evidence. No draft/grant/reward system. |
| `progression-prod /escalation/ESC_SEASON_1..6/{account}` | Wrapped zero-level initial state and empty talent/unlock lists | Static evidence; not an implemented Escalation progression system. |

All reads require a generated local session and enforce the account ID in the path. Character-specific
routes also enforce ownership. A valid session for A cannot read B's inventory or loadout by changing a URL.

## Starter inventory persistence

The database creates two new tables without deleting or rewriting existing accounts/characters. The
first owned inventory read atomically marks that character as bootstrapped and persists the two
research items. Repeated reads, reopening the database and concurrent reads do not issue more items.
The explicit marker means a future legitimate removal would not silently re-grant the seed.

This seed is isolated to the research database. Nothing reads, changes or imports a Revived account.
A failed lookup never creates a character. Inventory reads do not increment character data versions.

`POST /inventory` deliberately returns an empty **503**, not a fabricated successful transaction.
Source documentation establishes the response keys, but a proper implementation also needs the
request-item semantics, grant/spend authority, catalogue validation, atomicity and retry deduplication.
Do not echo an incoming transaction as its result. Loadout and progression writes remain unimplemented.

## Test scope

The new tests use real loopback HTTP. An additional TLS sequence exercises an explicitly enabled
research session with a **synthetic JWT**, account-info, character creation, inventory, loadouts and a
character save/read. It intentionally does NOT include maintenance, tags or ban-check, and therefore
is NOT a complete login-chain test or an Epic authentication test.

The loadout tests require actual JSON integers/booleans, consistent slot counts, a negative empty-loadout
active index and no shared mutable response objects. Storage tests verify ownership, persistence and
32 concurrent initial inventory reads with only two instances.

## Still next

Recover and verify the missing early login responses, add a reversible client-test harness, and test
with the actual client. Then implement proper state mutations and a compatible Unreal game-server
process. The presence or absence of these read endpoints alone cannot produce a controllable pawn.
