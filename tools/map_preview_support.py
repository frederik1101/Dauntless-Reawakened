# SPDX-License-Identifier: AGPL-3.0-only
"""Config-only map preview helpers. No injection, patching or game-server mode."""
from __future__ import annotations
import ctypes
import json
import os
import time
from pathlib import Path

REVISION = 'identity-mapping-20261012.5'
EXACT_SHA256 = '934325acecf64e19a01f70f72dcdcebd68cfb12f11a812cd551c608ac16cea34'
MAP = '/Game/Maps/ramsgate/ramsgate_01_persistent'
# The map and city mode are documented in Revived's awakening-2-1-1.md.
# Pool settings are hints, not a process memory limit. The watchdog is separate.
ENGINE_INI = (f'[/Script/EngineSettings.GameMapsSettings]\nGameDefaultMap={MAP}\n'
              'GlobalDefaultGameMode=/Game/blueprints/gamemode/BPGM_City.BPGM_City_C\n'
              '\n[SystemSettings]\nr.Streaming.PoolSize=400\nr.Streaming.LimitPoolSizeToVRAM=1\n')


def install_config(config: Path, journal: Path, *, normal_login: bool = False) -> None:
    """Write only inside the fresh directory already owned by the rollback journal."""
    from tools.probe_files import MARKER, _plain_path
    config, journal = config.absolute(), journal.absolute()
    for path in (config, journal, config / MARKER, config / 'Engine.ini'):
        _plain_path(path)
    record = json.loads(journal.read_text(encoding='utf-8'))
    if (record.get('version') != 1 or record.get('restored') is not False or
            Path(record['config']).absolute() != config or
            (config / MARKER).read_text(encoding='ascii') != record['marker']):
        raise ValueError('Map preview requires its active rollback journal')
    # Exclusive creation: never append to user config or overwrite an unknown file.
    with (config / 'Engine.ini').open('x', encoding='ascii', newline='\n') as stream:
        # Normal-login mode keeps the game's cooked default login map.
        # The explicit empty Engine.ini prevents carrying a prior Ramsgate override.
        stream.write('' if normal_login else ENGINE_INI)


def heartbeat_map(body: bytes) -> str:
    """Project one allowlisted field; never retain IDs, state, server or tokens."""
    if not isinstance(body, bytes) or len(body) > 65536:
        return 'invalid'
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        return 'invalid'
    value = value.get('map') if isinstance(value, dict) else None
    if not isinstance(value, str) or len(value) > 256:
        return 'unknown'
    if value.lower() in {MAP.lower(), 'ramsgate_01_persistent',
                         (MAP + '.ramsgate_01_persistent').lower()}:
        return 'ramsgate'
    if value.lower() in {'map_loginmenu', '/game/maps/map_loginmenu',
                         '/game/maps/map_loginmenu.map_loginmenu'}:
        return 'login_menu'
    return 'unknown'


def process_memory_bytes(process) -> int:
    """Query resource counters on the owned Popen handle, not process memory contents."""
    if os.name != 'nt':
        raise OSError('Memory measurement requires Windows')
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]
    info = Counters()
    info.cb = ctypes.sizeof(info)
    fn = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    fn.restype = wintypes.BOOL
    # Windows CPython Popen owns this handle until cleanup; no unrelated PID lookup.
    if not fn(wintypes.HANDLE(int(process._handle)), ctypes.byref(info), info.cb):
        raise OSError('Owned process memory measurement failed')
    return max(int(info.PrivateUsage), int(info.WorkingSetSize))


def login_test_duration(seconds: int | None, normal_login: bool) -> int:
    maximum = 600 if normal_login else 180
    value = seconds if seconds is not None else (600 if normal_login else 120)
    if type(value) is not int or not 30 <= value <= maximum:
        raise ValueError('Test duration outside supported mode bounds')
    return value


def watch(process, seconds: int, *, measure=process_memory_bytes,
          clock=time.monotonic, sleep=time.sleep, cap_mib: int = 5000,
          max_seconds: int = 180) -> dict:
    if type(max_seconds) is not int or max_seconds not in (180, 600):
        raise ValueError('Invalid watchdog duration bound')
    if type(seconds) is not int or not 30 <= seconds <= max_seconds:
        raise ValueError('Test duration outside watchdog bounds')
    if type(cap_mib) is not int or not 1 <= cap_mib <= 5000:
        raise ValueError('Invalid memory cap')
    start, peak = clock(), 0
    reason = 'client_exited'
    while process.poll() is None:
        if clock() - start >= seconds:
            reason = 'time_limit'
            break
        try:
            memory = measure(process)
            if type(memory) is not int or memory < 0:
                raise ValueError()
        except (OSError, ValueError, AttributeError):
            reason = 'client_exited' if process.poll() is not None else 'memory_query_failed'
            break
        peak = max(peak, memory)
        if memory >= cap_mib * 1024 * 1024:
            reason = 'memory_limit'
            break
        sleep(0.5)
    return {'termination': reason, 'elapsed_seconds': round(clock() - start, 2),
            'peak_observed_memory_mib': round(peak / 1024 / 1024, 1)}


def stop_owned(process) -> None:
    """Stop only the process object returned by this preview's own launch."""
    import subprocess
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=8)
    if process is not None and process.poll() is None:
        raise OSError('Owned client is still running; restoration withheld')
