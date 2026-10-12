# 2.1.1 identity-mapping test — identity-mapping-20261012.5

Experimental LOCAL API, not an authenticated Epic service or a native Ramsgate
host. Intended to test the repeated empty account-mapping result after login.
No successful PLAY, CITY join or controllable player is established by unit tests.

## What the actual .4 trace established

The user's two post-login attempts each asked for one account mapping and received
zero, followed by public login-menu requests. Local sessions and character
save/read/version continuity worked at the HTTP layer. Responses were written to
sockets; that is not evidence of client acceptance. The trace did not identify
which external namespace was requested or whether this was the player's own ID.
The user cancelled later login attempts, so generic failure counts do not identify
the original reset's cause. No raw user logs are included in the repository.

## Changes made for this test

- Keep the exact existing `eos-research:<sub>` database key. Do NOT derive a new
  local account from the corrected external ID, merge accounts, or reset data.
- Parse one submitted research token with bounded, duplicate-key-rejecting JSON.
  Project `sub` separately from a Connect-shaped `act` object. The supported
  experimental actor form is `{eat:"epicgames",eaid:"<external account>"}`.
  This is a conditional interoperability case, not a finding that the user's
  token contains those claims. Its occurrence must be established in the next
  value-free identity_projection trace. An unusable or non-Epic actor does not
  silently turn a product subject into an Epic account.
- Tokens without an actor retain the legacy subject fallback to avoid inventing
  a new identity on existing installs. This fallback is labelled `legacy_subject`
  unless it has the expected Auth issuer shape. Neither label verifies a token.
- Mapping/public-account replies refer to the same selected external binding.
  Only a session's own binding is mapped; arbitrary requested IDs are not adopted.
  Hex IDs of exactly 32 characters compare without case. Other opaque IDs remain
  case-sensitive; no trimming, prefix removal or UUID rewriting is performed.
- Add Mystic's session-envelope compatibility fields `error_code:null` and the
  legacy `sessionToken` alias alongside lowercase `sessiontoken`. These contain
  our existing local token, not the supplied Epic credential. We do not copy
  Mystic's shared Epic/Phoenix token or its unified account namespace.
- Add source and relationship counts to mapping traces, with no raw IDs/claims.
  The diagnostic distinguishes matching the local account, the external binding,
  the exchange subject, and an unrecognised/unavailable relationship.
- Add exact client error literals for an empty mapping, unavailable user account,
  attribute-resolution failures and login-time read/write outcomes. Recognise a
  cancellation only if the logged error explicitly says so. No raw stdout is kept.

## Source distinctions

Mystic source reviewed: `ParadoxBackend/src/routes/login.ts`, blob
`3b3f95af6ac1a24f542c33a06d8f65dac83477b6`. It targets another game version and
uses its own launcher-issued identity. It is a reference, not a verified 2.1.1
implementation. Account-mapping response envelope follows Revived's
`docs/findings/social.md`, blob `4ea2ddf4444f0c018b109e6c0aaba15545ca6f64`:
response parser evidence is 1.4.4, request evidence also includes 2.1.1.

Epic's official Auth token documentation establishes `sub` as Epic Account ID
for Auth ID tokens. Its Connect guide distinguishes the per-product Product User
ID from that Epic account. These sources support keeping the namespaces separate;
they do NOT establish which token shape the affected client supplied. The
Connect-shaped actor adapter above remains an explicit experimental contract
until a real-client trace confirms it. No claim of cryptographic verification is
made. Public-key validation, expected audience/issuer and expiry checks are needed
for a deployable authentication service; this is not that service.

- https://github.com/pranav158/Mystic-Paradox/blob/main/ParadoxBackend/src/routes/login.ts
- https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/social.md
- https://dev.epicgames.com/docs/epic-online-services/accounts-and-social/eos-epic-account-services/auth-interface/retrieve-and-validate-id-tokens?lang=en-US
- https://dev.epicgames.com/docs/epic-online-services/eos-fundamentals/connect-interface/connect-guide/log-in-with-an-epic-games-account

## Testing and limits

Synthetic tests exercise two differently named identities, own-account mapping
both directions, uppercase hex, unchanged database keys, character persistence,
invalid/ambiguous claims, Origin/TLS/opt-in gates, token rotation and revocation,
value-free diagnostics and cancellation markers. An actual TLS integration test
uses temporary certificates/SQLite and never contacts Epic or launches Dauntless.
The packaged self-test exercises the new parser and mapping without profile writes.
The build workflow itself is unchanged; this does not retry the previously blocked
packaged-listener smoke work or any native bootstrap publication.

Still missing: proof that these changes stop Updating Game Data -> login in the
real client, authentic full 2.1.1 game data, and the native gameplay host. Existing
unknown-route errors, no-host matchmaking behavior and ownership checks remain.
