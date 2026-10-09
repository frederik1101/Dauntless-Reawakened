# Technical starting point

This project targets an experimental **Dauntless 2.1.1** single-player revival. No working game integration is claimed yet.

## Existing projects (read before implementing)

- [Mystic Paradox](https://github.com/pranav158/Mystic-Paradox): TypeScript/MongoDB backend, director, Windows launcher and C++ runtime. Its **main** currently targets **1.14.7**, not 2.1.1. License: AGPL-3.0-only plus additional terms. Read its LICENSE, ADDITIONAL_TERMS and NOTICE before copying code.
- [Dauntless Revived](https://github.com/mixutin/dauntless-revived): functioning 1.4.4 gameplay reference. License: AGPL-3.0-only. Version-specific game-server hooks are **not** portable to 2.1.1 without investigation.
- [Revived 2.1.1 research](https://mixutin.github.io/dauntless-revived/findings/awakening-2-1-1.html): documented experiments and blockers.

## Practical approach

1. Study the 2.1.1 findings and identify the minimum request flow needed to reach a controllable character.
2. Map Mystic Paradox backend endpoints against those findings; document differences rather than assuming compatibility.
3. Adapt code only where licenses permit and retain required notices and source-sharing obligations.
4. Test locally with the user's own official client; keep proprietary assets, credentials and session tokens out of Git.
5. Verify each milestone independently: authentication, character data, hub spawn, movement, one hunt, persistence.

**Important:** A custom launcher alone cannot recreate the dedicated game server or game logic. A playable 2.1.1 build is an uncertain long-term goal.

## Sources and credits

The above repositories are independent projects. This repository does not claim affiliation with them or with the game's rights holders. No source code from them is copied here yet.
