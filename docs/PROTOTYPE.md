# Local 2.1.1 contract prototype

This is an intentionally limited implementation of a few documented 2.1.1 response shapes, based on [Dauntless Revived's published research](https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/awakening-2-1-1.md).

It is **not** compatible with the actual game yet. In particular, it does not implement HTTPS, EOS, sessions, bearer validation, player account binding, the complete character data schema, dedicated servers or hunts. Do not redirect the game client to this server.

## Requirements

Python 3.10+; no third-party dependencies.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Start the prototype

```powershell
python -m backend.server
```

In another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/login-queue-prod/login
```

Stop with Ctrl+C. Server listens on 127.0.0.1 only and stores test data in memory.

## Next implementation work

Compare the full published 2.1.1 backend contract, define request/response schemas and build a complete isolated integration-test harness before attempting any client redirection. Verify licenses and attribution before incorporating upstream source code.
