# SPDX-License-Identifier: AGPL-3.0-only
"""Local CITY matchmaking and a narrow handoff to an authoritative host owner.

This is not an Unreal server. The production default has NO host, so it cannot
return a destination. A future owned-process supervisor must implement HostProvider
only after native world/network/admission readiness. No HTTP 'set ready' shortcut
or fallback address exists. Wire format is a 2.1.1 research candidate, not live-verified.
"""
from __future__ import annotations

import math
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

RAMSGATE_MAP = '/Game/Maps/ramsgate/ramsgate_01_persistent'
_SAFE = re.compile(r'[A-Za-z0-9_.:+-]{1,128}\Z')


@dataclass(frozen=True, repr=False)
class PlayerBinding:
    account_id: str
    session_id: str
    character_id: str


@dataclass(frozen=True, repr=False)
class JoinRequest:
    build_id: str
    game_mode: str = 'CITY'


@dataclass(frozen=True, repr=False)
class HostAssignment:
    """Provided by the host owner, never constructed from a player request.

    expires_at uses the broker's monotonic clock. The supervisor must revalidate
    this exact generation on each poll, and reserve/release player admission.
    Merely binding UDP or starting a process is insufficient to return this object.
    Tickets/encryption are NOT invented here or inserted into serverInfo.
    """
    instance_id: str
    game_session_id: str
    generation: str
    build_id: str
    world: str
    port: int
    expires_at: float
    host: str = '127.0.0.1'


class HostProvider(Protocol):
    def reserve(self, player: PlayerBinding, candidate_id: str,
                request: JoinRequest) -> HostAssignment | None: ...
    def refresh(self, assignment: HostAssignment, player: PlayerBinding,
                candidate_id: str) -> HostAssignment | None: ...
    def is_live(self, assignment: HostAssignment, player: PlayerBinding,
                candidate_id: str) -> bool: ...
    def release(self, player: PlayerBinding, candidate_id: str) -> None: ...


class UnavailableHost:
    """The only production provider shipped in this change."""
    def reserve(self, player, candidate_id, request):
        return None

    def refresh(self, assignment, player, candidate_id):
        return None

    def is_live(self, assignment, player, candidate_id):
        return False

    def release(self, player, candidate_id):
        pass


@dataclass(repr=False)
class _Candidate:
    candidate_id: str
    player: PlayerBinding
    request: JoinRequest
    deadline: float
    retained_until: float
    state: str = 'MATCHING'
    reason: str = ''
    assignment: HostAssignment | None = field(default=None, repr=False)


def parse_join(body: dict, player: PlayerBinding) -> JoinRequest:
    if not isinstance(body, dict) or len(body) > 64:
        raise ValueError('Invalid join request')
    if body.get('playerId') != player.account_id:
        raise PermissionError('Player identity does not match local session')
    if body.get('gameMode') != 'CITY':
        raise NotImplementedError('Only CITY is implemented')
    build = body.get('buildId')
    if not isinstance(build, str) or not _SAFE.fullmatch(build):
        raise ValueError('Invalid build identifier')
    for key in ('isPrivate', 'privateMatch'):
        if key in body and not isinstance(body[key], bool):
            raise ValueError('Invalid privacy option')
    if 'characterId' in body and body['characterId'] != player.character_id:
        raise PermissionError('Character identity does not match local session')
    # Do not silently map a requested hunt onto the city.
    hunts = body.get('hunts', [])
    if hunts not in ([], ['ShatteredIsles_ReturnToRamsgate']):
        raise NotImplementedError('Hunts are not implemented')
    # Party/loadout/QoS metadata is not used as authority and is never forwarded
    # to a shell, host command line, URL or response. This broker is solo-only.
    return JoinRequest(build)


def valid_assignment(a: HostAssignment, request: JoinRequest, now: float) -> bool:
    if not isinstance(a, HostAssignment):
        return False
    return (a.host == '127.0.0.1' and a.world == RAMSGATE_MAP and
            a.build_id == request.build_id and type(a.port) is int and
            1024 <= a.port <= 65535 and
            type(a.expires_at) in (int, float) and math.isfinite(a.expires_at) and
            now < a.expires_at <= now + 30 and
            all(isinstance(v, str) and _SAFE.fullmatch(v) is not None
                for v in (a.instance_id, a.game_session_id, a.generation)))


class RamsgateMatchmaker:
    def __init__(self, hosts: HostProvider | None = None, *, wait_seconds: float = 120,
                 limit: int = 128, clock: Callable[[], float] = time.monotonic):
        if (type(wait_seconds) not in (int, float) or not math.isfinite(wait_seconds)
                or not 1 <= wait_seconds <= 600 or type(limit) is not int or not 1 <= limit <= 1024):
            raise ValueError('Invalid matchmaking bounds')
        self.hosts = hosts if hosts is not None else UnavailableHost()
        self.wait_seconds, self.limit, self.clock = wait_seconds, limit, clock
        self._candidates: dict[str, _Candidate] = {}
        self._lock = threading.RLock()

    def _release(self, c: _Candidate) -> None:
        try:
            self.hosts.release(c.player, c.candidate_id)
        except Exception:
            # Do not echo provider exceptions, which can contain private data.
            pass
        c.assignment = None

    def _prune(self, now: float) -> None:
        for key, c in list(self._candidates.items()):
            if now >= c.retained_until:
                self._release(c)
                del self._candidates[key]

    def join(self, player: PlayerBinding, body: dict) -> dict:
        request = parse_join(body, player)
        with self._lock:
            now = self.clock()
            self._prune(now)
            old = self._candidates.get(player.session_id)
            if old and old.player != player:
                raise PermissionError('Session binding changed')
            if old and old.request == request and old.state not in {'FAILED', 'CANCELED'}:
                return self._poll(old, now)
            if old:
                self._release(old)
            elif len(self._candidates) >= self.limit:
                raise OverflowError('Matchmaking capacity reached')
            c = _Candidate(secrets.token_hex(16), player, request,
                           now + self.wait_seconds, now + self.wait_seconds + 30)
            self._candidates[player.session_id] = c
            return self._poll(c, now)

    def status(self, player: PlayerBinding) -> dict:
        with self._lock:
            now = self.clock()
            self._prune(now)
            c = self._candidates.get(player.session_id)
            if c is None:
                raise KeyError('No candidate')
            if c.player != player:
                raise PermissionError('Candidate belongs to another session')
            return self._poll(c, now)

    def cancel(self, player: PlayerBinding) -> None:
        with self._lock:
            c = self._candidates.get(player.session_id)
            if c is not None:
                if c.player != player:
                    raise PermissionError('Candidate belongs to another session')
                self._release(c)
                c.state, c.reason = 'CANCELED', 'PLAYER_CANCELED'
                c.retained_until = self.clock() + 30

    def _fail(self, c: _Candidate, reason: str) -> None:
        self._release(c)
        c.state, c.reason = 'FAILED', reason

    def _poll(self, c: _Candidate, now: float) -> dict:
        if c.state in {'CANCELED', 'FAILED'}:
            return self._body(c)
        if c.assignment is None and now >= c.deadline:
            self._fail(c, 'NO_LOCAL_HOST_READY')
            return self._body(c)
        try:
            if c.assignment is None:
                c.assignment = self.hosts.reserve(c.player, c.candidate_id, c.request)
            else:
                previous = c.assignment
                renewed = self.hosts.refresh(previous, c.player, c.candidate_id)
                immutable = ('instance_id', 'game_session_id', 'generation', 'build_id', 'world', 'host', 'port')
                if (not isinstance(renewed, HostAssignment) or
                        any(getattr(renewed, key) != getattr(previous, key) for key in immutable)):
                    self._fail(c, 'LOCAL_HOST_GENERATION_LOST')
                    return self._body(c)
                c.assignment = renewed
            if c.assignment is not None:
                # An expired or dead generation must never yield its old address,
                # even if an earlier poll was IN_PROGRESS.
                if (not valid_assignment(c.assignment, c.request, now) or
                        self.hosts.is_live(c.assignment, c.player, c.candidate_id) is not True):
                    self._fail(c, 'LOCAL_HOST_UNAVAILABLE')
                else:
                    c.state, c.reason = 'IN_PROGRESS', ''
                    c.retained_until = now + self.wait_seconds + 30
        except Exception:
            self._fail(c, 'LOCAL_HOST_PROVIDER_FAILED')
        return self._body(c)

    @staticmethod
    def _body(c: _Candidate) -> dict:
        body = {
            'candidateId': c.candidate_id, 'status': c.state,
            'statusReason': c.reason, 'gameMode': 'CITY',
            'candidateStatusPeriodMillis': 1000, 'isNewMatchmaker': True,
            'playerStates': {},
        }
        if c.state == 'IN_PROGRESS' and c.assignment is not None:
            a = c.assignment
            body['playerStates'] = {
                c.player.account_id: {'isReadyToLeaveLobby': True, 'publicLoadoutHash': ''}}
            body['serverInfo'] = {
                'gameSessionId': a.game_session_id, 'instanceId': a.instance_id,
                'host': a.host, 'port': a.port, 'gameArgs': ''}
        # Deliberately omit serverInfo until a real assignment passes every check.
        return body
