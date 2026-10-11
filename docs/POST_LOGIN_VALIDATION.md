# Post-login package validation — 11 October 2026

Code commit: `cce3eff45b877cb1646a263ed62f21ec6b6cbecb`.
Branch: `work/ramsgate-map-preview`, PR #4. No main/native branch update.
Revision printed by BOTH executables: `post-login-20261011.2`.

## What actually ran

The full decoded Windows log of build job `114531251117` in
[run 38160177964](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38160177964)
was read. The job checked out the exact code commit above (not a different PR merge).
It reported:

```text
Ran 396 tests in 15.308s
OK
```

No skipped tests are listed. This includes the real loopback-TLS post-login
sequence, the four old-schema/backup tests and existing regression tests. Synthetic
identities are used; none of these tests starts Dauntless, connects to Epic or
runs an Unreal host. The TLS test verifies the generated CA rather than disabling
TLS verification, and checks that IDs/tokens/body secrets do not enter the logs.

PyInstaller successfully built BOTH Reawakened-Local-Server.exe and
Reawakened-Ramsgate-Preview.exe. Both packaged self-tests returned success, including
server-side identity mapping and the Windows process-resource counter query.
The packaged client --help also passed. The workflow checked that these self-tests
did not create the temporary LOCALAPPDATA profile.

Locally, 34 contract/session/SQLite tests and five timing tests passed without
skips. The new/modified source was syntax-checked. Full repository integration ran
on GitHub CI, not locally: github.com could not be resolved from that container.
Selected published source blob hashes were compared with the local tested copies,
including map_preview_support.py, ramsgate_map_preview.py and post_login_contracts.py.
No proprietary executable was executed, modified or uploaded to GitHub.

## Artifact verified

[Download matching server and client test](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38160177964/artifacts/11709809720)

- Artifact ID: `11709809720`.
- Name: `Reawakened-Post-Login-Test-Windows`.
- ZIP size: 26,847,473 bytes.
- ZIP SHA-256: `9db6fa6dd16ddb545ab5c0bf0b8819c3d0ea65743ad185e628eec5f66ce794d3`.
- Metadata reported not expired when checked; retention ends 25 October 2026.
- Includes both executables, matching source ZIP, START-HERE.md, license/notices,
  BUILD-COMMIT.txt and separate executable hashes. ZIP hash is not an EXE hash.

## Remaining acceptance test

No actual-client result exists for this new revision yet. The prior user log
reached session, character, inventory migration and player registration before
returning to login, with post-login mapping/store/tuning 404s. This motivated the
implementation but does not prove which call caused the return to login.

The new mapping preserves the distinction between an unverified external identity
and the local account. Tuning values come from upstream research defaults, not
recovered final 2.1.1 balance data. Empty creator affiliation is a compatibility
hypothesis. Store reconciliation is only a read-only local SQL balance snapshot,
not external purchase verification. These response semantics need client evidence.

The new ten-minute normal-login budget prevents the old three-minute wrapper limit
from cutting short the test; it is not claimed to fix the in-game sign-out.
The genuine native host remains absent. PLAY remaining visible, PLAY clicked,
matchmaking requested, client joined and controllable player are distinct milestones.
Do not claim one from another or advertise a fabricated gameplay destination.

Use the paired package and instructions in POST_LOGIN_FIXES.md. Preserve AppData,
TLS files and backups, close old tools first, and wait for journalled restoration
before stopping the standalone server. Send only the redacted server route log and
observed PLAY behavior, not raw game logs, private data or whole profile folders.
