# Local validation — 9 October 2026

Base revision: `01e06a90cc6f051a4c972a26ee5eabb5653f1f78`.

**50 tests passed; 0 failures; 0 skipped** in the local Linux execution environment for this change.
Command: `python -m unittest discover -s tests -v`.
Python: 3.13.5. OpenSSL: 3.5.5. Cryptography: 46.0.4.
`python -m compileall -q backend tools tests` also completed successfully.

This includes the 14 unchanged pure fixture/persistence/session regression tests, whose source files
were checked against their fetched GitHub blob hashes, and 36 HTTP, storage, session and TLS tests.

Coverage includes real IPv4 and IPv6 loopback TLS handshakes with a game-service SNI name; local session
exchange with a synthetic JWT; certificate trust rejection; token expiry/revocation; account isolation;
character creation, updates and database reopening; concurrent creation; strict JSON value types;
unknown-route empty responses; request-size and transfer-encoding rejection; and log redaction.

**Not tested here:** Windows execution, the user's installation, real Epic token validation, actual
Dauntless login, shared config isolation, Ramsgate, movement, inventory/gameplay or a hunt server.
The GitHub workflow now schedules Windows and Linux on Python 3.11 and 3.13. A workflow definition is
not a test result; inspect its actual run before claiming those environments passed.

The TLS negative test intentionally logs `transport-request-failed` when the client rejects the test
CA; that expected warning is not a test failure. Certificates are generated inside temporary directories
and deleted by the tests. No real account credentials, client files or external services were used.

## Verified GitHub Actions result for the transport baseline

The four jobs in [run 37979391572](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/37979391572)
completed successfully for commit `e1cbb01586cb89b4c22141e7903f4b0c8c1721c9`:
Ubuntu/Python 3.11, Windows/Python 3.11, Ubuntu/Python 3.13, Windows/Python 3.13.

The full Windows/Python 3.13 log (job `113985743136`) was also inspected: **50 tests passed, no skips**,
including both IPv4 and IPv6 TLS tests. That runner used Windows Server 2025, Python 3.13.15 and
cryptography 50.0.2. This verifies the hosted Windows test environment, **not** the user's Windows 11
installation or the Dauntless game. The four job statuses are not a claim that four real game clients ran.

## Follow-up: initial player-data reads

The follow-up change adds 22 tests, bringing the local suite to **72 tests passed, zero skipped**.
The full verbose run completed in 0.708s, followed by three successful repeated runs. Compilation with
`python -m compileall -q backend tools tests` also succeeded. Environment remains the local Linux
Python 3.13.5/OpenSSL 3.5.5/cryptography 46.0.4 combination described above.

New coverage: scoped inventory/loadout/progression reads, one-time inventory seed across database
reopening and concurrent requests, correct loadout scalar types, consistent slot counts, numeric-code
progression wrappers, all six documented initial Escalation-season shapes, and a real TLS request
sequence covering a synthetic research session through account, character, inventory, loadouts and save.

A log timing race found during reruns was fixed by recording the redacted audit entry before writing
the HTTP response. The expected untrusted-certificate rejection warning remains harmless.

The **72-test** version must have its own Actions run inspected; the earlier 50-test Windows run does
not establish results for the new code. Neither count demonstrates a complete game login or gameplay.
