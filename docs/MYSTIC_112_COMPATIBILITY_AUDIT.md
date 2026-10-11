# Mystic Paradox compatibility audit — 2026-10-11

Target here: Dauntless 2.1.1 (NOT Mystic Paradox's supported 1.12.0).
Evidence: the 2026-10-11 real-client redacted server log and upstream
`pranav158/Mystic-Paradox` public `ParadoxBackend/src/routes/` sources.
Do not port 1.12.0 runtime binaries, game content or hardcoded player progression.

## Observed real-client order

The user's post-login-20261011.2 run returned HTTP 200 for:
account-link -> login queue -> EOS research exchange -> accountinfo ->
tags/ban -> GET character (twice) -> inventory migration ->
store reconcile -> migration trigger -> creator -> public account ->
account mapping -> three tuning blobs -> progression/config ->
POST character -> player register. Immediately afterward the client
re-requests status/maintenance/features and displays the login UI again.
The user sees 'Logging into Dauntless' then 'Updating Game Data' for
approximately two seconds. No candidate CITY join, host assignment or
native gameplay process is evidenced.

## What upstream actually establishes

* `ParadoxBackend/src/routes/inventory.ts`: migration POST
  `/inventory/<character>/<build>` returns a small `{code:'NONE',message:''}`
  reply. This is already present in our backend and was HTTP 200 in the log.
  Its successful status does not prove the 2.1.1 parser accepted it.
* `ParadoxBackend/src/routes/character.ts`: character data has nested JSON
  string fields. The upstream commentary explicitly reports a **regression**
  when decoding more fields in a different 1.14.7 experiment. Do not
  automatically decode every stored character field.
* `ParadoxBackend/src/routes/progression.ts`: actual progression configuration
  depends on separately exported `progression_config.json` and Slayer's Path
  data. Upstream's synthetic example data is not playable and does not
  establish the final 2.1.1 configuration.
* `ParadoxDirector` and `ParadoxRuntime` are separate native-host and
  compatibility components. Backend HTTP 200 and register are not a
  Ramsgate game-server join.

## Next measured acceptance criteria

1. Preserve a single account's character ID and version across both login
   attempts; compare **redacted** character GET/POST schema and version
   outcomes without logging bearer tokens or full game data.
2. Determine whether a client parse error or an explicit disconnect is
   recorded by the client in the two seconds after progression/config and
   register. No such marker is in the redacted server route log.
3. Compare only the observed 2.1.1 route response envelopes with upstream
   contracts; test synthetic payloads over TLS before changing production
   handler behavior.
4. Treat PLAY visible, CITY join requested, host assigned and controllable
   Ramsgate as four separate milestones. Do not advertise a host without a
   real one.
5. Do not change the server to return success for unknown routes, auto-accept
   terms, grant currency, or treat an unverified EOS-sub as cryptographic Epic
   authentication.

## Upstream references

- https://github.com/pranav158/Mystic-Paradox/blob/main/ParadoxBackend/src/routes/character.ts
- https://github.com/pranav158/Mystic-Paradox/blob/main/ParadoxBackend/src/routes/inventory.ts
- https://github.com/pranav158/Mystic-Paradox/blob/main/ParadoxBackend/src/routes/progression.ts
- https://github.com/pranav158/Mystic-Paradox/blob/main/docs/SELF_HOSTING.md

License: upstream AGPL-3.0-only with Section 7 terms. No upstream
implementation was copied into this audit; see existing project notices for
the previously ported contracts.
