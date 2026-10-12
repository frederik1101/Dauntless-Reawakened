# Native C++ Win32 Launcher

Source: ReawakenedLauncher.cpp. CMakeLists.txt generates the Windows GUI.
See ../../docs/NATIVE_LAUNCHER.md for setup, consent, security limitations,
DPAPI display-name saving, and recovery.

Inspired by Revived's OS-protected key storage design, but **not** by
Revived's 1.4.4 account-key auth. No Epic credentials/tokens are stored.
The original stock Dauntless 2.1.1 still requires Epic EOS and a compatible
game backend. This is a research launcher, not a game server.
License: AGPL-3.0-only.
