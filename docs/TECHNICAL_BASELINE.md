# Verified technical baseline — 9 October 2026

## Target
- Dauntless **2.1.1**, Unreal Engine **5.1.1**, IoStore.
- Single player on local Windows 11 PC; public source repository.
- **No working 2.1.1 gameplay implementation yet.**

## Upstream sources
1. [Dauntless Revived 2.1.1 findings](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/awakening-2-1-1.md): local login chain and Ramsgate map boot were demonstrated, but no controllable player pawn spawned. The document identifies missing account binding and recommends a dedicated game-server approach rather than standalone map boot.
2. [Mystic Paradox port notes](https://github.com/pranav158/Mystic-Paradox/blob/main/docs/DAUNTLESS_1_14_7_PORT.md): **1.14.7 is not 2.1.1**. The 1.14.7 port runs on Unreal 4.26.2 and its dedicated hub/hunt processes work. Its SDK, offsets, hooks and binary patches cannot be assumed compatible with UE5.1.1.
3. [Mystic Paradox additional terms](https://github.com/pranav158/Mystic-Paradox/blob/main/ADDITIONAL_TERMS.md): AGPL-3.0-only with attribution and modification notices on covered material. No code copied yet.

## First engineering decision
Before building a launcher or copying code, identify the smallest reusable protocol layer and whether a UE5.1.1-compatible dedicated server can be started. A local HTTP service alone is not a working Dauntless server.

## Milestone gates
- M0: document source provenance and licenses (in progress).
- M1: reproduce the published 2.1.1 login/Ramsgate experiment with the user's own client and sanitized logs.
- M2: resolve controllable pawn / dedicated game-server boot.
- M3: complete one hunt with saved progression.

No game binaries, proprietary assets, Epic tokens or credentials belong in this repository.
