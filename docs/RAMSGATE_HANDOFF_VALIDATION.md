# World handoff and CITY routing validation — 11 October 2026

Code commit: `e40fb0ebc4ec25d83af6cea5822e243f80eb8667`.
Branch: `work/ramsgate-native-211`, draft PR #2. Main is unchanged.

## Local verification

26 new broker tests passed without skips. The world-attachment C++ source compiled
on Linux with warnings treated as errors, and its test passed 92 checks with no
failures. The published world_attachment.cpp blob matches the tested local file
(`2e4e4420b063f94ae607ec7b13f75b0d0ae79ed8`). All new Python files passed syntax
compilation. Full old backend dependencies were not cloned into this container;
full integration was run on CI, not locally.

Three new native guards matched the privately supplied exact 2.1.1 EXE. Its hash
remained `934325acecf64e19a01f70f72dcdcebd68cfb12f11a812cd551c608ac16cea34`.
No game process was executed. The proprietary executable was not sent to GitHub.

## Native Windows/Linux CI

[Run 38128382842](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38128382842)
completed successfully for both platforms. The actual Windows log of job
`114437412690` was read. It shows MSVC compiling bindings.cpp and the new
world_attachment.cpp into host211.lib, then CTest running both test programs:

```text
37 checks, 0 failures (synthetic engine; no game executed)
92 checks, 0 failures (synthetic world memory; no game executed)
100% tests passed out of 2
```

The 20 PE parser tests also passed in this job without test skips. CMake's compiler
probe reports a skipped compiler check and an unused CMAKE_BUILD_TYPE warning for
the multi-configuration generator; those are not failed/skipped project tests.

## Backend integration CI

[Run 38128382875](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38128382875)
completed successfully in all four Windows/Linux, Python 3.11/3.13 jobs. The actual
Windows/Python 3.11 log of job `114437412846` was read:

```text
Ran 275 tests in 12.063s
OK
```

No skipped tests are listed. This includes all 44 new broker/application/TLS tests.
The HTTPS sequence uses the actual backend transport, sessions and database, but
a synthetic host provider. It does not dial an Unreal port or prove game login.
The other three backend logs were not separately read for their counts/skips.

These PR runs checked merge revision `a93e8293f4968c7c079091d896360a4f950269a3`,
combining the code commit above with main `da9ccd004a4984ec203f4f35ff192f8a2e7943b3`.

## What is not delivered

There is no completed native bootstrap, owned live host provider, actual Ramsgate
listener/tick, ticket/encryption integration, real client join or controllable
player. The only shipped production host provider remains unavailable, so it
cannot publish a fabricated destination. The flat 2.1.1 candidate response is an
explicit research choice whose acceptance still needs real-client evidence.
No new playable or user-ready game-server binary is packaged by these workflows.
See NATIVE_211_WORLD_HANDOFF.md and RAMSGATE_MATCHMAKING.md for exact scope.
