"""Pure 2.1.1 login response-shape helpers.

Based on publicly documented observations, not on a copied proprietary SDK.
These helpers are not a complete authentication service.
"""
from __future__ import annotations


def features() -> dict:
    flags = {"crossplay": True, "crossprogression": True}
    return {**flags, "code": "OK", "message": "", "payload": flags}


def account_info(account_id: str, username: str) -> dict:
    if not account_id or not username:
        raise ValueError("account_id and username required")
    return {"username": username, "accountId": account_id}


def character_seed() -> str:
    """Every value is a string. Avoid HasFinishedTutorial key."""
    import json
    return json.dumps({"PlayerAccountProgressStep": "EnteredRamsgate"})


def game_session_response(session_id: str, session_token: str) -> dict:
    if not session_id or not session_token:
        raise ValueError("Session identifiers required")
    return {"code": "OK", "message": "", "payload": {
        "sessionid": session_id, "sessiontoken": session_token,
    }}
