# Dauntless Reawakened

Unofficial, experimental local-backend research for the **Dauntless 2.1.1 Windows client**.

**Not playable. No complete game login, controllable character or hunt server is implemented.**
A running HTTP service, a successful TLS handshake or a green test suite does not prove game compatibility.

## Implemented and locally tested

- Host-based Phoenix service routing, plus prefixed localhost routes for tests.
- Loopback-only HTTP and optional HTTPS, with separate IPv4/IPv6 listeners.
- Local sessions with expiry, revocation and account-scoped character access.
- Transactional SQLite character storage; exact client update versions and string-only data blobs.
- Known login-queue, feature, account-link, account-info, character, entitlement and status response shapes.
- An explicitly opt-in **unverified JWT subject lookup** for research. This is NOT Epic authentication.
- Request logs without tokens, raw URLs, query strings, request bodies or account IDs.

See [the evidence and blockers](docs/CONNECTION_BASELINE.md),
[developer instructions](docs/PROTOTYPE.md), and [test report](docs/VALIDATION.md).

## Development

Python 3.11+ is the tested target. The core server uses only the standard library.
Certificate generation and TLS tests additionally use `requirements-dev.txt`.

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m backend.server
```

Do not redirect your game to this backend yet. No system trust, hosts entries or game settings are changed
by these commands. The project does not ship game assets, client binaries, credentials or private keys.
Local data and certificates belong in the ignored `local-data/` directory.

## Sources

Protocol observations: [Dauntless Revived](https://github.com/mixutin/dauntless-revived).
Architecture reference: [Mystic Paradox](https://github.com/pranav158/Mystic-Paradox).
The current implementation retains this repository's original Python response helpers and independently
implements the documented response contracts; it does not contain either project's runtime DLL or game SDK.
Review and retain applicable licenses and notices before importing upstream code.

Not affiliated with or endorsed by Phoenix Labs, Epic Games or either community project.
