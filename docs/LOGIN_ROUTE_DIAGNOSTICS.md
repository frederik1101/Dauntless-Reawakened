# Login-loop investigation — 11 October 2026

**No successful Dauntless login is claimed.** This is a targeted candidate fix plus
privacy-preserving diagnostics, not proof that the login loop is solved.

## What the user's real-client log established

The probe received status-banner, experimental-maintenance and platform-features
requests and returned HTTP 200. Many POSTs and two GETs returned bodyless 404 with
only `route=unknown`. The log does not contain a recognised account-link, session
exchange, account-info or character request. Epic's consent UI was displayed, but
that is separate from completing the local Phoenix session.

We cannot recover the missing URLs from these old lines. In particular, repeated
POSTs could be telemetry/heartbeats, login requests or something else. Their count
alone is not evidence of the cause of the login loop. A 200 response likewise does
not prove the game parsed or accepted its contents.

## Narrow candidate correction

The existing default application matches only `/account/link/epic/{id}`. Revived's
[2.1.1 contract](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md)
(source blob `55cdc3b6cd0ac091ab9cb27ddb696b82cfd265a2`) describes the template
`/account/link/{service}/{accountid}` and names `epiceos` for the newer **session**
provider. This makes an EOS account-link alias worth testing; it does **not** prove
the unidentified GET used it. The separate standalone notes use `epic` for linking.

The opt-in `LoginPortApplication` now also recognises exactly
`GET /account/link/epiceos/{id}` over TLS, returning the existing wrapped link shape.
It is logged as `candidate-account-link-epiceos`. Unknown providers, malformed IDs,
extra segments and wrong methods still fail. The baseline `Application` is unchanged.
No new token shortcut, automatic account access or successful matchmaking is added.

The port retains the [Mystic Paradox source reference](https://github.com/pranav158/Mystic-Paradox/blob/fd795c6434abd63872f4af277c90747239f1ed40/ParadoxBackend/src/routes/login.ts),
license, additional terms and notices. The alias is our research addition, not an
upstream fix or an upstream-tested 2.1.1 feature.

## New log format

For example, a request using the candidate alias would appear as:

```text
INFO method=GET route=candidate-account-link-epiceos status=200 service=gamesession-prod endpoint=/account/link/epiceos/{id} transport=https route_key=-
```

A heartbeat, if that is what a POST actually is, can now be distinguished:

```text
INFO method=POST route=unknown status=404 service=tracking-prod endpoint=/heartbeat transport=https route_key=-
```

These are **examples, not observed user log lines**. Diagnostic recognition never
changes a response: classifying a heartbeat does not make it return 200.

Only fixed service labels and complete allowlisted route templates are output.
Variable slots are redacted even if an ID happens to equal a known route word.
Queries, raw headers, request/response bodies, credentials, names and account IDs
are not logged. Unrecognised paths remain `<redacted>` with a process-local keyed
fingerprint so repeats can be counted. The key is random and never written; these
fingerprints cannot be compared between separate probe processes. No raw path is
written to a sidecar or retained by the classifier.

HTTP vs HTTPS is recorded explicitly. Invalid/foreign hosts get fixed redacted
labels. Trailing slashes are visible as a property of a recognised template;
the routing itself does not silently normalise them.

## Tests and scope

New pure tests cover the narrow route predicate, identifier/query redaction,
unknown providers, encoded fields, control characters, fingerprints and service
separation. Integration tests cover HTTP 404 preservation, TLS-only alias handling,
unchanged baseline behaviour, absence of an authentication bypass and a synthetic
TLS flow through alias -> session -> account -> character. A synthetic token test
is not validation against Epic or the proprietary client. CI runs the entire existing
suite before packaging the EXE. Consult the run for the exact commit you download.

## User test

The new packaged console entry prints `login-route-diagnostics-20261011.1`.
Use the completed artifact for this change, not an older green run. Retain the
existing probe state/backups and ensure the preceding probe was restored. Close
Dauntless, then run PowerShell as administrator from the extracted package:

```powershell
.\Reawakened-Login-Probe.exe --run --experimental-maintenance --seconds 600
```

Read the temporary hosts/game-CA/config changes and type `TEST` to consent. Keep the
console open. After closing the game, wait for the restoration message. Upload only
`%LOCALAPPDATA%\DauntlessReawakenedProbe\active\probe.log`, never the whole state folder.
If cleanup is not confirmed, close the game and use `--restore` before another run.
See [LOGIN_PROBE.md](LOGIN_PROBE.md) for the rollback process and limitations.

Look for account-link then session-exchange, account-info and character requests.
If it still loops, the service/template/status fields identify the next observed
failure. Do not replace arbitrary 404s with empty successful objects.

Implementation references: [Python URL parsing security](https://docs.python.org/3/library/urllib.parse.html#url-parsing-security)
and [HTTP server logging](https://docs.python.org/3/library/http.server.html#http.server.BaseHTTPRequestHandler.log_message).
