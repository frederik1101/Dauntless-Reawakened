"""Bounded, expiring LOCAL sessions. Not an Epic token verifier."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Session:
    session_id: str
    session_token: str = field(repr=False)
    account_id: str
    expires_at: float


class SessionStore:
    def __init__(self, ttl: float = 7200, limit: int = 128,
                 clock: Callable[[], float] = time.monotonic):
        if ttl <= 0 or limit < 1:
            raise ValueError('Invalid session settings')
        self.ttl, self.limit, self.clock = ttl, limit, clock
        self._entries: dict[str, Session] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, account_id: str) -> Session:
        if not account_id:
            raise ValueError('Missing account')
        with self._lock:
            now = self.clock()
            self._entries = {k: v for k, v in self._entries.items() if v.expires_at > now}
            if len(self._entries) >= self.limit:
                raise OverflowError('Session capacity reached')
            session = Session(secrets.token_hex(16), secrets.token_urlsafe(32),
                              account_id, now + self.ttl)
            self._entries[self._key(session.session_token)] = session
            return session

    def resolve(self, token: str) -> Session | None:
        if not isinstance(token, str) or not 1 <= len(token) <= 256:
            return None
        with self._lock:
            key = self._key(token)
            session = self._entries.get(key)
            if session and session.expires_at <= self.clock():
                self._entries.pop(key, None)
                return None
            return session

    def revoke(self, token: str) -> bool:
        with self._lock:
            return self._entries.pop(self._key(token), None) is not None


def unverified_subject(token: str) -> str:
    """Research only: extract a lookup key. NEVER asserts authenticity or ownership.

    Caller must explicitly enable this and enforce a loopback-only listener.
    Does not validate signature, issuer, audience or expiry. No outbound calls.
    """
    try:
        if len(token) > 16384:
            raise ValueError()
        parts = token.split('.')
        if len(parts) != 3 or not all(re.fullmatch(r'[A-Za-z0-9_-]+', p) for p in parts):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
        subject = payload.get('sub') if isinstance(payload, dict) else None
        if not isinstance(subject, str) or not 1 <= len(subject) <= 256:
            raise ValueError()
        if any(ord(c) < 33 or ord(c) > 126 for c in subject):
            raise ValueError()
        return subject
    except (ValueError, UnicodeError, binascii.Error, RecursionError):
        raise ValueError('Invalid research identity token') from None
