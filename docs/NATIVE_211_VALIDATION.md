# Native 2.1.1 foundation validation — 11 October 2026

Code commit: `ecb555c09e556821029b81335161613a2d14549d`, draft PR #2, branch `work/ramsgate-native-211`.

**This is not a running game server or a user-ready Windows host package.**

## Real file, read-only

The supplied original executable was never executed or modified. Its size is 151,448,856 bytes; SHA-256 is `934325acecf64e19a01f70f72dcdcebd68cfb12f11a812cd551c608ac16cea34`. A final independent re-hash returned the same value. All 19 profile byte guards and the relative Listen call target matched. Native globals in virtual zero-fill were treated as having no on-disk runtime value.

The published C++ files' Git blob hashes match their locally tested sources. The published profile has formatting differences only; its guard values and layout entries match the locally validated profile. No proprietary game image or raw user log was uploaded to the repository or CI.

## Local execution

- 20 synthetic Python PE tests passed without skips.
- Linux C++ static library compiled with warnings treated as errors.
- CTest ran one test executable, which reported **37 checks, 0 failures**. Its engine interface was simulated. The original game functions were not called.

## GitHub native CI

[Native workflow run 38125769843](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38125769843) completed successfully on Windows and Ubuntu.

The complete Windows job log (`114429703818`) was read. It checked out PR merge commit `240cde852dbfc9068b74e91d3efc17aca10aec9c`, merging the code commit into main `da9ccd004a4984ec203f4f35ff192f8a2e7943b3`. The log shows:

```text
Ran 20 tests in 0.012s
OK
host211.vcxproj -> ...\Release\host211.lib
host211_tests.vcxproj -> ...\Release\host211_tests.exe
37 checks, 0 failures (synthetic engine; no game executed)
1/1 Test #1: host_initialization_gates ... Passed
```

No skipped Python or CTest tests were reported. CMake's configure output says a redundant compiler check was skipped and warns that CMAKE_BUILD_TYPE is unused with the multi-configuration Visual Studio generator; the actual compilation and Release test both ran. These are not skipped game tests.

The Ubuntu native job (`114429703986`) also reports successful PE tests, configuration, compilation and CTest in the retrieved job summaries; its full log was not separately inspected. Linux tests were additionally run in the local environment.

## Existing backend CI

[Backend workflow run 38125769846](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38125769846) reports successful completion of all four Windows/Linux Python 3.11/3.13 jobs. Job summaries were checked. No new exact full-suite count or skip count is claimed here because those four full logs were not read in this validation step.

## What remains unverified

There is no live bootstrap/loader or concrete engine adapter in this change. No native world was started, no real game netdriver was opened, no player joined, and no pawn/possession/movement replication was tested. The C++ wrappers' inferred ABI, live object lifetime, game-thread entry, world/level-collection links, startup mode and loopback enforcement still require integration work. The static-library build is not evidence that those conditions hold.

The initial coordinator never advertises gameplay readiness. Do not replace this missing runtime with a fake server endpoint or ask the user to rerun an old login probe as a test of this branch. Continue from `NATIVE_211_ANALYSIS.md` and issue #1.
