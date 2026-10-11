# Login report validation — 11 October 2026

Code commit: `14d898adaa8accb4f532a0d25085241c81778d3d`.
This update adds diagnostics, not a confirmed fix for the user's login failure.
No backend response, game launch method or rollback behavior was changed.

## Verified locally

26 new tests in tests/test_login_report.py passed without skips. The uploaded
report module and tests were checked against their Git blob hashes:

- tools/login_report.py: 8929cdc6ea039fde6c513c7fd8a04f07c7923497
- tests/test_login_report.py: 53578e34c82b5bccae24a4e38e22c33d72be7e62

Both supplied probe logs were also processed locally. The latest log contains no
local-session response; the older log does. No raw user logs were committed.
The full existing integration suite did not run locally: GitHub could not be cloned
from this container. Repository operations used the connected GitHub tools.

## Verified on Windows CI

[Build run 38122351850](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38122351850)
completed successfully. The actual log of job 114419519146 was read:

```text
Ran 211 tests in 8.741s
OK
```

No skips were reported. Packaging succeeded, and the built EXE executed both
--about and --diagnose. The latter used a deliberately nonexistent temporary
LOCALAPPDATA profile, emitted read_only=true and not_found, and did not create
that profile. This is a packaged command smoke test, not a real client login.

## Artifact

[Windows diagnostic package](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38122351850/artifacts/11695069879)

- Artifact ID: 11695069879
- ZIP size: 13,488,831 bytes
- ZIP SHA256: c5000527bd4f337c0064419e31147a006684de93a400b5ad4bd9c0f6859efede
- Revision: login-report-20261011.1
- Includes EXE, matching corresponding source, notices/license, instructions and EXE hash list.
- Not code-signed. Do not disable security software. The ZIP hash is not the EXE hash.

## Next observation and limits

Run --diagnose only, from normal PowerShell after the previous probe is restored.
No further login attempt is needed to inspect already-existing logs. Share only
the filtered report. The client log folder may not exist in this retail build;
missing logs or no recognised marker are inconclusive, not a successful login.
The two newest client logs are selected by modification time, not proven correlated
to the current probe. Match timestamps with user observations before making claims.
See LOGIN_REPORT.md for scan limits and the exact read-only behavior.
