# SPDX-License-Identifier: AGPL-3.0-only
"""PyInstaller entry point. Build from repo root; source remains public."""
from tools.login_probe import main

if __name__ == '__main__':
    raise SystemExit(main())
