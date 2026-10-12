# RamsgateResearch — standalone UE5 dedicated-server laboratory

**This is NOT a Dauntless 2.1.1 server.** This clean-room sample has Game,
Editor, Client and Dedicated Server targets and a minimal C++ GameMode. It can
only network with a client built and cooked from **this same Unreal project**.
It has no Dauntless world, network classes, gameplay, credentials, or runtime.
Never advertise this lab as ready in Reawakened matchmaking.

The original code within this independent sample is MIT-licensed (see LICENSE),
subject to the separate Unreal Engine license when you use Unreal Engine.
Epic's Unreal Engine itself, its headers and binary content are not included.

## When you have Unreal Engine installed

Use a supported UE5 **source build** with Visual Studio and Windows SDK; Unreal
is not installed or compiled in this repository's GitHub Actions. Associate the
project's .uproject with that engine, generate project files, and build the
Development Editor target. In Editor create and save a blank map at
Content/Maps/Lab.umap, add a Player Start and change Game/Server Default Map
to /Game/Maps/Lab. Save and cook it for your server and client build targets.

Compile Development Server and Development Client from the same project, then
run RamsgateResearchServer.exe -log -port=7777 -MULTIHOME=127.0.0.1 and run
the matching RamsgateResearchClient.exe 127.0.0.1:7777. Verify a PostLogin
message and a player pawn in that **own** test game. Keep port 7777 local
and don't expose it publicly; the lab has no account authorization.

A successful source build alone does not prove a cooked, connecting server.
This is a foundation for understanding UE server/toolchain behavior, **not**
a way to connect the original Dauntless EXE.

Epic source-build dedicated-server tutorial:
https://dev.epicgames.com/documentation/unreal-engine/setting-up-dedicated-servers-in-unreal-engine

See ../../docs/UE5_HOST_GAP.md for the actual 2.1.1 game-host requirements.
