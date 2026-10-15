# Native UE5 host vs Dauntless 2.1.1 login

## Distinct milestones

In the user's actual .6 test, the client received two successful character
GET responses with nine string-valued fields, then reported login failures
and returned to public menu requests. No inventory migration, tuning, CITY
join or game-host connection followed. The older two-field .5 profile got
through several more REST stages but also never performed a CITY join.
A future Unreal game server therefore cannot fix the **earlier character
parse/compatibility regression** merely by listening on a UDP port.

## What is already present

The existing RamsgateMatchmaker has HostProvider, generation/lease guards,
player ownership, candidate polling and UnavailableHost by default. It does
not return a host IP or falsely claim admission without verified readiness.
The existing native/host211 branch contains synthetic world/net-driver
attachment tests, but no working owned-process bootstrap, replicating
original 2.1.1 game world or attached server player.

An earlier attempt to publish original-game native bootstrap was blocked.
That implementation is not being recreated or distributed here.

## Requirements for a genuine original 2.1.1 Ramsgate host

1. A lawful, build-compatible runtime and game assets for the **same** 2.1.1
   client; a new UE project has different network classes and cooked content.
2. Real Ramsgate map and compatible GameMode loaded, a bound correct NetDriver,
   and running world/game-thread tick loop (not just a listening UDP socket).
3. GameState/PlayerState replication and possession of the real game pawn.
4. Valid ticket/admission handling linked to the locally authenticated player
   and consistent travel/encryption protocol; never fabricate a ready host.
5. A trusted owned-process supervisor that proves live world/map, engine build,
   generation, network binding and admission before implementing HostProvider.
   On exit, restart, expiry or lost driver the supervisor revokes all assigned
   candidate destinations.

Only after those are implemented can we verify CITY join, actual spawn and
controllable play independently from HTTP 200 and the PLAY button.

## Separate training project

ue5_lab/RamsgateResearch is an independently licensed MIT clean-room UE5
project containing a C++ GameMode and Game/Editor/Client/Server targets. It can
serve its **own** compatible UE client after installing a source-built UE5
and cooking a test map, not Dauntless. No engine or proprietary files are
distributed. No UE compilation has been run in CI; source-layout tests only.
Do not supply this sandbox process to Reawakened's HostProvider.

Epic dedicated server reference:
https://dev.epicgames.com/documentation/unreal-engine/setting-up-dedicated-servers-in-unreal-engine

See also docs/RAMSGATE_MATCHMAKING.md and
docs/NATIVE_211_WORLD_HANDOFF.md.
