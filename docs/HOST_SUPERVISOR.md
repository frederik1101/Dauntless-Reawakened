# Local host supervisor (foundation only)

This work adds `tools/host_supervisor.py`, a minimal Windows/Linux subprocess lifecycle component for a separately provided executable. It does not start Dauntless, inject into Unreal, patch memory, provide a gameplay host, issue tickets, or advertise readiness to matchmaking.

The status deliberately reports `gameplay_ready: false` until a compatible Unreal gameplay host has independently demonstrated a verified admission/readiness contract. Do not change `UnavailableHost` in the existing matchmaking branch based on process-running status.

Run the tests with `python -m unittest tests.test_host_supervisor -v`. They launch a short-lived Python child process, not a game. Source is original Reawakened process-control code; no third-party game runtime copied.

Next permitted engineering tasks: add a local GUI and bounded log capture, review a documented compatible gameplay-host readiness protocol if one becomes available, and perform actual client join tests only when a real host exists. Keep this branch separate from concurrent native/runtime work.
