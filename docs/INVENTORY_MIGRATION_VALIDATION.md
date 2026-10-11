# Inventory migration port validation — 11 October 2026

Code commit: `25fc21e712721323cd5bff54cd2957cc8763f202`.

## Local checks

16 pure migration tests and 7 method-aware diagnostic tests passed without skips.
Changed Python files passed syntax compilation. The copied login-port, diagnostics
and HTTP-server baselines were verified against their Git blob hashes before edits.
The complete repository could not be cloned directly in the local environment;
GitHub access used the connected tools. Full integration ran on CI, not locally.

## Verified Windows build

[Run 38120521558](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38120521558),
job `114414114025`, completed successfully. Its actual log was read and contains:

```text
Ran 185 tests in 17.206s
OK
```

No skipped tests were reported. This includes the synthetic TLS sequence through
local session, character creation, inventory migration, inventory retrieval and
SQLite reopening, plus tests for authentication, ownership, payload rejection,
no migration-side database writes, and diagnostic redaction.

The Windows EXE was built and its packaged --about ran successfully, printing:

```text
Probe revision: inventory-migration-20261011.1
```

This proves packaged startup and test results, not successful login/gameplay with
the proprietary client. The user's supplied log predates this migration patch.

## Artifact

[Windows test package](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38120521558/artifacts/11695516116)

- Artifact ID: `11695516116`.
- ZIP size: 13,464,713 bytes.
- ZIP SHA256: `224f6ab5025e61db5d78d29533233e3b72f68db9f559827ea3acc68327552c53`.
- Contains executable, corresponding source, license/notices, instructions and EXE hash list.
- Not code-signed. Do not disable security software to run it.
- The archive hash is not the executable hash; see SHA256SUMS.txt in the package.

## Remaining limits

The gate is adapted from 1.14.7; a real 2.1.1 retry must establish acceptance.
Only an absent body or empty JSON object is accepted, and no migration is actually
performed for this new local research profile. There is no complete inventory
transaction/crafting implementation, real Epic token verification, functional
matchmaking, controllable player or compatible UE5 game server in this patch.
See INVENTORY_MIGRATION_PORT.md and LOGIN_PROBE.md before testing.
