# SPDX-License-Identifier: AGPL-3.0-only
"""PyInstaller entry point. Build from repo root; source remains public."""
from tools.login_probe import main

if __name__ == '__main__':
    print('Probe revision: login-route-diagnostics-20261011.1', flush=True)
    raise SystemExit(main())
