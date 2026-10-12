# Dauntless Reawakened

Unofficial, experimental local-backend research for the **Dauntless 2.1.1 Windows client**.

**Not playable. No successful real-client login, controllable pawn or hunt server is verified.**
A running HTTP service, TLS handshake or green test suite does not prove game compatibility.

## First Windows login experiment

A bounded, opt-in login probe is now packaged by GitHub Actions. It combines the
existing 2.1.1 backend with selected Python ports from Mystic Paradox's login handlers.
It checks the original client, starts a localhost backend and runs a three-minute
attempt with journalled configuration/hosts/CA-bundle changes and recovery support.
Read the exact effects and restoration procedure before using it.

- [Windows probe instructions](docs/LOGIN_PROBE.md)
- [Download the tested Windows artifact](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38078759843/artifacts/11679128295)
- [Exact source, ported handlers and cross-version caveats](docs/MYSTIC_LOGIN_PORT.md)
- [Verified build/test record](docs/LOGIN_PROBE_VALIDATION.md)

**The maintenance-status response remains an explicit hypothesis.** The opt-in EOS
subject lookup is not signature-verified Epic authentication. There is no compatible
UE5 game server to travel to. Do not interpret a login attempt as playable Ramsgate.

## Backend baseline

Host-based Phoenix service routing; loopback HTTP/HTTPS with separate IPv4/IPv6
listeners; expiring local sessions; transactional, account-scoped SQLite character
storage; documented response shapes and initial inventory/loadout/progression reads.
The starter inventory is an initial research seed, not working crafting/rewards.
The original `backend.application.Application` remains the conservative default;
`LoginPortApplication` enables the additional experimental handlers for the probe.

Python 3.11+ is the tested source target. Certificate generation needs requirements-dev.txt.

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m backend.server
```

These development commands alone do not redirect a game or modify system trust.
No game files, proprietary SDK, tokens, keys, saves or databases belong in Git.

## Sources and licensing

Selected login handlers are adapted from [Mystic Paradox's pinned login.ts](https://github.com/pranav158/Mystic-Paradox/blob/fd795c6434abd63872f4af277c90747239f1ed40/ParadoxBackend/src/routes/login.ts).
2.1.1 protocol evidence comes from [Dauntless Revived](https://github.com/mixutin/dauntless-revived).
No upstream runtime DLL, fixed UE4 hook offsets or game SDK is copied.

The combined source is AGPL-3.0-only: see [LICENSE](LICENSE),
[NOTICE.md](NOTICE.md) and the retained [additional terms](ADDITIONAL_TERMS.md).
Mystic Paradox's Dauntless 1.12.0 port and related modifications were developed by
Pranav Karande. See NOTICE.md for contribution and provenance information.

No warranty. Not affiliated with or endorsed by Phoenix Labs, Epic Games, Mystic Paradox,
Undaunted or Dauntless Revived.

## Character compatibility and separate UE laboratory (October 2026)

- [A/B testing the 2.1.1 character fields](docs/CHARACTER_FIELD_ISOLATION_211.md):
  local SQLite snapshots and filtered client errors, not a verified login fix.
- [Independent Unreal 5 dedicated-server sample](ue5_lab/RamsgateResearch/README.md):
  **not compatible** with the stock Dauntless client; Unreal Engine must be
  installed separately and this template has not been compiled in UE.
- [Original game host requirements](docs/UE5_HOST_GAP.md): actual game
  world/driver/replication and admission readiness still missing.
