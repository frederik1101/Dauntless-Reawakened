# SPDX-License-Identifier: AGPL-3.0-only
"""PyInstaller entry point. --diagnose is read-only; normal probe is unchanged."""
import sys
from tools.login_probe import main
from tools.login_report import main as report_main, REPORT_REVISION

if __name__ == '__main__':
    print('Probe revision: ' + REPORT_REVISION, flush=True)
    if sys.argv[1:] == ['--diagnose']:
        raise SystemExit(report_main())
    raise SystemExit(main())
