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
