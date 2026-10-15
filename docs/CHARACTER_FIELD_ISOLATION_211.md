# 2.1.1 character A/B isolation — October 12, 2026

New revision character-isolation-20261012.7 adds an allowlisted profile variant
without changing Epic login, the original client, or the user's production
database.

Actual .5 user log with two character fields progressed through inventory
migration, game tuning and registration (but reset before real CITY join).
Actual .6 user log with nine fields failed after two character reads in each
of two separate attempts. In .6 the client reported login_operation_failed
at the character-read stage. We do not have the exact error text.

The regression is correlated with the seven new fields, not proven to be
caused by a particular one. The new test uses the original persisted data in
fresh SQLite snapshots, and can add only the following field groups:

- baseline: no additional fields
- appearance-only: AppearanceData only
- flags-only: CharacterFlagData, LoginFlagData, PlayerDataRepair
- metadata-only: LoginTime, LastLoginTime, LastChangelist
- without-appearance: all but AppearanceData (recommended first)
- without-flags: all but flag and repair fields
- without-metadata: all but time and changelist
- full: all seven added fields (the earlier .6 profile)

Each test server run creates a NEW snapshot, never modifies players.sqlite3,
and never silently merges results. Sessions, character IDs, account ownership,
version constraints, and the original wire string types stay unchanged.

The new client filter logs only fixed hints if a LoginOperation Failed line
contains a known term. They are not a verified error reason. Do not expose
token data or raw client logs. Do not run different variants simultaneously.

Passing tests demonstrates profile handling, preservation and TLS, not a
successful Dauntless login. The independent UE5 source testbed in
ue5_lab/RamsgateResearch is unrelated to the original client's protocol.

See docs/LOGIN_CONTINUITY.md for commands and docs/UE5_HOST_GAP.md for
requirements for a future genuine gameplay host.
