# Login route diagnostic validation — 11 October 2026

Code commit: `388f3259422c26123a17b13ba11da242969cd333`.

## Local checks

15 tests in `tests/test_request_diagnostics.py` passed locally without skips.
All changed Python files passed syntax compilation. The two copied baseline modules
(server and login port) were checked against the Git blob hashes before modification.
The full integration suite was executed on GitHub's Windows runner, not locally;
this environment could not clone GitHub directly, so repository access used the
connected GitHub tools. No proprietary game client was available in the test environment.

## Windows CI verification

[Build run 38119053020](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38119053020)
completed successfully. The actual log of job `114409815415` was read. It shows:

```text
Ran 144 tests in 12.015s
OK
```

No skipped tests are listed. This includes the synthetic TLS sequence through the
candidate EOS account-link alias, locally issued session, account-info and character.
It also includes privacy tests verifying that synthetic tokens, names, account IDs
and character IDs do not appear in the request log.

The workflow built the Windows EXE and successfully ran its packaged `--about`:

```text
Probe revision: login-route-diagnostics-20261011.1
```

The older general `0.3` banner is still printed below the revision. The revision
line above distinguishes this packaged build. Packaged startup is not a test of
the privileged game-launch/rollback path on a user's installation.

## Artifact

[Reawakened-Login-Probe-Windows](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38119053020/artifacts/11694668535)

- Artifact ID: `11694668535`
- ZIP size: 13,446,983 bytes
- ZIP SHA256: `6c070b2de1c00274849c0439bf784cdad125af385e6698a3b63e934a5023b1f4`
- Source revision: the code commit above; `Corresponding-Source.zip` is included.
- Executable hash is in `SHA256SUMS.txt`. The ZIP digest is not the EXE digest.
- The program is not code-signed. Do not disable security software to run it.

## What is NOT verified

No successful Dauntless client login, no verified Epic authentication, no controllable
player and no UE5 hunt server. The user's old `unknown 404` log does not identify its
failed URLs. The EOS link alias remains a candidate, and the next real-client log is
needed to establish whether it is used and whether the login progresses.

See [the investigation and user test instructions](LOGIN_ROUTE_DIAGNOSTICS.md).
