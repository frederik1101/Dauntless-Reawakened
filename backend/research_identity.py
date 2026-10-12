# SPDX-License-Identifier: AGPL-3.0-only
"""Typed identity projection for the explicitly enabled loopback experiment.

This module DOES NOT authenticate Epic, verify a signature, or assert ownership.
It extracts only a bounded subject and an explicit external-account claim from
one token already submitted to our local research exchange. Tokens and arbitrary
claims are not retained. Never use this parser for an Internet-facing service.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

KINDS = frozenset({'legacy_subject', 'auth_subject', 'connect_epic_actor',
                   'connect_other_actor', 'unusable_actor'})


def identity_string(value: object) -> bool:
    return (isinstance(value, str) and 1 <= len(value) <= 256
            and all(33 <= ord(c) <= 126 for c in value))


def same_identity(left: object, right: object) -> bool:
    """Preserve opaque IDs; compare 32-hex representations case-insensitively.

    No UUID rewriting, trimming, prefixes, substring matches or namespace aliases.
    In particular a PUID does not become an Epic ID just because it is 32 hex.
    """
    if not identity_string(left) or not identity_string(right):
        return False
    if left == right:
        return True
    return (re.fullmatch(r'[0-9a-fA-F]{32}', left) is not None
            and re.fullmatch(r'[0-9a-fA-F]{32}', right) is not None
            and left.lower() == right.lower())


@dataclass(frozen=True)
class ResearchIdentity:
    subject: str = field(repr=False)
    epic_id: str | None = field(repr=False)
    kind: str

    def __post_init__(self):
        if (not identity_string(self.subject) or self.kind not in KINDS or
                (self.epic_id is not None and not identity_string(self.epic_id))):
            raise ValueError('Invalid research identity projection')

    def summary(self) -> dict:
        return {'source': self.kind, 'verified': False,
                'epic_binding_present': self.epic_id is not None,
                'epic_differs_from_subject': (None if self.epic_id is None else
                                              not same_identity(self.subject, self.epic_id))}


def parse_research_identity(token: str) -> ResearchIdentity:
    """Strict, bounded JSON parsing; preserve the EXACT existing DB subject key.

    Supported Connect-shaped claim: act={eat:'epicgames',eaid:'external-id'}.
    If act is present but is not an explicit usable Epic actor, do NOT silently
    substitute the product subject as an Epic account. For tokens without act,
    retain the old subject fallback, prominently labelled legacy/unclassified
    unless the issuer has the Auth service shape. These are shape observations,
    NOT issuer/signature validation. The next real-client trace must establish
    which of these cases actually applies to the affected client.
    """
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate claim')
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError('Nonfinite claim')

    try:
        if not isinstance(token, str) or not 1 <= len(token) <= 16384:
            raise ValueError()
        parts = token.split('.')
        if len(parts) != 3 or not all(re.fullmatch(r'[A-Za-z0-9_-]+', p) for p in parts):
            raise ValueError()
        raw = base64.b64decode(parts[1] + '=' * (-len(parts[1]) % 4),
                               altchars=b'-_', validate=True)
        if len(raw) > 12288:
            raise ValueError()
        claims = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
        if not isinstance(claims, dict) or not identity_string(claims.get('sub')):
            raise ValueError()
        subject = claims['sub']
        if 'act' in claims:
            actor = claims['act']
            if not isinstance(actor, dict):
                return ResearchIdentity(subject, None, 'unusable_actor')
            if actor.get('eat') != 'epicgames':
                return ResearchIdentity(subject, None, 'connect_other_actor')
            epic = actor.get('eaid')
            if not identity_string(epic):
                return ResearchIdentity(subject, None, 'unusable_actor')
            return ResearchIdentity(subject, epic, 'connect_epic_actor')
        issuer = claims.get('iss')
        kind = 'legacy_subject'
        if isinstance(issuer, str) and len(issuer) <= 256:
            parsed = urlsplit(issuer)
            if (parsed.scheme == 'https' and parsed.netloc == 'api.epicgames.dev'
                    and parsed.path.startswith('/epic/')):
                kind = 'auth_subject'
        return ResearchIdentity(subject, subject, kind)
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
        raise ValueError('Invalid local research identity token') from None
