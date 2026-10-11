# Post-login server/client test — post-login-20261011.2

This package contains BOTH matching Windows executables. It is an experimental
post-login compatibility update, NOT a native gameplay server and NOT a guarantee
that PLAY remains available. No proprietary game binary/content is included.

## What changed

- Real Epic and local Phoenix identifiers are no longer conflated. The existing
  unverified EOS-sub exchange now carries its own external ID in an expiring,
  private session field. `POST auth-prod/account/mapping` maps only this session's
  own IDs in either direction. `POST /accountinfo/public` now returns that same
  external ID in linkedAccounts, not the local account's hash. Lab accounts do
  not receive an invented Epic link. This fixes an actual mismatch in our code;
  its role in the observed return to login is not yet proven.
- The three explicitly named tuning routes `seasonal_event_schedule`,
  `huntpass_xp_config`, and `island_content_config` now have documented response
  shapes. They use the upstream research defaults; they are NOT a recovered copy
  of final official 2.1.1 balancing/progression. No bounty/daily/weekly response is
  invented, and unknown blobs still return bodyless 404.
- `POST store-prod/reconcile` returns a read-only LOCAL balance snapshot.
  `GET /balance` reads the same SQLite data. An additive local_store_balances table
  starts empty, so a new local account has zero currencies. No remote purchases,
  receipts, currency grants or inventory transactions are performed. Unknown
  transaction fields are rejected. refreshInventory=false means no mutation.
- `GET store-prod/creator` answers a negative empty affiliation state, rather
  than inventing a creator code. Its shape comes from the older source; the
  negative-state values remain a compatibility hypothesis for 2.1.1.
- Normal login tests default to TEN minutes instead of two/three minutes; the
  direct-map preview still has its old limits. The 5000 MiB sampled memory
  watchdog, owned-process-only shutdown and rollback remain. No hang detector,
  antivirus, packet encryption or global Windows trust control is disabled.
- The client checks the server's revision before editing game settings. External
  mode now reads only the PUBLIC CA, not the standalone server private key.
  The server logs UTC timestamps and distinct fixed tuning route labels.

## Source evidence and limits

Selected response-shape port: Mystic Paradox / Undaunted, AGPL-3.0-only with retained
Section 7 terms and notices. Pinned revision:
https://github.com/pranav158/Mystic-Paradox/blob/386302c1333fe3dfcb2baf176edc101e200f5081/ParadoxBackend/src/routes/tuning.ts
https://github.com/pranav158/Mystic-Paradox/blob/386302c1333fe3dfcb2baf176edc101e200f5081/ParadoxBackend/src/routes/store.ts

Identity mapping evidence: Revived social.md, source blob
4ea2ddf4444f0c018b109e6c0aaba15545ca6f64:
https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/social.md
It explicitly distinguishes 1.4.4 parser analysis from the observed 2.1.1 request.
Its documented root-and-wrapped accountMappings OBJECT form is retained here.

Read-only inspection of the privately provided exact 2.1.1 executable found the
three tuning blob names and their response field names, accountMappings,
srcAccountType, balances and refreshInventory as literals. Literal presence does
not verify control flow, parse success or client acceptance. The original file
was not executed, changed or sent to GitHub/CI.

The existing local session bearer remains mandatory for these handlers. The
external ID comes ONLY from the existing opt-in, unverified EOS-sub flow; this
is not cryptographic Epic authentication, not an offline-Epic bypass, and must
remain loopback-only. Unknown requested account IDs are omitted, not mapped to
the caller. All request bodies/IDs/tokens remain absent from server logs.

## Before starting

Close Dauntless and let the previous client test finish restoring. Stop the old
API server with Ctrl+C. Keep ALL AppData folders, databases, TLS files and backups.
Extract this package into a new folder, for example C:\ReawakenedPlayTest.
On first startup against the older schema, the server makes a uniquely named
SQLite backup BEFORE adding the new table. It does not delete or reset characters,
inventory or older databases. Do not run two server versions on the same database.
The executable is unsigned. Do not disable security software to run it.

## Run this client test

First administrator PowerShell:

```powershell
cd C:\ReawakenedPlayTest
.\Reawakened-Local-Server.exe --client-ports
```

The server must print `Server revision: post-login-20261011.2` and CLIENT PORTS READY.
It uses the SAME `%LOCALAPPDATA%\DauntlessReawakenedServer\players.sqlite3` and TLS
files as before. No new account password or Epic credentials are needed by the API.

Second administrator PowerShell:

```powershell
cd C:\ReawakenedPlayTest
.\Reawakened-Ramsgate-Preview.exe --run --normal-login --external-server --seconds 600
```

Check `Preview revision: post-login-20261011.2`, then type MAP to consent. Both
windows remain open. Complete the normal Epic sign-in in its own UI and accept
the game's EULA yourself. This package does not automatically accept terms.
If PLAY remains visible, try it once and observe the server window. A CITY request
can still wait/fail with NO_LOCAL_HOST_READY: there is no genuine gameplay host.
The test changes only the same journalled hosts entries, game CA and user config
as before. The original EXE is not modified. A time-limit stop is explicitly named.

After observing the result, close the game normally; do not wait ten minutes
unnecessarily. Wait for the client-runner's restoration confirmation before
stopping the server. If restoration is not confirmed, close the game and run:

```powershell
.\Reawakened-Ramsgate-Preview.exe --restore
```

The server's timestamped/redacted output is the backend evidence in external
mode, not the runner's zero local counters. Share only those route log lines and
the observed screen/PLAY behavior. Do not share private keys, whole AppData folders,
raw game/crash logs, databases or login codes. A 200 response is not proof that
the client parsed it, and pressing PLAY is not proof of a Ramsgate world join.

## Validation plan

Pure response/session/SQLite and timing tests are run locally. CI runs the full
repository tests, including a real loopback-TLS sequence that exchanges a synthetic
identity, creates a character, checks migration, reconcile, creator, public info,
mapping, tuning, registration and CITY waiting. Tests also cover token rejection,
other-account isolation, idempotent reads, old-schema backup and no fake host.
CI packages both executables and runs both self-tests without game files or user
profile writes. These are not real-client or gameplay tests. Consult the actual
CI result for this exact package before treating packaging as verified.
