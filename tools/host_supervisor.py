"""Local Ramsgate host supervisor (standard process control only).

This is NOT a UE game server. It only starts an independently provided,
compatible host and checks a structured readiness report. No DLL injection,
process patching, fabricated matchmaking destination or game assets.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path


class HostSupervisor:
    def __init__(self, executable: str, *, cwd: str | None = None):
        self.executable = Path(executable).resolve()
        self.cwd = Path(cwd).resolve() if cwd else self.executable.parent
        self._process: subprocess.Popen | None = None
        self._lock = threading.RLock()

    def start(self, args: tuple[str, ...] = ()) -> int:
        with self._lock:
            if self.is_running():
                raise RuntimeError("Host already running")
            if not self.executable.is_file():
                raise FileNotFoundError(self.executable)
            if any(not isinstance(a, str) or "\x00" in a for a in args):
                raise ValueError("Invalid argument")
            self._process = subprocess.Popen(
                [str(self.executable), *args], cwd=str(self.cwd),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, shell=False,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            return self._process.pid

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if not self.is_running():
                return
            assert self._process is not None
            self._process.terminate()
            try:
                self._process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=timeout)

    def status(self) -> dict:
        with self._lock:
            return {
                "process_running": self.is_running(),
                "pid": self._process.pid if self.is_running() else None,
                "gameplay_ready": False,
                "reason": "No verified Unreal gameplay readiness/admission protocol",
            }
