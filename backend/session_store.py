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
from .research_identity import ResearchIdentity


@dataclass(frozen=True)
class Session:
    session_id: str
    session_token: str = field(repr=False)
    account_id: str
    expires_at: float
    # Ephemeral binding from the unverified research exchange, never a token.
    linked_epic_id: str | None = field(default=None, repr=False)
    research_identity: ResearchIdentity | None = field(default=None, repr=False)


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

    def create(self, account_id: str, *, linked_epic_id: str | None = None,
               research_identity: ResearchIdentity | None = None) -> Session:
        if not account_id:
            raise ValueError('Missing account')
        if linked_epic_id is not None and (
                not isinstance(linked_epic_id, str) or not 1 <= len(linked_epic_id) <= 256 or
                any(ord(c) < 33 or ord(c) > 126 for c in linked_epic_id)):
            raise ValueError('Invalid linked research identity')
        if research_identity is not None and (
                not isinstance(research_identity, ResearchIdentity) or
                research_identity.epic_id != linked_epic_id):
            raise ValueError('Inconsistent local identity binding')
        with self._lock:
            now = self.clock()
            self._entries = {k: v for k, v in self._entries.items() if v.expires_at > now}
            if len(self._entries) >= self.limit:
                raise OverflowError('Session capacity reached')
            session = Session(secrets.token_hex(16), secrets.token_urlsafe(32),
                              account_id, now + self.ttl, linked_epic_id, research_identity)
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

    def active_for_account(self, account_id: str) -> Session | None:
        """Presence-only admission; never use this lookup as API authentication."""
        if not isinstance(account_id, str) or not account_id:
            return None
        with self._lock:
            now = self.clock()
            candidates = [v for v in self._entries.values()
                          if v.account_id == account_id and v.expires_at > now]
            return max(candidates, key=lambda v: v.expires_at) if candidates else None

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
