# New paired package — identity-mapping-20261012.5

Use BOTH new executables. This is a conditional identity-mapping compatibility
experiment, NOT a confirmed login fix. Detailed changes and evidence limits are
in docs/IDENTITY_MAPPING_211.md in Corresponding-Source.zip.

Stop the old programs only after the runner confirms restoration. Preserve every
AppData database, TLS directory and rollback backup. Extract over the application
files in C:\ReawakenedContinuityTest (not into the Dauntless game directory).

Administrator PowerShell 1:

```powershell
cd C:\ReawakenedContinuityTest
.\Reawakened-Local-Server.exe --client-ports --diagnostic --presence
```

Wait for CLIENT PORTS READY. Administrator PowerShell 2:

```powershell
cd C:\ReawakenedContinuityTest
.\Reawakened-Ramsgate-Preview.exe --run --normal-login --external-server --trace-client --seconds 600
```

Both must report identity-mapping-20261012.5. Confirm MAP and perform normal Epic
login/EULA acceptance. Nothing impersonates Epic or changes the original game EXE.
If PLAY stays visible, one click is enough for this test. The absent native host
still prevents a playable Ramsgate. Close the game normally once the result is
clear, and wait for rollback confirmation before stopping the server with Ctrl+C.
If rollback fails, leave the game closed and run the preview EXE with --restore.

Share the NEW sanitized server log from
%LOCALAPPDATA%\DauntlessReawakenedServer\logs and the result:

```powershell
Get-Content "$env:LOCALAPPDATA\DauntlessReawakenedMapTest\active\map-preview-result.json"
```

Never share full AppData, database, certificate keys, sign-in codes or raw logs.

---

## Previous continuity capabilities (retained)

### Earlier revision login-continuity-20261011.4

**Experimental backend, NOT a Ramsgate gameplay server.** No guarantee that PLAY
stays visible. Both executables must come from this exact paired build. The
original EXE, UI, Epic sign-in and user acceptance of EULA remain unchanged.

## Evidence and scope

The two supplied local logs (17:50 and 18:12/18:13 UTC, 11 October) show session,
character, store, mapping, tuning and player registration HTTP 200, followed by
public login requests. They do not show a CITY join, a presence WebSocket request,
a 409 character save, or a native host. The character data response already has
the documented 2.1.1 string shape; a successful player-register reply is also an
empty object in Mystic. Neither was changed to speculative content.

The exact cause of the observed return to login has NOT been proven. A server log
of HTTP 200 is not proof of bytes received or data accepted by the client.

## Actual server-side changes

1. The three supported tuning replies use a string code `OK` rather than null;
   their payload remains an object. Values are still upstream research defaults,
   NOT a recovered final 2.1.1 balance/configuration dataset.
2. POST /character acknowledges an exact retry of the current stored version
   and identical data without writing again. Older versions or changed data at
   the same version remain conflicts. Authentication, ownership, original
   string-only data and the root `{data: string}` reply remain. This is for lost
   responses/retries, not a claim that the logs contained a conflict. No guessed
   merge, progress advance, tutorial skip or character reset is added.
3. Optional `--presence`: the published static 2.1.1 presence route
   `ws://presence-prod.steelyard.ca/ws/{accountid}` upgrades with the `json`
   subprotocol and stays open. wsproto handles RFC 6455 masking, fragmentation,
   ping/pong and close. At most eight connections are accepted; receive sizes
   and event counts are bounded. Session revocation/expiry and server shutdown
   close owned sockets. No proprietary JSON updates, rewards, chat messages,
   host advertisements or gameplay replication are generated.
4. Presence admission requires an existing active local account session. If the
   peer provides a bearer, it must match the path account. The static source does
   not establish an HTTP bearer requirement, so missing-bearer admission to this
   data-free local socket is supported. This is NOT identity verification and
   grants no permission to any HTTP API. Browser Origin requests are refused.
   The entire service remains loopback-only and is not suitable for the Internet.
5. Correlated protocol diagnostics report prepared responses and actual socket
   writes separately. Bounded character versions/types and mapping counts show
   what was provided without raw IDs/tokens. Public requests are not mislabeled
   as an expired session. Automatic sanitized log files rotate at 2 MiB.
6. `--trace-client` drains the owned stock-client stdout and keeps only known
   error markers, not raw lines. Shipping builds may produce no output; this is
   reported as inconclusive. The external-mode report now uses null for counters
   it does not collect, rather than misleading zeros.

