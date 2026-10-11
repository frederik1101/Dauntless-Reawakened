# First observed post-character blocker — 11 October 2026

## Evidence from the supplied real-client log

The user-provided probe.log shows, in order, successful HTTP responses for:
account-link using **epic** (not the experimental epiceos alias), login queue,
local epiceos session exchange, account info, tags, ban state, character list,
character creation, and another character list. Immediately afterwards a POST
on dauntless-prod with a two-slot inventory path receives 404.

This is evidence of progress into the character/login flow. It is NOT evidence
of a completed game login, a correctly rendered inventory, or a game-server join.
No mm2-prod matchmaking calls occur in this log. The background POST 404s are
tracking-prod /heartbeat; their count was not proof of a failed login call.
A separate mailbox-prod GET remains redacted and unidentified.

The original /inventory/{account}/{character} text was OUR diagnostic template,
not the raw client path. Its slot names were assigned without considering the
HTTP method. Raw values and the body cannot be recovered from that old log.
The new diagnostics therefore distinguish POST and GET and keep both slots private.

## Upstream implementation inspected

[Mystic Paradox inventory.ts](https://github.com/pranav158/Mystic-Paradox/blob/fcf915cb918edbe9f030d03b62c94f4879dc655a/ParadoxBackend/src/routes/inventory.ts),
source blob `0b78377afce4dc1dffce5f4203f056a6199dfde4`, lines 1–65.

It distinguishes:

- POST /inventory/{characterId}/{changeList}: inventory migration gate, returning
  a flat `{"code":"NONE","message":""}` with HTTP 200.
- GET /inventory/{accountId}/{characterId}: fetch inventory.
- POST /inventory: apply an item transaction, a different operation.

Its explicit regex also handles an empty character slot. Its comments report
that missing this POST route blocked login on **1.14.7**. That cross-version
observation motivates the port; it does not prove the same handler solves 2.1.1.
[Revived's 2.1.1 contract](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md)
corroborates the distinct GET inventory and bare POST transaction shapes, but does
not document this migration gate's complete 2.1.1 contract.

## Port and safeguards

`backend/inventory_migration.py` carries the source link, original copyright
headers and AGPL-3.0-only notice. The existing NOTICE/ADDITIONAL_TERMS apply.
`LoginPortApplication` integrates the port; the default `Application` is unchanged.

The handler requires HTTPS and a valid local session. A nonempty character ID
must belong to that session's account. An empty slot is accepted only when the
account has zero or one character; multiple candidates get 409. Only no body or
an empty JSON object is currently supported. Unknown/nonempty request bodies get
422 with `inventory-migration-body-unsupported`, not a false transaction success.

The response means **no inventory migration is performed** for this fresh local
research profile. It imports nothing, changes no database rows, adds no items,
issues no sessions, and does not alter progression. Repeating it has no side effects.
A build-shaped path segment is not cryptographic verification of the client build.
Character creation and research starter-item behaviour in the earlier backend are
unchanged. Real inventory transactions, crafting, XP and gameplay are NOT implemented
by this migration port. The bare POST /inventory still does not report success.

## Validation and next test

16 new pure migration tests and 7 diagnostic tests passed locally. Changed Python
files passed syntax compilation; their copied baseline blobs were checked before
editing. Full application/TLS integration tests run in CI before Windows packaging.
Do not mistake the pure local run for the full integration suite; consult the build
for the actual commit downloaded. The full new test set has 41 tests, including a
synthetic TLS session → character → migration → inventory → database-reopen sequence.

The packaged revision is `inventory-migration-20261011.1`. Retain all existing probe
backups and wait for restoration before replacing/rerunning the EXE. The existing
command and temporary file-change safeguards are unchanged:

```powershell
.\Reawakened-Login-Probe.exe --run --experimental-maintenance --seconds 600
```

No success against the real client is claimed until a new log shows it. The next
observation should be the migration reply and the calls that follow it; a 422 or
ownership error also provides a concrete next boundary. Never publish raw request
bodies, account IDs, tokens or entire state folders.

## The actual game-server milestone

A local backend session is not the Unreal gameplay process. A real city/hunt server
must load the correct 2.1.1 world, bind the player's state, spawn and possess a pawn,
and replicate movement before matchmaking can truthfully point at it. Do not turn
an arbitrary UDP listener or a fabricated IN_PROGRESS reply into a claimed server.
The 1.14.7 UE4 runtime is not a drop-in 2.1.1 UE5 runtime. That work remains separate;
this update removes a candidate earlier HTTP blocker, not that gameplay requirement.
