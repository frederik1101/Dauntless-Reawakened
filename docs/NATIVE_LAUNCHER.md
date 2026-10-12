# C++ Launcher for Dauntless Reawakened 2.1.1

Native Windows C++ Win32 application: ReawakenedLauncher.exe.

## Use
Extract the 3 executables together: ReawakenedLauncher.exe,
Reawakened-Local-Server.exe and Reawakened-Ramsgate-Preview.exe
into C:\ReawakenedContinuityTest. Run the C++ Launcher. Select
without-appearance for the recommended first character A/B test.
Check consent for reversible temporary changes to the Windows hosts file,
game-specific CA and WindowsClient configuration and click START SPILLET.
Windows may request administrator privileges.

The launcher starts the real local API and waits for CLIENT PORTS READY,
then launches the existing reversible original-client helper with 600 seconds.
It passes MAP only after the explicit UI consent. Epic sign-in still
happens through Epic's own account portal. Close the game normally; the
helper restores the changes before the launcher stops the server through
a private inherited stdin STOP command. If restore fails, close the game
and click Gendan; alternatively open administrator PowerShell and run
.\Reawakened-Ramsgate-Preview.exe --restore.

## Remembering login -- limitation
The C++ launcher encrypts an optional **display label** and saved character
test variant using the Windows current-user DPAPI. Settings are under
%LOCALAPPDATA%\DauntlessReawakenedLauncher\settings.dpapi.
Click Glem navn to delete that file. This display label is NOT an Epic
credential. The launcher never captures, saves or replays the Epic
password/access/refresh token. It may appear to sign in automatically if
Epic's own browser has a valid cached session; otherwise Epic sign-in
is required again. Dauntless Revived 1.4.4 stores its OWN private-server
account key; that cannot authenticate stock 2.1.1 EOS.

This is a convenience GUI for experimental local backend tests, not a
working playable Ramsgate host, verified Epic login or a fix for Updating
Game Data. Only first-party Epic UI controls actual login.

## Development
CMake and Visual Studio/MSVC compile launcher/native/ReawakenedLauncher.cpp
with native Win32 API and CryptProtectData (Windows DPAPI).
Self-test: ReawakenedLauncher.exe --self-test (in-memory crypto/args only,
no game launch or profile write). Other helper tests are packaged alongside
and Windows CI builds and tests all three EXEs. There is no game-client
test in CI.

Never share raw game logs, personal databases, tokens or TLS private keys.
Retain the existing AppData backup/journal folders and original 2.1.1 EXE.
Licensing: AGPL-3.0-only; see LICENSE and NOTICE.
