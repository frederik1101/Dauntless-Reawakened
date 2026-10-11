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
