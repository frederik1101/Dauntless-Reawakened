# Login stage comparison — 14 October 2026

This is an offline, data-free comparison of existing sanitized `server-diagnostic-*.log` files. No actual client, game files, local database, raw stdout, tokens, private TLS keys, or Windows configuration are accessed.

Code: `tools/login_stage_diagnostics.py`. Six synthetic regression tests: `tests/test_login_stage_diagnostics.py`.

## Real-client diagnostic evidence (12 October)

On the supplied sanitized server log: one unverified local EOS research exchange written to socket; one GET /character returning zero records; one PUT /character creating a record; one subsequent GET returning a character with nine string fields including AppearanceData and progress EnteredRamsgate. There were zero post-character requests and zero CITY joins after this read. Twenty-four unknown 404 replies were written, mostly tracking heartbeats. No prepared response lacked confirmation of a successful local socket write. All this is HTTP-side evidence, NOT proof of game parsing, a compatible character, verified Epic authentication or a completed login.

The early Epic mentions in the independent filtered client trace occurred *before* the local exchange; they cannot automatically be attributed to our backend.

## Usage and privacy

`python -m tools.login_stage_diagnostics <sanitized-log>` (optional `--previous <sanitized-log>`). Output is fixed counts, booleans, allowlisted state/profile values and stage names only. It does not emit request/session/account/character IDs, raw request or character content, user filenames, login tokens, arbitrary client error strings, or timestamps. It reads at most 2 MiB and 4096 prepared records without persisting input. Only paired PROTOCOL_TRACE/PROTOCOL_TRACE_END socket writes are counted.

Two REAL sanitized server logs have now been compared offline. The earlier 12 October 13:20-13:25 UTC run had two local research exchanges, four populated GET /character responses containing two string-valued fields, eight subsequent post-character HTTP 200 socket writes, and no CITY join. The later 16:57-17:00 UTC run had one local exchange, GET /character [] -> PUT create -> GET character with nine string fields, zero subsequent post-character calls, and no CITY join. The comparator therefore reports a regression from post_character_request to character_loaded. This is a measured difference in observable server call sequence, not a proof that any specific extra field caused failure. Neither source log or token is committed. Other experiments with eight fields also failed. No additional client test is required for this comparison.

This independent analysis tool does not alter the game's EXE, hosts file, CA, shared Archon config, Windows trust, Epic login, Revived installation or SQLite storage. It is not a gameplay host.
