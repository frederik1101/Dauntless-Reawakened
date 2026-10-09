"""Minimal, offline 2.1.1 protocol fixtures from published research.

No Epic credentials, game files or proprietary source code are required.
These are *response-shape fixtures*, not a working game authentication system.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


def login_queue() -> dict:
    # Published 2.1.1 findings: precisely five keys.
    return {
        "state": "OPEN",
        "error_code": "",
        "title": "",
        "message": "",
        "timeout": 5000,
    }


def linked_account() -> dict:
    # gamesession-* endpoints use wrapped responses.
    return {"code": "OK", "message": "", "payload": {"isLinked": True}}


@dataclass
class CharacterStore:
    """Ephemeral in-memory character store for contract tests only."""
    characters: dict[str, dict] = field(default_factory=dict)

    def create(self, name: str) -> dict:
        if not name or len(name) > 64:
            raise ValueError("Invalid character name")
        character_id = f"local-{len(self.characters) + 1}"
        record = {
            "id": character_id,
            "name": name,
            "updateVersion": 0,
            "data": None,
        }
        self.characters[character_id] = record
        return {"id": character_id, "name": name}

    def list(self) -> list[dict]:
        return list(self.characters.values())

    def save(self, character_id: str, data: str, version: int) -> dict:
        if character_id not in self.characters:
            raise KeyError("Character not found")
        if not isinstance(data, str):
            raise ValueError("data must be a JSON string")
        json.loads(data)
        current = self.characters[character_id]
        if version <= current["updateVersion"]:
            raise ValueError("updateVersion must increase")
        current["data"] = data
        # Preserve the exact client-provided version; do not increment twice.
        current["updateVersion"] = version
        return {"data": data}
