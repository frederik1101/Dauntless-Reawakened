# Local CITY candidate routing and native-host handoff

## Implemented, but not a running gameplay server

`RamsgateApplication` is a separate opt-in subclass of the existing login backend.
It handles `POST /candidate/player/register`, `POST /candidate/join`,
`GET /candidate/status` and `DELETE /candidate` or `/candidate/leave` on mm2-prod.
Use it with the existing loopback HTTP/TLS transport. The current user login probe
and main branch are not switched to this experiment by this change.

The route handlers require TLS, a valid locally issued session and exactly one
owned character. They do not create a character or pick an arbitrary first one.
Only CITY is accepted; a hunt is never silently changed into Ramsgate. Account
identity is derived from the session and checked against playerId. The existing
EOS-sub research option is still not cryptographic Epic authentication.

The broker stores bounded per-session candidates, deduplicates repeated joins,
supports polling/cancellation, and times out when no host becomes available.
Candidates and requests never turn raw client gameArgs into launch arguments.
Account IDs, session tokens and incoming request bodies are not added to logs.

## Host readiness is not a player-controlled switch

`HostProvider` is an internal interface for a future authoritative owned-process
supervisor, not an HTTP registration endpoint. It must reserve real admission to
a specific live native process and generation, then revalidate it on every poll.
An assignment must match the requested build, exact Ramsgate map, local numeric
port and short monotonic lease. Restarted generations, expired leases, changed
endpoints, provider errors and dead hosts remove the offered address.

**The only production provider currently shipped is UnavailableHost.** With it,
join/status returns MATCHING without serverInfo, then a bounded FAILED state.
Only test fixtures provide synthetic ready assignments. No environment variable,
manual ready flag, successful HTTP check or arbitrary UDP socket can create a
production ready host. The provider's liveness/admission evidence has not yet been
implemented, so this change cannot itself send a real player into Ramsgate.

When a future provider genuinely supplies readiness, the broker forms IN_PROGRESS
with isNewMatchmaker=true, playerStates keyed by the authenticated account, and
serverInfo containing exactly gameSessionId, instanceId, host, numeric port and
gameArgs. The supported host is literal 127.0.0.1. The same generation must remain
live; an old destination is never recycled after restart. Cancel releases the
reservation; provider release must be idempotent. Calls to provider methods must
be bounded/nonblocking; the broker is not a process scheduler.

## Protocol evidence and remaining uncertainty

[Revived's 2.1.1 contract](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md)
(source blob 55cdc3b6cd0ac091ab9cb27ddb696b82cfd265a2) documents candidate paths,
status values, playerStates, numeric port, and the five-field serverInfo. It marks
the 2.1.1 status envelope as unresolved. This implementation deliberately chooses
the flat candidate form as an explicit experiment, NOT a proven 2.1.1 response.
The register acknowledgement is informed by the older
[Mystic Paradox route](https://github.com/pranav158/Mystic-Paradox/blob/fcf915cb918edbe9f030d03b62c94f4879dc655a/ParadoxBackend/src/routes/matchmaking.ts).
It is not represented as a live-tested upstream 2.1.1 port.

The real client's travel URL also needs ticket/game-session/encryption handling.
Tickets do not belong inside serverInfo. This change does not implement key
issue/consume, ticket redemption, native playerjoined, QoS regions or replication.
It does not copy the older upstream fallback that selects the most recently
issued player's encryption key. No authentication/encryption is disabled.

## Validation

26 broker tests ran locally without skips. They include a default missing host,
retries, ownership, cancellation, capacity, timeouts, dead/restarted generations,
lease and loopback restrictions, concurrency and secret-safe exceptions.
18 additional application/TLS tests run in CI with the existing database and
transport. The TLS sequence is session -> account -> character -> register ->
join/wait -> synthetic offer -> cancel; it never starts a game server or dials a
Unreal port. Source syntax was compiled locally; full old dependencies were not
cloned in that environment. Read exact CI results before claiming their outcome.

For the actual next runtime step see [native world handoff](NATIVE_211_WORLD_HANDOFF.md)
and issue #1 / draft PR #2. No new player-facing test package is announced here.
