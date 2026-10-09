# Verified validation — 9 October 2026

Latest tested code: **`a1246084ab24d7b684878e32f790c647e1963d7b`**.

**72 tests passed locally, zero failures, zero skipped. All four GitHub Actions jobs also passed.**
These are backend/transport/contract tests, NOT successful Dauntless client-login or gameplay tests.

## Local execution

Command: `python -m unittest discover -s tests -v`.
Environment: Linux, Python 3.13.5, OpenSSL 3.5.5, cryptography 46.0.4.
The full verbose run completed in 0.708s. Three additional consecutive full runs passed.
`python -m compileall -q backend tools tests` also completed successfully.

The suite contains 14 unchanged legacy fixture/persistence/session regression tests, 36 new transport,
HTTP, storage and session tests, and 22 initial player-data tests. The uploaded code blobs were checked
against the locally tested files' Git object hashes.

## GitHub Actions — actual results, not just a workflow definition

[Run 37980878135](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/37980878135)
ran against the code commit above. The job statuses were fetched after completion:

| Job | Job ID | Result |
| --- | --- | --- |
| Windows / Python 3.13 | 113990763017 | Success |
| Ubuntu / Python 3.13 | 113990763098 | Success |
| Ubuntu / Python 3.11 | 113990763201 | Success |
| Windows / Python 3.11 | 113990763328 | Success |

The full **Windows/Python 3.13** log was additionally inspected. It reports **72 tests passed in
28.842s, no skips**, including IPv4/IPv6 HTTPS and the added session-to-player-data TLS sequence.
That runner used Windows Server 2025, Python 3.13.15 and cryptography 50.0.2.
This verifies a hosted Windows test environment, not the user's Windows 11 machine or the game.
The other three completed job statuses were inspected; their full logs were not individually reviewed.

## What the tests cover

- Actual IPv4 and IPv6 loopback TLS handshakes, game-service SNI and rejection of an untrusted CA.
- Host routing, case-insensitive local session bearers, expiry, revocation and account isolation.
- Character creation, strict data types, exact client update versions, conflict rejection and database reopening.
- Concurrent character creation, scoped inventory reads and one-time starter inventory across concurrent reads/restarts.
- Typed loadout slot counts, the documented empty-loadout active index, and initial progression read shapes.
- A real TLS request sequence through a synthetic research session, account-info, character creation,
  inventory, loadout reads and a character save/read. This deliberately omits the still-unknown early login calls.
- Unknown-route bodyless responses, request-size limits, transfer-encoding rejection and log redaction.

A repeated run exposed a timing race: the handler originally sent the HTTP response before writing its
redacted audit entry. Logging now precedes the response, and the repeated full runs passed afterward.

The TLS negative test intentionally logs `transport-request-failed` when the client rejects the test
CA. That expected warning is not a test failure. Certificates are generated inside temporary directories
and deleted by the tests. No real Epic credentials, game files or external game services were used.

## Not established by these tests

Actual Epic authentication (the optional JWT-subject mode does not verify tokens), complete Dauntless
login, Windows client/DNS/certificate/config isolation, Ramsgate, a controllable pawn, equipped gear,
inventory transactions, crafting, XP, saved loadout changes, hunts or a compatible UE5 game server.
See [connection blockers](CONNECTION_BASELINE.md) and [player-data read limitations](PLAYER_DATA_READS.md).

## Prior transport baseline

Code `e1cbb01586cb89b4c22141e7903f4b0c8c1721c9` had 50 passing local tests.
Its [Actions run 37979391572](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/37979391572)
also passed all four matrix jobs. Windows/Python 3.13 job `113985743136` was inspected and reported
50 tests, no skips. That earlier result is retained for traceability, not substituted for the newer run.
