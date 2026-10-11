# Read-only login failure report — 11 October 2026

## Why this change, not another guessed login handler

The newly supplied probe(1).log has 26 nonempty lines. It shows status/maintenance,
platform-features, 19 tracking heartbeat 404s and one unidentified mailbox 404.
It does NOT show account-link, login-queue POST, a local session exchange, character
requests or the newly ported inventory migration. The older probe.log progressed
through account-link and local session to character creation despite both heartbeat
and mailbox 404s. Consequently, neither their presence nor their count identifies
the cause of this new outcome. The process-local route fingerprints cannot be
compared across runs to establish that two mailbox URLs are identical.

The new log lacks timestamps, a build revision and a termination marker. It may
be incomplete, from a different attempt, or from an attempt that did not reach the
Phoenix session. We do not know which. There is no evidence that the user made a
mistake, that inventory migration regressed, or that adding an Unreal game-server
address would fix this pre-session boundary. Epic's browser UI and a successful
Phoenix/game login are different observations.

## Implemented

The packaged EXE now accepts exactly `--diagnose` as a read-only mode. It reads:

1. The current probe log in `%LOCALAPPDATA%/DauntlessReawakenedProbe/active/probe.log`.
2. Up to two most recently modified `.log` files in `%LOCALAPPDATA%/Archon/Saved/Logs`.

It prints JSON with fixed stage/error-marker labels, bounded counts, file size and
modification times. It does not print raw lines, local filenames, account IDs,
request/response bodies, headers, URLs, keys, login codes or tokens. It performs
no network requests, opens no game, changes no hosts/CA/config/database files and
needs no administrator privileges. It does not upload the report automatically.
The one-file executable may unpack its own runtime into a temporary directory,
as before; read-only refers to the diagnostic's game/user-data operations.

At most 2 MiB per selected file are read. UTF-8 and BOM-marked UTF-16 are supported;
tail truncation, missing files and scan limitations are reported. Symlink/reparse
paths and non-regular files are rejected. Output uses complete allowlisted markers
rather than a permissive `EOS_*` expression. No raw exception messages are returned.

Marker matches are clues, not validated authentication results or root causes.
Absence of a recognised marker does not prove absence of an error. The newest game
logs are NOT automatically proven to belong to the current probe attempt; compare
modification times and the user's observations. A matching `EOS_Success` alone is
not proof of game login. Missing game logs may mean that this retail client did not
write them; do not claim that the diagnostic enabled client logging.

## Usage: no additional login attempt needed

Close the previous test normally and wait for its restoration message. Download
the matching completed Windows artifact, extract it outside the game folder, keep
all state/backups, then use ordinary PowerShell from the extracted folder:

```powershell
.\Reawakened-Login-Probe.exe --diagnose
```

The revision line is `login-report-20261011.1`. Share this report, not raw game logs
or entire state folders. Do NOT run `--run` just to collect existing logs. If no
client log is found or no marker is recognised, the next useful observation is the
exact on-screen error and how/when the attempt ended, not a fabricated backend fix.

## Scope and tests

No backend response, token handling, launch method, timeout, inventory migration or
rollback behavior is changed by this commit. This is a diagnostic gap fix, NOT a
confirmed fix for the reported login failure. The prior inventory patch remains
pending evidence from a real-client request.

26 new tests passed locally, without skips, including representative sequences
matching the two supplied logs, redaction, bounded tail scans and non-mutation.
Only those new tests ran locally: direct GitHub cloning was unavailable. CI runs
the full repository suite before packaging. The build workflow additionally
executes the packaged `--diagnose` against a nonexistent temporary profile and
checks that no diagnostic files were created. Check the actual run/commit for the
full test result; do not substitute a successful compilation for client testing.

References for interpreting separate login phases:
- Epic EOS Auth callback result handling:
  https://dev.epicgames.com/docs/epic-online-services/accounts-and-social/eos-epic-account-services/auth-interface/auth-guide/log-in-with-the-dev-auth-tool
- Crossplay account consent/login outcomes:
  https://dev.epicgames.com/docs/epic-online-services/accounts-and-social/crossplay/crossplay-technical-overview
- Project's earlier evidence: LOGIN_ROUTE_DIAGNOSTICS.md and INVENTORY_MIGRATION_PORT.md.
