# Reawakened UE game-server compatibility experiment

This is an **isolated feasibility experiment**, not a Dauntless 2.1.1 server or a playable Ramsgate implementation.

## Goal
Determine whether the original 2.1.1 Windows client can negotiate an Unreal network connection with a separately built UE 5.1.1 dedicated server, and identify the first incompatible handshake stage.

## Boundaries
- Keep the existing Python login backend and Windows login probe unchanged.
- Do not inject DLLs into the retail client in this phase.
- Do not bypass Epic authentication, disable TLS verification, or redirect Epic services.
- Never commit game binaries, assets, SDK dumps, tokens, keys or proprietary protocol captures.
- Use only loopback for initial tests; preserve existing Revived installation.

## Milestones
1. Build a stock UE 5.1.1 C++ dedicated server using an appropriately licensed source-built Unreal Engine and a blank project.
2. Connect a matching stock UE 5.1.1 test client to confirm the server itself works.
3. Collect a **sanitized** protocol-stage report from a controlled original-client connection attempt, if lawful and feasible.
4. Compare network protocol version, project/game network version, package map, net driver, authentication and replicated class expectations.
5. Only then decide whether a client-side bridge is needed and technically justified.

A stock UE server cannot serve Dauntless maps or classes without compatible content and server-side game logic. A successful TCP/UDP connection or socket handshake is not proof of gameplay compatibility.

## Exit criteria
Document the first reproducible compatibility failure and whether it can be addressed without proprietary server code. If the client cannot negotiate a compatible network session, do not build speculative Ramsgate gameplay systems.

See [TEST_PLAN.md](TEST_PLAN.md).
