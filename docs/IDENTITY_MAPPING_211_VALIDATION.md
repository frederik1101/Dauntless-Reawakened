# Identity mapping validation — 12 October 2026

Code commit: `7e8b77b32ccb4d986d410854c2df6c146d531ab5`.
Both packaged executables: `identity-mapping-20261012.5`.
Branch: work/login-continuity-211. Existing PR #5 remains unmerged.

## Actual Windows validation

The full decoded log of job `114854949877` in run `38262104190` was read.
The job checked out the code commit above and completed successfully:

```text
Ran 487 tests in 26.996s
OK
```

There were no skipped tests. The 27 added tests cover typed local identities,
conditional actor handling, case-sensitive opaque IDs versus 32-hex spelling,
account/character preservation, cross-account isolation, invalid claims,
revocation, safe metadata and explicit cancellation markers. The suite includes
an actual CA-verified loopback HTTPS sequence with two synthetic logins, mapping,
character saves and SQLite reopen. Neither Epic nor Dauntless ran in CI.

Both PyInstaller Windows builds completed. The packaged server self-test passed
API, local mapping, presence codec, character retry and typed identity mapping.
The matching preview passed its packaged self-test and CLI help. The workflow
verified these self-tests did not create the temporary LOCALAPPDATA profile.
This is not a live game-client or native gameplay-host test.

Local Linux source tests also passed: 487 tests, 8.784 seconds, no skips.
All 14 changed Git blob hashes were checked against the locally tested files.
The workflow and dependency requirements were not changed.

## Download and archive verification

[Paired Windows package](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38262104190/artifacts/11753116674)

- Artifact ID: 11753116674, Reawakened-Login-Continuity-Windows.
- Downloaded filename in the conversation: Reawakened-Identity-Mapping-Windows.zip.
- ZIP size: 27,191,518 bytes.
- ZIP SHA-256: `37797ae09255c25baf2187b5c0a25cdd4442098492e6c82e8ed8d99a6a6c06b6`.
- Server EXE SHA-256: `1a931ac231d27553d13375cbd26592305bfdb9c2b5367230e802d8702346270b`.
- Preview EXE SHA-256: `c51cce2221bf50b708c9fffd044e883c376f8cea3ae94de733e03209efd4a27e`.

The artifact was downloaded and checked against its GitHub SHA-256. Both EXE
hashes match SHA256SUMS.txt, BUILD-COMMIT.txt matches the tested commit, and all
14 changed source files match the tested source (normalizing CRLF only).
START-HERE.md has the new revision. The ZIP includes both EXEs, corresponding
source and the existing license notices. Windows binaries were not run in the
Linux working container; the packaged execution evidence is the Windows job log.

## What is not established

No real-client result exists for this revision yet. The earlier .4 client log
showed two empty mappings, but did not identify the requested namespace or prove
causation. The new actor projection is a conditional interoperability experiment,
not evidence that the affected client supplied that claim form. Tokens without
an actor retain the explicitly labelled legacy subject fallback.

Mystic's session-response fields are adapted; its different client/runtime,
unified identity and external-token echo are not copied. The original 2.1.1
executable, Epic sign-in and EULA acceptance remain unchanged. This is still an
explicit loopback-only UNVERIFIED identity experiment, not an Epic verifier.

A stable PLAY button, authenticated CITY request, real server join and controllable
Ramsgate character are separate milestones. This build does not establish any of
them or provide a native gameplay host. Preserve the existing database, TLS and
rollback backups; use the paired commands in LOGIN_CONTINUITY.md. Return the new
sanitized server log and filtered runner JSON, never tokens or raw client logs.
