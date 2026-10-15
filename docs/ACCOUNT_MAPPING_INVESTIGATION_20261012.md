# Account mapping investigation — 12 October 2026

This is an evidence update, NOT a login fix or a new client-test package.
Target: original Dauntless 2.1.1; paired revision login-continuity-20261011.4.
The new user-supplied sanitized server trace and runner JSON were reviewed.
No raw log, bearer token, account/character identifier, or private file is included.

## Observed in the actual client attempt

- The user deliberately cancelled a login while trying to close the game. Do not
  treat every generic login_operation_failed marker as a spontaneous server fault.
  The runner captured two native_login_callbacks_finished markers and five generic
  failures, but no operation name or cause. Callback completion is not login success.
- Two authenticated post-login sequences reached character reads/writes, store,
  tuning, player registration and account mapping. The API reported valid local
  sessions during these calls and recorded successful writes to the sockets.
  Socket writes do not prove receipt, parsing or acceptance by the game.
- The same anonymized account and character were used across both exchanges; the
  session alias rotated. Character versions progressed 4 -> 5 -> 6. The second
  GET returned version 5 from the first save. Both saves echoed the submitted
  data, and all top-level character data values were strings.
- The character blob contains only PlayerAccountProgressStep and RecentPlayers.
  Its progress state is EnteredRamsgate; this is stored data, NOT proof of a join.
  Required outer field types were present. This does not establish that the blob
  contains every field required by the later gameplay initialization.
- All three tuning envelopes now have string code OK. That change alone did not
  resolve the reported return to login. The progression configuration remains
  a minimal bootstrap, not authentic recovered final-version progression data.
- BOTH POST auth-prod/account/mapping replies reported requested_count=1,
  returned_count=0, all_requested_ids_mapped=false and HTTP 200. The response was
  written to the socket. The next observed HTTP requests were public status and
  maintenance calls. This is a repeatable mapping miss, NOT proven causation.
- There is no observed CITY join or presence WebSocket request in this trace.

## Code-level finding

At code commit dfad8d34b7d4b5bc3fb4218b128455d20eca8eb2:
backend/post_login.py _session stores the entire EOS-research subject as
linked_epic_id. backend/session_store.py unverified_subject extracts only the
JWT sub field. backend/post_login_contracts.py mapping_response then compares
requested IDs exactly with either that value or the local Phoenix account ID.
It omits all unmatched IDs. Thus an HTTP 200 with an empty mapping is entirely
possible even with a valid local session and external_binding_present=true.

The actual request source/type and identity relationships are NOT shown by the
current trace. The lookup could concern a different namespace, case/format, or
another account (for example a friend). Do not auto-bind requested IDs to the
caller merely to turn returned_count into one.

## Primary external context, distinct from user-log evidence

Epic's Auth documentation identifies an Auth ID token's sub as Epic Account ID.
Epic's Connect guide distinguishes the per-product Product User ID from the
Epic account used to log in. These are not interchangeable identifiers. This
supports investigating the unconditional linked_epic_id assumption; it does NOT
prove which token variant this particular client supplied.

- https://dev.epicgames.com/docs/epic-online-services/accounts-and-social/eos-epic-account-services/auth-interface/retrieve-and-validate-id-tokens?lang=en-US
- https://dev.epicgames.com/docs/epic-online-services/eos-fundamentals/connect-interface/connect-guide/log-in-with-an-epic-games-account

## Next targeted work

1. Preserve existing account/database lookup keys and character data. No reset or
   silent account merge as a diagnostic shortcut.
2. Add bounded, value-free identity relationship diagnostics: requested source
   enum, match-to-local-ID, match-to-existing-external-binding, and whether an
   external identity claim is available. Distinguish an unknown account from
   the wrong namespace. Do not dump JWTs, raw claims, URLs or identifiers.
3. Correct the external identity binding only from a documented token/identity
   contract tied to that same exchange. Keep the existing explicit loopback-only
   research limitation; this is still not cryptographic Epic verification.
4. Keep unknown account lookups omitted. Test cross-account isolation, both
   mapping directions, token rotation, persistence, and malformed inputs.
5. Refine client failure markers to preserve only allowlisted operation/reason
   enums and distinguish cancellation where explicit. Absence of a marker does
   not establish success.
6. Acceptance requires a real client result: valid own-account mapping where
   applicable, stable PLAY, then a separate CITY request. No genuine native
   gameplay host or controllable Ramsgate character is supplied by this work.

No runtime handlers were changed as part of this evidence-only commit.
