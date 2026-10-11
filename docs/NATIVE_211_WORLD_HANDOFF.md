# 2.1.1 native world/driver handoff

## Scope

This change implements a concrete, version-specific attachment operation, not an
owned-process bootstrap or a running Ramsgate server. The previous generic
initialization coordinator and all main-branch login behavior remain unchanged.
No proprietary executable, raw user logs, account data or SDK is distributed.

## New static evidence

Read-only analysis used the privately supplied image with SHA-256
`934325acecf64e19a01f70f72dcdcebd68cfb12f11a812cd551c608ac16cea34`.
The original file was not executed or modified. Names below are analysis labels,
not recovered debug symbols. The existing exact-image binding gate is retained.

Reflection metadata and native instructions agree on these offsets:

| Object | Field | Offset/size |
|---|---|---|
| UWorld | PersistentLevel / NetDriver | 0x30 / 0x38 |
| UWorld | LevelCollections / active collection index | 0x180 / 0x190 |
| FLevelCollection | size / collection type | 0x78 / byte at 0 |
| FLevelCollection | NetDriver / PersistentLevel | 0x10 / 0x20 |
| UNetDriver | World / Notify | 0x150 / 0x230 |

The LevelCollections property descriptor at VA 0x14796d4e0 contains offset 0x180.
The FLevelCollection construction metadata at 0x148716a70 specifies size 0x78.
The dump routine at 0x1453dd9a0 also iterates world+0x180 with stride 0x78.

The operation labelled SetActiveLevelCollection at VA 0x1453ec150 writes the active
index and copies the collection's PersistentLevel, GameState and NetDriver to the
world. At 0x1453ec19a it reads collection+0x10; at 0x1453ec1aa it writes world+0x38.
Consequently, attaching a driver only to World->NetDriver can be undone when the
engine applies a collection. This is a static initialization hazard, NOT proof
that it caused the user's observed login loop.

Three additional byte guards (entry, collection read, world write) matched the
supplied file and are checked again before the Windows native call. The shared
false-return Listen stub is not patched.

## Implementation

`world_attachment.cpp` validates a bounded collection array, exactly one dynamic
source collection, an already-active matching source, matching persistent level,
and absence of a foreign driver. It calls native SetWorld to install delegates,
verifies native World/Notify, writes only the source collection's driver slot,
and reapplies the same collection through the engine's operation. Readback checks
the world, driver, notify, level, collection/index and array invariants. It does
not overwrite static/replay collection driver slots.

The Windows entry additionally checks the supplied game-thread identifier,
dedicated flags, image-local object vtables, engine world-context membership and
the expected SetWorld vtable slot. ReadProcessMemory/WriteProcessMemory target only
the current process. No DllMain, arbitrary-process injection or automatic execution
is added. A failed preflight makes no native calls; a failure after SetWorld may
have native side effects and requires termination of the owned host, not a retry.

These checks do not establish arbitrary UObject lifetime or world readiness. The
caller must eventually be a verified game-thread bootstrap at the appropriate
LoadMap phase, with host mode, exact object identities and enforced local binding.
No runtime has yet supplied that callback in this project.

## Tests and limits

The local Linux compile treats warnings as errors. The new synthetic memory test
passed 92 checks, covering ordering, non-source preservation, malformed arrays,
foreign drivers, changed native state and partial failure. Three new static guards
matched the actual image separately. Neither test executes the game. Windows
compilation and the full CMake tests must be checked in CI for the exact commit.

Still missing: owned-process bootstrap, scoped host-mode/command-line setup, live
EngineOps wiring, real listen/ticks/replication, admission and client join. The
matchmaker added alongside this operation has no production ready host provider.

References: [existing exact-image analysis](NATIVE_211_ANALYSIS.md),
[Revived's native hosting analysis](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/multiplayer.md),
[Epic FLevelCollection API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/FLevelCollection).
Independent implementation; existing AGPL/NOTICE/ADDITIONAL_TERMS remain in force.
