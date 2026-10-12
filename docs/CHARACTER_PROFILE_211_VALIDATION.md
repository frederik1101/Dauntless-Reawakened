# Character-profile validation — 12 October 2026

Code commit: `a681237f9473e2287e4df530412220dffa4f6adf`.
Both Windows executables report `character-profile-20261012.6`.
Branch work/login-continuity-211; PR #5 remains unmerged.

## Windows build actually checked

The full decoded log of job `114886926432`, run `38271601662`, was read.
It checked out the commit above and reported:

```text
Ran 520 tests in 31.079s
OK
```

No tests were skipped. The 33 new tests exercise missing-field initialization,
all-string 2.1.1 wire values, preservation of existing data/IDs/versions, no old
quest/cosmetic/progression import, source-database hash invariance, fresh SQLite
snapshots, corruption/path rejection, stable retry dates, concurrent saves,
authentication/ownership, and real CA-verified loopback HTTPS profile reads and
saves. These are synthetic clients, NOT Dauntless or real Epic authentication.

Both PyInstaller Windows builds succeeded. Both packaged self-tests succeeded;
the server's result includes `profile_initializer: passed`. The matching preview
self-test and help succeeded, and the workflow checked that self-tests did not
create the temporary LOCALAPPDATA profile. Packaged self-tests are not a real
client test and do not independently run the complete server/listener lifecycle.

The exact published source was also tested locally on Linux:
520 tests in 9.557 seconds, OK, no skips. Initial local source and published
source differed only by one extra blank line in a test module; their ASTs were
identical, and the published file was used in this final local rerun.

## Artifact verification

[Paired Windows package](https://github.com/frederik1101/Dauntless-Reawakened/actions/runs/38271601662/artifacts/11757112139)

- Artifact ID: 11757112139, Reawakened-Login-Continuity-Windows.
- Conversation filename: Reawakened-Character-Profile-Windows.zip.
- ZIP size: 27,214,051 bytes.
- ZIP SHA256: `90b6f13098bd45a974926f5c9fe1a31905e290195064cc94d64bbdbb1eeec58a`.
- Server EXE SHA256: `288e25d7f9817fbed6b75f011d46462df7b15a5f8629c74e230750d15f39f492`.
- Preview EXE SHA256: `8cef89de46a02e0b64de62dc08cd9953a463da18ac3abb4bfdbb6d4932ce93cf`.

Downloaded ZIP matches the GitHub digest; CRC validation passed. Both EXE hashes
match SHA256SUMS.txt. BUILD-COMMIT.txt matches the tested commit. All 11 changed
source/documentation files were compared with the tested source (see whitespace
note above). START-HERE.md contains the new revision and --mystic-profile command.
Windows binaries were not executed in the Linux container; Windows execution
claims come from the actual Actions job log.

## Experiment boundaries

--mystic-profile creates a new snapshot of the existing players.sqlite3 and
initializes missing fields only in that copy before accepting requests. It keeps
the original account/character keys, versions and supplied strings. Later saves
return the normalized data actually stored in the copy. It does not rewrite the
original database or automatically merge test results back. Each invocation
creates a fresh copy from the original, not a continuation of the preceding test.

The appearance sample supplies common structure with empty cosmetic selections,
NOT a verified 2.1.1 player appearance. New dates and LastChangelist are synthetic
test metadata. No tutorial-completion flags, old quest tables or grants are added.
The original Epic sign-in, EULA, executable/hash gate, TLS and reversible launcher
remain unchanged. Local identity exchange is still UNVERIFIED loopback research.

No real-client result exists for .6 yet. The missing fields were identified by
comparison with Mystic, not proved to cause the .5 reset. Read-only static review
also found the missing LastChangelist path does not itself reject compatibility;
do not claim that seeding that field alone fixes login. A stable PLAY button,
CITY request, native host join and controllable Ramsgate character remain separate
unverified milestones. This package provides no native gameplay host.

See CHARACTER_PROFILE_211.md for the source comparison and LOGIN_CONTINUITY.md
for both commands and restoration instructions. Share only the sanitized server
log and filtered runner JSON, never database copies, private keys or raw tokens.
