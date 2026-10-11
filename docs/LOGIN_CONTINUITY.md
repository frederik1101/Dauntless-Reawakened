# Local login-continuity test — login-continuity-20261011.4

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

## Windows test after the paired build is green

Close the old game, wait for its runner to confirm restoration, and stop the old
server. Preserve ALL AppData folders, databases, TLS files and backups. Extract
this ZIP into `C:\ReawakenedContinuityTest`. The same `players.sqlite3` and existing
certificates in `%LOCALAPPDATA%\DauntlessReawakenedServer` are reused. Do not run
multiple server versions on that database. No new schema is added by this revision.

Administrator PowerShell 1:

```powershell
cd C:\ReawakenedContinuityTest
.\Reawakened-Local-Server.exe --client-ports --diagnostic --presence
```

Check `Server revision: login-continuity-20261011.4` and `CLIENT PORTS READY`.
The presence experiment is optional: omit `--presence` for the comparison run;
the rest of the server corrections and diagnostics are unchanged.

Administrator PowerShell 2:

```powershell
cd C:\ReawakenedContinuityTest
.\Reawakened-Ramsgate-Preview.exe --run --normal-login --external-server --trace-client --seconds 600
```

Check the SAME revision, type MAP and complete the usual Epic sign-in yourself.
Keep both consoles open. If PLAY stays visible, click once. There is no native
host: matchmaking may wait or fail with NO_LOCAL_HOST_READY. Do not confuse this
with PLAY/login success or a rendered/joined Ramsgate world.

After seeing the outcome, close the game normally. Wait for restoration before
stopping the server with Ctrl+C. If restoration is not confirmed, close the game
and use the matching executable:

```powershell
.\Reawakened-Ramsgate-Preview.exe --restore
```

Share the sanitized server log printed at startup and this runner result only:

```powershell
Get-Content "$env:LOCALAPPDATA\DauntlessReawakenedMapTest\active\map-preview-result.json"
```

Do not upload databases, TLS private keys, the complete state folder, raw native
logs or sign-in codes. If there are no PRESENCE events, that experiment was not
used by the client; do not infer that it repaired login. If there are no client
markers, the collector is inconclusive, not evidence of a successful parse.

## Validation boundaries

The source suite tests real loopback HTTP/TLS and WebSocket handshakes, a socket
remaining idle beyond the old five-second HTTP timeout, ping/pong, fragmentation,
invalid/masked frames, session/capacity/origin controls and shutdown, plus concurrent
identical character saves and the previous rollback and privacy regressions.
There are no game-client files in CI. No genuine Epic or native game-host session
is created by tests. Check the exact Actions run and BUILD-COMMIT.txt for the
Windows packaging result; passing tests do not establish a fixed in-game reset.

## Primary sources / research vs implementation

- The user's redacted route logs: observations summarized above, not published.
- 2.1.1 presence and character shapes: mixutin/dauntless-revived,
  docs/findings/backend-contract.md, blob 55cdc3b6cd0ac091ab9cb27ddb696b82cfd265a2.
  https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md
  Presence is explicitly STATIC and not opened in that project's 2.1.1 tests.
- Mystic register acknowledgement: commit 386302c1333fe3dfcb2baf176edc101e200f5081,
  ParadoxBackend/src/routes/matchmaking.ts. It sends an empty object; no host-ready
  state is inferred. Existing AGPL and additional terms are retained.
- WebSocket handshake/control frames: https://www.rfc-editor.org/rfc/rfc6455.html
- wsproto 1.3.2 API: https://python-hyper.org/projects/wsproto/en/stable/api.html
- Byte-identical retry acknowledgement is an explicit local compatibility choice,
  not claimed as a captured official server response on duplicate writes.
