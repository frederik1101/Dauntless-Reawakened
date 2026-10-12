# Revived 1.4.4 vs Reawakened 2.1.1 API comparison

Source: mixutin/dauntless-revived, branch dauntless-revived:
- UndauntedMetagame/src/routes/character.ts
- UndauntedMetagame/src/controllers/character.ts

Source: this repository main:
- backend/application.py
- backend/database.py
- backend/protocol_211.py

## Confirmed differences

| Behavior | Revived 1.4.4 | Reawakened baseline |
|---|---|---|
| GET /character for new account | auto-creates a character, then returns list | returns empty list until client PUT |
| PUT /character | creates from name, returns full wire character | creates from name, returns id and name only |
| Seed data | JSON string `{}` | JSON string containing PlayerAccountProgressStep=EnteredRamsgate |
| Initial updateVersion | 0 | 0 |
| Character GET wire fields | accountId, createdDate, data, id, lastModifiedDate, name, updateVersion | id, name, updateVersion, data |
| POST /character | saves and returns updated full wire character | saves and returns data only |

These differences **do not prove** a bug: clients target different releases and engine versions. The user's actual 2.1.1 run already sends GET empty -> PUT name -> GET one, which may be the expected 2.1.1 flow. Do not copy the 1.4.4 auto-create behavior into 2.1.1.

## Experiment strategy

1. Add read-only shape/contract tests comparing baseline behavior against Revived's documented shape.
2. Do not point the retail Revived client at the experimental server yet: it relies on its own launcher, auth, DLL and game-server stack. Redirecting just the HTTP API would not constitute a valid end-to-end test and could disrupt the user's working installation.
3. A future isolated 1.4.4 compatibility adapter can implement the older contract, using synthetic requests and separate databases, but must not silently change the 2.1.1 default behavior.
4. Record which differences are confirmed, and only implement a 2.1.1 change if independent 2.1.1 evidence supports it.

No client-side DLL or game binary modifications are made by this comparison.
