# Login continuity validation — 11 October 2026

Code commit: `dfad8d34b7d4b5bc3fb4218b128455d20eca8eb2`.
Revision of both executables: `login-continuity-20261011.4`.
Branch `work/login-continuity-211`, PR #5 into `work/ramsgate-map-preview`.
No merge to the previous branch or main was performed.

## Verified Windows build

The complete decoded log for job `114557672075`, run `38169079115`, was read.
It checked out the code commit above and reported:

```text
Ran 460 tests in 22.794s
OK
```

There were no skipped tests. The run includes real loopback TLS and independent
WebSocket frame tests, idle connection survival beyond five seconds, session
revocation, origin/capacity checks, shutdown, concurrent byte-identical character
save retries, and the existing rollback and redaction regressions. Identities
and subprocess output are synthetic; Dauntless and Epic were not run in CI.

PyInstaller built both Windows executables. The packaged server self-test passed
API, mapping, presence codec and character-retry checks. The packaged client
helper passed its imports, resource counter, marker filter and CLI help checks.
The self-tests did not create the temporary LOCALAPPDATA profile.

An earlier Windows run failed two new fixture tests: certificate generation first
initialized the Windows entropy provider after the test had mocked SystemRoot.
The fixture now generates real TLS material before mocking that environment.
No production cryptography, security checks or test assertions were disabled.
The subsequent full Windows run above passed. The local source suite also passed
460 tests after the fixture correction (10.303 seconds).

## Download and independent archive checks

[Paired Windows package](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38169079115/artifacts/11713800270)

- Artifact: `11713800270`, `Reawakened-Login-Continuity-Windows`.
- ZIP size: 27,164,590 bytes.
- ZIP SHA-256: `4b56a87eaca5a368f35b772cea409bbcc9623bd4c413269aa94b1f97e6c730c5`.
- Reawakened-Local-Server.exe SHA-256: `469703d1f0498a6d89fcef44d3497adab58b56d85f1310dac07d6f245a606564`.
- Reawakened-Ramsgate-Preview.exe SHA-256: `ac1d68fe5a8516fcab9f3ef0b4130cd1a8e39175c2ea5d5c937c2b355280e3c3`.

The actual artifact was downloaded. Its ZIP hash, BUILD-COMMIT.txt and both EXE
hashes were verified. Fifteen relevant bundled source files were compared with
the locally tested copies, normalizing CRLF only. Source, START-HERE.md and
license/notices are included. The Windows binaries were not executed in the
Linux working container; packaged execution evidence is the Windows CI log.

## Unverified acceptance criteria

There is no user-client result for this revision yet. Existing logs contain no
presence WebSocket request or character-save conflict, so those additions are
experiments/robustness improvements, not an established diagnosis. The string
code correction preserves the tuning payloads, which remain research defaults.
No proprietary update message or native gameplay host was invented.

A stable PLAY button, a CITY join request, a real server connection and a
controllable character are separate milestones. None is established by this CI
run. Presence transport does not provide gameplay replication or Ramsgate.

Run the paired package according to LOGIN_CONTINUITY.md. Keep the original
SQLite database, TLS keys and rollback backups. Share only sanitized server logs
and the runner result with filtered client markers, never complete AppData,
private keys, databases, sign-in codes or raw native logs.
