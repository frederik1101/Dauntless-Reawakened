# Local 2.1.1 backend: developer instructions

**Research stage, not a playable server.** The earlier in-memory HTTP fixture has been replaced with
host routing, session checks, transactional storage and optional TLS. Historical pure fixture modules
remain for regression tests; the running application uses `database.py` and `session_store.py` instead.

## Verify locally

Use Python 3.11 or later. No game client or Epic account is needed for these tests.

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Without the optional dependency the TLS tests explicitly skip. A green run with skipped TLS tests is
not evidence of a working TLS listener. CI installs the dependency on both Windows and Linux.

## HTTP transport only

```powershell
python -m backend.server
```

In a second terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod -Method Post http://127.0.0.1:8765/login-queue-prod/login
```

Stop with Ctrl+C. `/health` deliberately reports `game_compatible: false` and lists the blockers.
A real Phoenix request uses `Host: login-queue-prod.steelyard.ca` with `/login`; the prefixed URL above
is only a developer convenience. The localhost-only `/__lab/session` test hook requires a per-process
lab key. Automated tests construct it in memory; the CLI does not print or expose that key.

## Optional HTTPS transport test

```powershell
python -m tools.local_tls --out local-data/tls
python -m backend.server --port 8443 --ipv6 --cert local-data/tls/server.pem --key local-data/tls/server-key.pem
```

The tool creates a fresh 30-day test CA certificate, leaf certificate and leaf private key. It refuses
to overwrite an existing directory and never persists the CA private key. It **does not** import a CA
into Windows, modify the game's certificate bundle, edit the hosts file or start Dauntless.
Certificate files must never be committed. Windows file permissions depend on the containing folder's ACL;
use your own local user directory, not a shared/network folder.

For an explicitly isolated research environment, `--allow-unverified-eos-sub` enables the documented
`PUT /gamesession/epiceos` experiment. TLS is mandatory for that option. The token's `sub` becomes a
stable local lookup key. Signature, issuer, audience, ownership and expiry are **not verified**.
It is not an authentication solution and must not be exposed through a proxy, tunnel or LAN.
Subsequent requests require the generated local session bearer, not the original JWT.

## Storage and compatibility

Default database: `local-data/reawakened.sqlite3`. The old `characters.json` is not imported or overwritten.
Back it up before any future migration. Sessions are in memory and intentionally disappear on restart;
account/character records persist. Character creation starts at version 0. Saves must use `characterId`,
`data` as a string containing a JSON object of string values, and an increasing integer `updateVersion`.
Repeated/stale versions return 409; no second increment is added by the server.

The initial `EnteredRamsgate` value is a research seed, not proof of completed gameplay or working travel.
No game-server endpoint is advertised. Unknown routes return an empty 404 on supported HTTP methods.

## Before a real client test

Read [the blockers and next tasks](CONNECTION_BASELINE.md). In particular, do not manually scatter DNS,
certificate or config edits across a machine where Revived already works. Both game builds may share
`%LOCALAPPDATA%\Archon\Saved\Config\WindowsClient`; a backup/restore and build-isolation procedure is needed.
