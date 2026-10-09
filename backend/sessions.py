"""Isolated demo sessions; not Epic/EOS authentication.

Tokens are generated locally and never accepted from external identity providers.
This module is intended for offline tests only.
"""
from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from threading import RLock


@dataclass(frozen=True)
class DemoSession:
    session_id: str
    session_token: str
    account_id: str


class DemoSessionManager:
    def __init__(self):
        self._lock = RLock()
        self._by_token: dict[str, DemoSession] = {}

    def create(self, account_id: str) -> DemoSession:
        if not account_id:
            raise ValueError("account id required")
        session = DemoSession(
            session_id=token_urlsafe(18),
            session_token=token_urlsafe(32),
            account_id=account_id,
        )
        with self._lock:
            self._by_token[session.session_token] = session
        return session

    def resolve(self, token: str) -> DemoSession | None:
        with self._lock:
            return self._by_token.get(token)

    def revoke(self, token: str) -> bool:
        with self._lock:
            return self._by_token.pop(token, None) is not None
