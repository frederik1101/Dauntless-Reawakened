# Ramsgate stock-client map preview

Revision: `ramsgate-map-preview-20261011.1`.

## What this test can and cannot show

This is an independently scoped **map-loading preview**, not a game server, a native
host bootstrap, a matchmaking connection test, or a login fix. It temporarily sets
GameDefaultMap to the original Ramsgate map through the game's user Engine.ini.
The native host branch and the normal login probe are not modified. No runtime DLL,
injection, executable patch, listen mode, network-encryption change or artificial
ready destination is included or loaded.

The aim is to observe whether the installed 2.1.1 client can load/render the city.
The normal login scene is replaced by this boot configuration, so this cannot
validate the normal login -> matchmaking -> server journey. Do not infer a player
or server from a picture of Ramsgate. A blank scene, loading failure, return to
login, or a client crash is possible. Player spawning/control is not implemented.

## Evidence and choices

Revived's [2.1.1 standalone findings](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/awakening-2-1-1.md)
(source blob `c337249b84271f96015bef88dc8d72ef19bd1669`) report that this map and city
GameMode rendered Ramsgate but did not produce a controllable player. That is an
upstream observation, not a successful test on the user's PC with this package.
The documented map is `/Game/Maps/ramsgate/ramsgate_01_persistent` in
`Archon_Maps_2-WindowsClient.utoc`/`.ucas`. File presence is checked, not container
contents or completeness of the whole installation. The executable must match the
previously inspected full SHA-256 and pass the existing original-signature check
before a run. No proprietary executable/assets are redistributed.

[Unreal config documentation](https://dev.epicgames.com/documentation/unreal-engine/configuration-files-in-unreal-engine)
explains configuration overrides generally; compatibility with this retail build
is informed by the separate Revived findings. The preview does not request
`?listen`, replace the player controller, force identity fields, raise player-start
timeouts or disable the engine's hang detector.

Memory is sampled twice per second using
[GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)
on the already-owned Windows CPython Popen handle. This reads resource counters,
not process memory contents. A maximum of private commit and working set at or
above 5000 MiB ends the preview. Sampling can overshoot; this is not a hard OS
memory reservation/limit. An unavailable resource query also ends the preview.
Streaming pool hints limit some graphics allocations, not all game memory.
The normal duration is 120 seconds; the permitted range is 30–180 seconds.

## Backend and privacy

The existing local HTTP/TLS backend runs on loopback IPv4/IPv6, ports 80/443, with
an **in-memory** database. The user's previous persistent research database is
neither opened nor altered. No automatic character/identity fallback is added.
Existing session checks and unknown-route errors are preserved. Consequently the
standalone city's unauthenticated data requests can still fail: this test does
not claim to reproduce every backend choice from Revived's standalone experiment.
The previously experimental maintenance reply and unverified local EOS-sub lookup
retain their limitations; neither is proof of secure Epic authentication.

HTTPS `tracking-prod/heartbeat` bodies are projected to an allowlisted map label
only. Raw bodies, server names, account IDs, login codes, tokens and other fields
are not logged. The existing heartbeat HTTP response is unchanged, including 404.
A positive `ramsgate_self_report_seen` means only that a client reported that map;
it is not proof of completed rendering, a real server connection or player control.
No telemetry is uploaded by this tool. The game itself may contact other services.

## Running on Windows

Close the game and any previous probe normally; wait for its restoration message.
Extract the completed Windows preview artifact into `C:\ReawakenedMapTest`, not
into the game installation. Keep its accompanying license/notices and source ZIP.
The preview EXE is not code-signed. Do not disable security software to run it.

Use PowerShell as administrator:

```powershell
cd C:\ReawakenedMapTest
.\Reawakened-Ramsgate-Preview.exe --run
```

Read the warning and type `MAP` to consent. Keep the console open. Take a screenshot
if the city becomes visible, then close the game normally. The preview stops its
own launched game after the time/memory limit; it never terminates other programs.
A preview-triggered time or memory stop is distinguished from a client exit in
the result. The game's console output is not retained; the request logger and
filtered map report provide the limited evidence collected by this test.

## Restoration and results

The old login probe must not have an unfinished rollback journal. The map preview
uses a different state folder: `%LOCALAPPDATA%\DauntlessReawakenedMapTest`.
A busy local backend port prevents configuration edits. The existing rollback
helper backs up the original hosts, game CA and entire WindowsClient configuration
before changes. Only the newly journal-owned config receives the preview Engine.ini.
On normal completion the preview closes its game first, restores the original
files, and keeps its test config and backups locally. Unexpected edits are retained
for review rather than overwritten. A crash/power loss can require manual recovery.

If restoration was not confirmed, with the game closed run **the preview EXE**:

```powershell
.\Reawakened-Ramsgate-Preview.exe --restore
```

Do not use the old login probe's default restore command for the preview journal.
Do not delete backups or start another game/probe before restoration succeeds.

Share only the filtered result (or a screenshot without login codes):

```powershell
Get-Content "$env:LOCALAPPDATA\DauntlessReawakenedMapTest\active\map-preview-result.json"
```

The report deliberately keeps `renderer_verified`, `game_server_started`,
`client_join_verified` and `controllable_player_verified` false. A screenshot
can separately establish visual rendering; a real host/join needs different tests.
The local map-preview.log has timestamps and redacted request labels. Never publish
whole state folders, raw game/crash logs, TLS keys or the proprietary game files.

## Validation boundaries

26 new pure helper tests ran locally without skips. The additional 19 integration
and lifecycle tests are intended to run against the full repository on Windows CI:
real temporary-file rollback, original backend responses, one verified local TLS
heartbeat exchange, and mocked game-launch failure paths. No game is executed by
those tests. The packaged --self-test checks imports, in-memory backend and Windows
resource counters without creating a user profile. Actual CI outcome must be read
for the delivered commit; compilation is not evidence that the city loads.
