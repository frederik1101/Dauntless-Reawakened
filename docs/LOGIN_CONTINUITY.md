# Character-profile test — character-profile-20261012.6

A paired Windows server and client helper for the original 2.1.1 client.
This is an experimental comparison, NOT proof of a completed login or a
Ramsgate gameplay server. Both EXEs must show character-profile-20261012.6.

## Before starting

Close the previous game, wait for its launcher to confirm restoration, then
stop the previous server with Ctrl+C. Keep all AppData databases, TLS and
rollback backups. Extract BOTH EXEs to C:\ReawakenedContinuityTest.
Do not change the original game EXE, disable security software or alter the
Windows certificate trust store.

## Server: first administrator PowerShell

```powershell
cd C:\ReawakenedContinuityTest
.\Reawakened-Local-Server.exe --client-ports --diagnostic --presence --mystic-profile
```

Wait for CLIENT PORTS READY. The banner must also say EXPERIMENTAL MYSTIC
PROFILE and print PROFILE_INITIALIZATION with counts only. The Database line
points into AppData\Local\DauntlessReawakenedServer\profile-tests, NOT the
original players.sqlite3. Each start creates a NEW copy of the original DB;
changes made during the test remain in that copy and are not merged back.
The original TLS folder is reused unchanged. Logs are saved in the usual logs
folder. Without --mystic-profile the baseline database behavior is unchanged.

## Client: second administrator PowerShell

```powershell
cd C:\ReawakenedContinuityTest
.\Reawakened-Ramsgate-Preview.exe --run --normal-login --external-server --trace-client --seconds 600
```

Confirm MAP, sign into Epic and accept the game terms yourself. Leave both
PowerShell windows open. Click PLAY once if it remains visible. No native
gameplay host is included, so a later matchmaking failure remains possible.

The snapshot adds only missing profile metadata and structural appearance.
It retains your account/character identities and existing strings. It does not
import 1.12 cosmetics, quests or its numeric intro progression; does not advance
progress or grant items. New times and LastChangelist are SYNTHETIC test
metadata, not reconstructed history. See CHARACTER_PROFILE_211.md in the source
archive for the full source comparison and uncertainties.

## Finish

Close the game normally once its behavior is clear, and wait for restoration
before stopping the server. If restoration is not confirmed, close the game
and run .\Reawakened-Ramsgate-Preview.exe --restore before another attempt.

Send the new sanitized server log from:
%LOCALAPPDATA%\DauntlessReawakenedServer\logs
and the result below, not any database, private key, token or raw client log:

```powershell
Get-Content "$env:LOCALAPPDATA\DauntlessReawakenedMapTest\active\map-preview-result.json"
```

No full Epic verification, playable character, real world host or completed
login is established by the automated tests. Original Epic login and EULA are
unchanged. The local identity exchange remains explicit UNVERIFIED loopback
research, not a secure public authentication service.
