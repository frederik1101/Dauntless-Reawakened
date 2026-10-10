# Windows 2.1.1 login experiment (not gameplay)

This package is ready for a **first bounded experiment**, not a promise of working
login, Ramsgate or hunts. It ports selected Mystic Paradox login handlers; see
[MYSTIC_LOGIN_PORT.md](MYSTIC_LOGIN_PORT.md) for exact sources and limitations.
The first real client run has not yet been performed by this project.

## Before running

Close **Dauntless and Revived**, and do not open either in parallel with the probe.
The expected installation is `C:\Games\Dauntless`; it must contain the original
151448856-byte Windows x64 EXE and a readable CA bundle. Size is an inspection
check, not proof of authenticity: Windows must also verify a valid Phoenix Labs
Authenticode signature. A failed check stops before changing the game configuration.

The program temporarily adds localhost entries **only for its listed Phoenix service
hosts**, appends its research CA to this installation's CA bundle, and moves aside
the shared `Archon\Saved\Config\WindowsClient` directory. It never edits the EXE,
installs a CA in Windows trust, disables certificate checks, alters Epic domains,
injects a DLL or opens a public server. It refuses conflicting existing hosts entries.
This temporarily affects access to those Phoenix names by other local programs.

Original CA/hosts bytes and a rollback journal are kept outside the repo in
`%LOCALAPPDATA%\DauntlessReawakenedProbe\active`. Original config is moved to a
uniquely named adjacent backup, on the same filesystem. Do not delete those backups.
Do not publish this state folder: it contains keys, local identity data and config.

## Packaged Windows executable

Download the `Reawakened-Login-Probe-Windows` artifact from the repository's
**Build Windows login probe** workflow for the intended commit. Extract it to its
own folder (not the game folder). The artifact contains the EXE, SHA256SUMS.txt,
license/notices and the corresponding source ZIP. The executable is not code-signed;
do not disable Defender or other security software to run it. Verify its provenance
against the workflow and source before execution.

In PowerShell in that folder, a read-only inspection is:

```powershell
.\Reawakened-Login-Probe.exe --check
```

For the first actual attempt, open PowerShell **as administrator** (needed for the
hosts file) and run:

```powershell
.\Reawakened-Login-Probe.exe --run --experimental-maintenance
```

Read the on-screen changes and type `TEST` to consent. The maintenance reply is an
explicit **unverified hypothesis**, not a recovered 2.1.1 contract. The experiment
also uses an unverified EOS subject as a local lookup key, not secure authentication.

The probe binds HTTPS on 127.0.0.1/::1 port 443 and HTTP on port 80 using one backend
and session store. Busy ports cause a stop before edits. It then starts the original
signed client directly with the documented Epic account-portal switches. Any real
Epic sign-in is completed by you in Epic's browser UI; never give a password/token
or a raw launch command containing credentials to another person.

Observe the login/menu outcome. A response from our server is not proof the client
accepted it. There is **no game server to travel to**, so no playable Ramsgate or hunt
is expected. The test ends when the game exits or after 180 seconds. Only the process
started by this probe is terminated at timeout. Keep the console open while testing.

## Restoration and crash recovery

Normal exit restores the original CA additions, hosts entries and config before
closing the backend. The temporary test config is retained in an adjacent,
uniquely named local folder, not deleted. Unrelated later file edits are preserved
where our exact addition can be removed; ambiguous edits stop restoration rather
than overwriting someone else's changes.

If the console/computer was forcibly closed, do not start Revived yet. Close any
remaining Dauntless process and run from elevated PowerShell:

```powershell
.\Reawakened-Login-Probe.exe --restore
```

A second restore is safe. If restoration reports a conflict, keep the backups and
report the error; do not manually delete config or certificate files to bypass it.

## Feedback

Report the visible game message or screenshot and `active\probe.log`. That log
contains only fixed route labels, methods and statuses, not request bodies, tokens,
query strings or account IDs. It starts recording only after the transport self-check.
Never share the complete active/state directory, database or key files.

## From source instead

Python 3.11+ and the repository's requirements-dev.txt are needed. From the repo root:

```powershell
python -m pip install -r requirements-dev.txt
python -m tools.login_probe --check
python -m tools.login_probe --run --experimental-maintenance
# Recovery:
python -m tools.login_probe --restore
```

Source/runtime setup is optional; the Windows workflow packages the same code.
