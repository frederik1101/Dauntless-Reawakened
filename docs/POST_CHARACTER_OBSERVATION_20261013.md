# Post-character login observation — 13 October 2026

The original 2.1.1 client test on 12 October reached a local unverified
EOS-sub exchange followed by GET /character [] and PUT /character {name}.
A subsequent GET returned a new character at updateVersion 0 with nine
string-valued fields, including AppearanceData. The client returned to login.
These are HTTP delivery observations, not proof of successful parsing.

The standalone server was started with --mystic-profile and no explicit
--profile-variant. The legacy default full yields one base field plus all
eight additional fields. This explains the nine-field response but not the
cause of the login failure. An older run with an existing version-7 character
and eight fields also failed near the compatibility stage.

When --diagnostic is active, the local epiceos exchange PROTOCOL_TRACE now
includes local_account_at_exchange {preexisting, owned_characters} and
profile_selection {mode, variant}. The selected database and account are
observed before later GET or PUT calls. No identifiers, character contents,
tokens, Epic credentials, raw stdout or unbounded error text enter the audit.
The observations NEVER enter the JSON sent to the game client.

Startup prints PROFILE_SELECTION, and isolated snapshot summaries include
only counts of accounts and characters. An implicit full profile is warned
about, without changing the CLI default or any existing character data.
Explicitly set --profile-variant on comparative tests.

Four synthetic regression tests exercise the eight existing variants,
the exact empty-create-version-zero sequence, current database baseline,
safe logging over verified loopback TLS, and legacy default warning.
No game was run. The verified local source suite reported 537 tests,
zero errors, zero skips on Linux Python 3.13.

Precise native login failure enums are not yet confirmed from a real client.
The existing fixed error markers are descriptive labels, not native codes.
A green CI is not proof of playable Ramsgate or a compatible UE5 game host.
The original SQLite DB, game EXE, certificates, Epic login and rollback
procedure are unchanged.
