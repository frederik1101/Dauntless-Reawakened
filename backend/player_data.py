"""Documented 2.1.1 initial player-data reads, not functioning gameplay systems.

Loadout /all: upstream live shape. Inventory/progression: static contract evidence.
See docs/PLAYER_DATA_READS.md for every implemented route and its limitations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadRoute:
    label: str
    account: str | None = None
    character: str | None = None
    season: str | None = None


def match_read(service: str, endpoint: str) -> ReadRoute | None:
    # Bounded patterns prevent path fragments from entering SQL, logs or telemetry.
    identity = r'([^/]{1,256})'
    routes = [
        ('dauntless-prod', r'/inventory/' + identity + '/' + identity, 'inventory-bootstrap'),
        ('loadout-prod', r'/loadout/' + identity + '/' + identity + r'/all', 'loadouts-bootstrap'),
        ('loadout-prod', r'/loadout/' + identity + '/' + identity + r'/slotcount', 'loadout-slots'),
        ('loadout-prod', r'/loadout/' + identity + r'/slotcount', 'loadout-slots'),
        ('progression-prod', r'/progression/config', 'progression-config-bootstrap'),
        ('progression-prod', r'/progression/objectives/' + identity, 'progression-objectives-bootstrap'),
        ('progression-prod', r'/progression/' + identity, 'progression-tracks-bootstrap'),
        ('progression-prod', r'/cooldown/' + identity, 'cooldowns-bootstrap'),
        ('progression-prod', r'/bounty/' + identity, 'bounties-bootstrap'),
    ]
    for expected_service, pattern, label in routes:
        if expected_service != service:
            continue
        match = re.fullmatch(pattern, endpoint)
        if match:
            values = match.groups()
            return ReadRoute(label, values[0] if values else None,
                             values[1] if len(values) > 1 else None)
    if service == 'progression-prod':
        match = re.fullmatch(r'/escalation/(ESC_SEASON_[1-6])/' + identity, endpoint)
        if match:
            return ReadRoute('escalation-bootstrap', account=match[2], season=match[1])
    return None


def wrapped(payload: object, *, code: str | int = 'OK') -> dict:
    return {'code': code, 'message': '', 'payload': payload}


def slot_counts() -> dict:
    return {'num_account_slots': 1, 'max_account_slots': 5,
            'num_character_slots': 0, 'max_character_slots': 0}


def initial_loadouts() -> dict:
    # Empty slots let the client read its own DefaultLoadout. -1 is deliberate:
    # upstream reports an access violation with active_index=0 and an empty list.
    persistent = {name: '' for name in (
        'intro_emote', 'banner', 'bannerCustomization', 'flare', 'title',
        'head_accessory', 'back_accessory', 'pet', 'glider')}
    persistent.update({name: [] for name in (
        'manual_emotes', 'quick_chats', 'emojis', 'quick_curiosities_items', 'quickwheel')})
    persistent['update_version'] = 0
    return wrapped({'loadouts': [], 'persistent': persistent, **slot_counts(),
                    'active_index': -1, 'needs_migration': False})


def initial_progression(label: str) -> dict:
    # Shape-correct initial research state, never evidence of functioning XP,
    # unlocks, bounties, mastery, Escalations or reward logic.
    if label == 'progression-config-bootstrap':
        return wrapped({'paths': []})
    if label in {'progression-tracks-bootstrap', 'progression-objectives-bootstrap'}:
        return wrapped([], code=200)  # These two readers expect int32, not "OK".
    if label == 'cooldowns-bootstrap':
        return {'cooldowns': []}
    if label == 'bounties-bootstrap':
        return {'bounties': [], 'draft_data': {
            'current_draft_choices': [], 'previous_draft_selections': [],
            'bronze_count': 0, 'silver_count': 0, 'gold_count': 0}}
    if label == 'escalation-bootstrap':
        return wrapped({'escalation_level': 0, 'next_level_xp': 0,
                        'talents_progress': [], 'unlock_progress': [], 'update_version': 0})
    raise ValueError('Unknown bootstrap shape')
