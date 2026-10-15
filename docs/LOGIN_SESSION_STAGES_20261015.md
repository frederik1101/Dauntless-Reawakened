# Within-run login session analysis — 15 October 2026

This is an offline, privacy-safe extension of `tools/login_stage_diagnostics.py`.
It does **not** alter Dauntless, HTTP responses, account bindings, SQLite,
Epic login, TLS certificates or the reversible Windows launcher.

## Observed regression and ambiguity

Two sanitized 12 October client traces differed: an older run with an existing
two-field character continued to inventory migration, character save and store
calls; a newer run created a version-zero nine-field character and stopped
after its populated GET. Neither trace showed a CITY join. These are **server
socket writes**, not evidence of client acceptance. The older log had two
local research exchanges, so a global furthest-stage report can inadvertently
combine independent attempts.

## Added analysis

`session_flows` groups only valid-local-session PROTOCOL_TRACE records by a
random process-HMAC session alias, with a 16-session cap. It reports ordered,
bounded per-session stages, character GET/PUT counts, categories of subsequent
HTTP-200 routes and the first observed HTTP 4xx/5xx after the last populated
GET. No aliases, identities, raw paths, tokens, character data or user-specific
timestamps are emitted. Only paired `written_to_socket` records count.

Research exchanges have no local session alias and **cannot** be assigned to
these session flows. Missing aliases are explicitly reported as unlinked.
Interleaved or parallel requests, unknown 404 heartbeats and client stdout
markers cannot by themselves prove a root cause. Process keys change between
server runs; no cross-run identity correlation or Epic verification is claimed.
The existing global `stage` field is deliberately unchanged for compatibility.

Seven isolated synthetic tests plus one integration test with the existing
log analyzer exercise separation of interleaved sessions, status failures,
redaction, missing aliases, limits and socket-write gates. Actual CI results
must be read from the specific code commit. No new game-client test is
required or claimed, and no Windows package is needed just for these diagnostics.
