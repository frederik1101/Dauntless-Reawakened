# Standalone local API server (Windows research build)

This is a **persistent local HTTP API backend**, not a complete Dauntless emulator.
It does not bypass Epic login, redirect the game, run a UE5 host, spawn a player,
provide matchmaking host readiness, or make the game playable. Unknown API routes
continue to fail rather than returning fabricated success.

## Windows
Extract the Windows artifact to a new directory such as `C:\ReawakenedServer`.
Keep the bundled source and license notices. Open normal PowerShell:

```powershell
cd C:\ReawakenedServer
.\Reawakened-Local-Server.exe --self-test
.\Reawakened-Local-Server.exe
```

The server stays running until Ctrl+C. It listens **only** on
`https://127.0.0.1:8765` (not on public interfaces). No administrator rights
are required. The certificate is locally generated and not trusted by Windows.
Do **not** import it into Windows' root trust store or disable antivirus.

Database: `%LOCALAPPDATA%\DauntlessReawakenedServer\players.sqlite3`.
Local TLS files: `%LOCALAPPDATA%\DauntlessReawakenedServer\tls`.
Back up the directory before deleting or replacing it. Do not publish its files.
A newly generated TLS certificate is valid for 30 days; after expiry a
controlled renewal is needed. This program does not overwrite existing keys.

The server does not edit hosts, Windows certificates, game configuration,
the Epic launcher or the game executable. The official Dauntless client will
**not** automatically connect to this server merely because it is running.
The current matchmaking provider remains unavailable without a real native host.
The optional research EOS-sub lookup is disabled in this entrypoint.

This is intended for backend development and persistence testing, not as a
public-facing or multiplayer server. Never expose port 8765 to the Internet.

## Experimental real-client HTTP connection test (not gameplay)

**Only after a green build of both Windows packages.** Stop any running
standalone server on 8765 with Ctrl+C and make sure previous preview changes
are restored. Close the game and Epic launcher.

1. In an administrator PowerShell, start the **new** standalone server package
   from `C:\ReawakenedServer`:

   ```powershell
   .\Reawakened-Local-Server.exe --client-ports
   ```

   This binds only loopback IPv4/IPv6 ports 80 and 443. Both ports must be free.
   The existing database is reused. The client-ports mode uses an unverified
   EOS-sub lookup key **for local research only**; it is not Epic authentication.

2. In a **second** administrator PowerShell, run the **new** preview package:

   ```powershell
   cd C:\ReawakenedMapTest
   .\Reawakened-Ramsgate-Preview.exe --run --normal-login --external-server --seconds 180
   ```

   Confirm `MAP` when prompted. The runner verifies local HTTPS before making
   reversible game CA, hosts and config edits. It does not start a competing API.
   Leave both windows open during the test.

3. After the runner restores its changes, stop the standalone server with Ctrl+C.
   The preview result reports `external_server_logs_required: true`: its own
   backend counters are **not** meaningful in this mode. Check the standalone
   server PowerShell for the fixed redacted route labels. Never share raw
   authentication tokens, private certificate keys or full game logs.

**This test can only establish that the original client makes requests to the
persistent local API.** It cannot skip Epic login, prove a completed session,
start a native gameplay host or make Ramsgate playable. An Epic sign-out or
login loop remains possible. Do not disable Windows security or install the
local CA into the Windows trust store. If rollback fails, close the game and
use the preview EXE's `--restore` before any further run.
