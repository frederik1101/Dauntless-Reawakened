"""Atomic local JSON persistence for prototype character data (not game-ready)."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path


class JsonCharacterRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.records = {}
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("Expected character dictionary")
            self.records = loaded

    def get(self, account_id: str) -> list[dict]:
        return list(self.records.get(account_id, []))

    def create(self, account_id: str, name: str) -> dict:
        if not account_id or not name or len(name) > 64:
            raise ValueError("Invalid account or character name")
        existing = self.records.setdefault(account_id, [])
        record = {"id": f"local-{len(existing) + 1}", "name": name,
                  "updateVersion": 0, "data": None}
        existing.append(record)
        self.flush()
        return {"id": record["id"], "name": name}

    def save(self, account_id: str, character_id: str, data: str, version: int):
        json.loads(data)
        for record in self.records.get(account_id, []):
            if record["id"] == character_id:
                if not isinstance(version, int) or version <= record["updateVersion"]:
                    raise ValueError("Stale version")
                record["data"] = data
                record["updateVersion"] = version
                self.flush()
                return {"data": data}
        raise KeyError("Character not found")

    def flush(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".characters-", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.records, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
