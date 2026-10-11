# Exact-image native host port — 11 October 2026

## Status: foundations, not a running server

The original 2.1.1 executable was supplied privately and inspected without executing or modifying it. This branch adds a reproducible read-only image check, a version-locked native C++ binding layer and initialization gates. **There is no native bootstrap/loader, concrete live EngineOps adapter, running Ramsgate host, matchmaking integration or controllable player in this change.** Do not download the old login probe expecting these changes to start a server.

The main Python backend and existing login probe are unchanged. This is a separate native workstream for issue #1. We are not adding another user-side HTTP diagnostic loop.

## Verified against the supplied file

- Size: 151,448,856 bytes.
- SHA-256: `934325acecf64e19a01f70f72dcdcebd68cfb12f11a812cd551c608ac16cea34` (matches the user's earlier installation check).
- PE32+, AMD64, preferred image base `0x140000000`; mapped image size `155627520`.
- The version resource contains engine version 5.1.1.0; release/2.1.1 strings are present. These are static identifiers, not an independent Authenticode or Epic ownership check.
- 19 byte guards in `native/host211/profile.json` matched the real file. The `E8 rel32` at RVA `0x537140e` resolves to RVA `0xbfde50`.
- Original file hash remained unchanged after analysis. No game binary or raw user log is committed, included in CI, or packaged.

### Existing upstream candidates checked in actual bytes

`UWorld::Listen` at VA `0x140bfde50` is `xor al,al; ret`. It does not create a socket or initialize a world. The LoadMap call at `0x14537140e` calls that address and tests its boolean result. `UWorld::GetNetMode` at `0x1453e4ef0` reads a pointer at world+0x38 and returns 3 (client) when it is non-null. PreInit stores a register byte to `GIsClient` at `0x1488ea0f2` and zero to `GIsServer` at `0x1488ea0f3`.

These byte observations agree with [Revived's client-only findings](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/client-internals.md) and the [2.1.1 continuation plan](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/awakening-2-1-1.md). Function names are inferred analysis labels, not recovered debug symbols. The shared false-return stub must NOT be globally changed to return true: it is not a complete server implementation and the linker shares trivial functions.

`UIpNetDriver::InitListen` at `0x140c6d200` has a nontrivial body. It calls the InitBase virtual slot at +0x2c8, checks failure, and writes the bound port back to URL+0x20. The identified vtable entry is at `0x146252820`, with inferred table base `0x146252548` and InitListen slot +0x2d8. This proves code/structure presence, not that a live host has successfully bound.

### Additional functions located in this analysis

| Inferred function | VA | Evidence |
|---|---|---|
| CreateNamedNetDriver, context overload | `0x1453571f0` | References the duplicate/failure diagnostic strings; searches the active-driver array at context+0x210 and compares driver name at +0x1a8. |
| CreateNamedNetDriver, world overload | `0x1453571b0` | Calls the world-context resolver, then tail-jumps to the context overload. |
| FindNamedNetDriver, world overload | `0x145362850` | Called with engine, world and 8-byte name after creation in existing code. |
| World-context resolver | `0x145365530` | Iterates engine context pointers at +0xea8 and compares each context's +0x2c0 with the world. |
| UNetDriver::SetWorld | `0x144fca360` | Detaches old callbacks, sets World at driver+0x150, binds notify at +0x230 to world+0x28, registers four world delegates and informs replication-related objects. |
| FName::ToString candidate | `0x142fc4a90` | Used in the named-driver diagnostics; output has a 16-byte FString layout. |
| FMemory::Free candidate | `0x142eb8c50` | Null-checking deallocator used for the native temporary strings. |
| FCommandLine::Get | `0x142f4af80` | Returns the command-line buffer; called by PreInit and the UserDir parser. |

The overload distinction matters: passing UWorld* to the context overload would interpret unrelated memory as a driver array. Similarly, simply writing a NetDriver World pointer omits native SetWorld's delegate work. Level-collection ownership, live object types/lifetime, game-thread timing, binding scope and native replication still need verification before calling these routines from a bootstrap.

`GEngine`, `GIsClient` and `GIsServer` are in the virtual zero-filled tail of `.data`, not file-backed byte ranges. Their runtime values cannot be obtained by blindly converting their RVAs to disk offsets. The parser explicitly distinguishes these cases, following [Microsoft's PE section semantics](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format).

## Implemented code

- `tools/pe211.py`: bounded PE parsing and exact SHA-256/size/guard checks, with no execution or modification.
- `profile.json`: small byte guards and the inferred layout observations, not a full SDK or an executable patch.
- `bindings.cpp/.hpp`: C++ wrappers for native create/find/set-world/init-listen and string release. On Windows they can only be constructed after the current process's original file and loaded image pass the pinned identity/guard checks. On other systems binding is disabled. They contain no DllMain, injector, hooks or automatic network start. Checks establish an image binding, not object validity; callers remain responsible for live objects and correct threading.
- `host_core.hpp`: initialization ordering and fail-closed state handling. A partial native failure demands termination of the owned host instead of retrying potentially corrupt state. `listen_bound` does not authorize gameplay advertisement.
- CMake and Windows/Linux CI compile the native library. Tests use synthetic callbacks/images, not the game.

This is independent code using our 2.1.1 analysis and the architecture described by [Mystic Paradox Networking.cpp](https://github.com/pranav158/Mystic-Paradox/blob/fcf915cb918edbe9f030d03b62c94f4879dc655a/ParadoxRuntime/Networking.cpp) and [Revived's multiplayer notes](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/multiplayer.md). No old SDK, runtime DLL or hardcoded 1.14.7 offsets are copied into 2.1.1. Existing repository AGPL/NOTICE/ADDITIONAL_TERMS remain in force.

## Validation performed before publication

20 new Python tests passed locally without skips. The C++ library built locally on Linux with warnings treated as errors; CTest passed 37 checks covering call ordering, failure boundaries, no unsafe retry, no premature gameplay-ready status and rejection of the test executable as a game. The real supplied image separately passed all 19 static guards. **Those are three different checks; none executes the game.** Consult CI for the separately verified Windows compilation result after publication. The full old Python backend suite was not rerun locally because direct GitHub cloning was unavailable.

## Next engineering work (not another identical login test)

1. Implement the isolated host bootstrap and a concrete live EngineOps adapter: validate native object types/lifetime, game-thread entry, correct world/level collections, host mode and enforced loopback socket binding; verify each scoped patch before use. Do not patch the shared false stub or assume that `-server` restores missing code.
2. Start the original Ramsgate world, use the real InitListen path, and observe continued engine/network ticks under an owned-process memory/time watchdog. Keep host and normal-client configuration separate. GPU-free operation remains untested.
3. Wire matchmaking/admission only to a verified live host; then check account/character loading, player spawn and possession, movement replication and reconnect. Existing HTTP 200s do not prove those stages.

The user's missing-host hypothesis is relevant to the eventual world travel. It is not proven as the cause of the latest pre-session login loop; older and newer log attempts reached different stages. Do not close the end-to-end login issue from this static analysis.
