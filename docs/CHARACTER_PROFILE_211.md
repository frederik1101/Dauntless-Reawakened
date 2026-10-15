# Mystic-derived character-profile test for 2.1.1

Revision: `character-profile-20261012.6`. Experimental, not a verified login fix.
No native game server, Ramsgate join, or controllable player is provided.

## Actual source comparison

Mystic Paradox commit 386302c1333fe3dfcb2baf176edc101e200f5081,
`ParadoxBackend/src/controllers/character.ts` (blob
fabe2f180775c1a4fce72cdb935a8089e792ed09), `NormalizeCharacterData`, fills absent
metadata before serving character data and after saves. Its returning-player
logic also forces appearance/intro state, which is a development shortcut.
This port is deliberately narrower than that function.

The user's actual .5 trace returned only PlayerAccountProgressStep and
RecentPlayers, at version 6; it saved the same two fields as version 7.
Protected calls had a valid local session and socket-write completion.
There was no account/mapping request in that submitted trace. The user reported
an automatic return to login at Updating Game Data. No raw logs are published.

## Concrete behavior changed

`--mystic-profile` uses a NEW SQLite backup snapshot each invocation. It never
selects the original players.sqlite3 for writes. Account keys, character IDs,
versions, inventory and balances are copied unchanged. Only the snapshot's
missing profile fields are initialized atomically before any listener starts.
GET remains read-only. Later POST /character normalizes missing fields before
the normal version-checked save, returns the ACTUAL stored string, and retains
generated fields if a later client request omits them. It does not double-
increment versions or ignore ownership/conflicts. Identical normalized retries
reuse stored dates, rather than changing on each request.

Added only when missing:

- RecentPlayers: string containing {RecentPlayers:[],Version:0}.
- CharacterFlagData and LoginFlagData: strings containing {Flags:[]}.
- PlayerDataRepair: string containing {Data:[]}.
- LoginTime and LastLoginTime: synthetic UTC test time in Mystic's format.
- LastChangelist: synthetic test build metadata, string 682875, not real history.
- AppearanceData: common structural fields CreationState, Data, AssetReferences
  and StringData. The structural sample has one Head Slot with empty MorphData,
  empty asset references and empty cosmetic selections. No Hair12/skin/body
  preset or other unverified 1.12 asset is imported. CreationState is FaceComplete
  only when the existing 2.1.1 progress name already denotes a created character;
  otherwise it is NewCharacter. Existing appearance strings are never overwritten.

All outer data values remain strings. Existing values, including empty strings,
are preserved. No progress state is advanced, no HasFinishedTutorial key or
WatchedNewRamsgateCinematic flag is added, no 1.12 enum ordinals or quest data
are used, and no currency/item/XP grants occur. This is a structural profile
experiment, NOT a complete catalogue, appearance implementation or progression
dataset. A more populated response still may be rejected by 2.1.1.

## Static checks and limits

The user's previously supplied original 2.1.1 image was examined READ-ONLY.
SHA256 934325acecf64e19a01f70f72dcdcebd68cfb12f11a812cd551c608ac16cea34.
The relevant profile names and appearance structural names/creation-state
literals occur in it; literal presence is NOT proof of required fields or
correct defaults. No binary, SDK, asset dump or raw disassembly is included.

A targeted static review followed the CheckCharacterCompatibility path into
the LastChangelist reader. The missing-key path logs an unknown previous CL and
reaches its non-rejecting continuation; a greater stored CL uses a different
branch. Thus missing LastChangelist ALONE must not be claimed to explain this
user's reset. Seeding it in the snapshot is a comparison input, not a proven fix.
The new fixed client markers retain the unknown-build message distinctly from
login failures and also recognize reviewed migration-failure literals.

The original 2.1.1 string-valued character envelope, private local session,
Epic portal, EULA, original executable hash check, reversible launcher and TLS
are retained. No new trust store, host names, network listener or native runtime
is introduced. This does not implement the separate telemetry capture proposal.

## Validation

Tests cover the observed two-field seed, field types, no progression/cosmetic
imports, repeat normalization, stable retry dates, existing-value preservation,
source database hash invariance, fresh snapshots, corrupt source rejection,
original-path refusal, concurrent saves, account isolation, actual CA-verified
HTTPS read/save/relogin sequences and private diagnostic output.
Windows build results are recorded separately after they exist.

## Acceptance

Compare the real client against the normalized copy: does PLAY stay visible?
If not, inspect the updated filtered client markers and profile fields in the
server trace. Never assert that HTTP 200 or initialized fields prove login.
A CITY request and actual native gameplay remain separate unverified stages.

References:
- https://github.com/pranav158/Mystic-Paradox/blob/386302c1333fe3dfcb2baf176edc101e200f5081/ParadoxBackend/src/controllers/character.ts
- https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/awakening-2-1-1.md
