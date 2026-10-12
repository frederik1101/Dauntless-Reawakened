# Character/login regression investigation — 12 October 2026

## Verified observations from user-supplied diagnostics
Two separate real-client runs reached the local Phoenix session and character reads, but the client subsequently reported login failure with character/compatibility markers. The newer run with an empty database:

1. GET /character returned an empty array (2 bytes).
2. PUT /character received 22 bytes, reported no characterId, data or updateVersion fields and returned HTTP 200 with id/name.
3. GET /character returned one character, updateVersion 0, nine string-valued fields including AppearanceData, with PlayerAccountProgressStep=EnteredRamsgate.
4. The client returned to login, not a process crash.

The older run had an existing character, updateVersion 7 and eight fields (no AppearanceData), but failed at the same broad client stage. This means neither a pre-existing DB record nor AppearanceData presence alone explains the failure. HTTP 200 proves only delivery, not acceptance.

## Code provenance mismatch (actionable)
The main-branch `backend/application.py` handles PUT /character by calling `database.create(account, data['name'], character_seed())`.
`backend/protocol_211.py::character_seed()` returns ONLY `{"PlayerAccountProgressStep":"EnteredRamsgate"}`.
`backend/database.py::create()` initializes version 0.

**Therefore the nine-field response observed from the user's standalone Reawakened-Local-Server.exe cannot be attributed solely to this baseline seed function.** The actual source/revision for that newer executable must be located and inspected before changing production behavior. Do not assert a specific root cause from the baseline repository.

## Hypotheses to test, not assumptions
- Client rejects a nested JSON value type, character progress state or version.
- An identity/session binding or later initial-data load fails after GET /character.
- A client-side compatibility check is independent of the character response.

## Next evidence gate
1. Identify the exact Git commit and source that produced Reawakened-Local-Server.exe and its `--mystic-profile` implementation.
2. Compare the source-produced response schemas with the observed nine-field and eight-field diagnostics.
3. Preserve the exact client failure category safely (allowlisted error code; no raw Epic tokens, account IDs or full stdout).
4. Change one behavior at a time; add a regression test for that change.
5. Rebuild and test on Windows only after the discrepancy is resolved.

## Scope
`tests/test_character_login_regression.py` verifies the baseline application's empty-create-read sequence. It does NOT validate the proprietary 2.1.1 client or fix the newer executable. No profile schema or authentication semantics were changed.
