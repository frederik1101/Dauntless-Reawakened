# UE5.1.1 feasibility test plan

## A. Prerequisites
- Licensed UE 5.1.1 source build with dedicated-server target support.
- Windows C++ toolchain compatible with the chosen engine source.
- Blank C++ project named ReawakenedNetLab.
- Original Dauntless installation remains unchanged.

## B. Baseline: stock engine
1. Build Development Server and Development Client targets for the blank project.
2. Start the server on loopback with a dedicated test port (e.g. 7777).
3. Connect the matching blank-project client.
4. Confirm a map load, connection acceptance, and player controller possession.
5. Record engine version, build revision, and sanitized stage markers.

## C. Compatibility investigation
Compare observed stages in this order:
- Transport and NetDriver initialization
- Engine network protocol and game network version negotiation
- Challenge / welcome / login / join control messages
- Package map and replicated class availability
- Player controller / pawn spawning and possession

Classify each stage as PASS, FAIL, or NOT TESTED. Do not infer later-stage compatibility from an earlier-stage pass.

## D. Bridge decision
Only design a bridge DLL after establishing which client call must be adapted and what the corresponding server expects. Prefer a standalone launcher or supported configuration change where possible. Keep Epic authentication untouched.

## E. Evidence and privacy
Log only stage names, result codes, engine/build versions and elapsed durations. Do not log raw packets, account IDs, hostnames, tokens, session keys or user paths.

## Current status
- Repository scaffold: prepared.
- UE build: NOT RUN.
- Stock client-server test: NOT RUN.
- Dauntless 2.1.1 compatibility test: NOT RUN.
- Client DLL: NOT IMPLEMENTED.
