# Stock-client Ramsgate map preview validation — 11 October 2026

Code commit: `dd294ca42846a0d0bdc1862ee2b67253b7a39b9e`.
Branch: `work/ramsgate-map-preview`, draft PR #4, based on the existing native branch.
Main and the native branch are unchanged by this separate preview workstream.

## Verified Windows build

[Build 38132065066](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38132065066)
completed successfully. The complete decoded log of job `114448269909` was read.
It contains:

```text
Ran 320 tests in 8.653s
OK
```

No skipped tests are reported. This includes all 45 new preview tests: 26 pure
helper/observation/watchdog cases and 19 backend/TLS/config/lifecycle cases. The
lifecycle cases launch mock processes, not Dauntless. The TLS test opens a real
loopback TLS socket and submits a synthetic map heartbeat; it is not a game join.

The job checked PR merge revision `730c424783090d6b14b59c3a04f3def60208a73d`,
combining the code commit above with base `8952a456b6ef7dfea62585fba484de757560b242`.

PyInstaller built Reawakened-Ramsgate-Preview.exe. The packaged --about and
--self-test both ran successfully. The latter checks the in-memory backend,
imports and actual Windows process-resource counters under a nonexistent temporary
LOCALAPPDATA profile; it passed the assertion that no such profile was created.
No proprietary game executable, native runtime or game assets were used on CI.
This validates packaging and the tested helper paths, NOT rendering or gameplay.

## Local checks

26 pure tests passed locally without skips; new source passed Python syntax
compilation. The full old repository could not be cloned in the working container
because github.com did not resolve. Full integration ran on GitHub CI, not locally.
Published helper and runner blob hashes match the locally checked files:

- map_preview_support.py: d662674f5d917892522305a3b93c648abf3095d5
- ramsgate_map_preview.py: 84438293593c9fde24575306ff94fe4519733c3c

No supplied proprietary executable was executed, edited or uploaded in this round.

## Verified artifact

[Windows map-preview package](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38132065066/artifacts/11699985229)

- Artifact: 11699985229, Reawakened-Ramsgate-Map-Preview-Windows.
- ZIP size: 13,543,087 bytes.
- ZIP SHA-256: 39a1d7e2c106fc6c643d3ddc19284f3e7073b84c13a130e68241ef0183780d59.
- Revision: ramsgate-map-preview-20261011.1.
- Includes executable, notices/license, matching source archive, instructions and EXE hash list.
- Not code-signed. Do not disable security software. The ZIP hash is not the EXE hash.
- Artifact metadata reported not expired when checked. Retention ends 25 October 2026.

## What the user can test

Extract into C:\ReawakenedMapTest. After the old probe has restored its changes,
run Reawakened-Ramsgate-Preview.exe --run as administrator and type MAP.
The preview temporarily changes the starting map to Ramsgate. It does not load a
native host component, supply an invented match destination, or remove session
requirements. Default duration is 120 seconds and the sampled memory cutoff is
5000 MiB. It uses an in-memory backend and does not touch the previous character DB.

Observe the game screen; share map-preview-result.json from the separate
DauntlessReawakenedMapTest state folder. A Ramsgate self-report is not verified
rendering, client join or a controllable player. A return to login is still possible.
Restore with this preview executable's --restore, not the old login probe, if
normal restoration was not confirmed. Keep all backups. Full instructions and
limitations are in RAMSGATE_MAP_PREVIEW.md.

The real gameplay-host milestone remains open. This is a reduced-scope, config-only
map-loading test; no previously denied native implementation has been delivered.
