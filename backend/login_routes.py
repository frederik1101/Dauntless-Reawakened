# SPDX-License-Identifier: AGPL-3.0-only
"""Narrow candidate alias for the opt-in login port, not an identity verifier.

Evidence: Revived documents /account/link/{service}/{accountid} and the newer
session provider epiceos. Whether the user's unidentified GET uses this alias
is NOT established by the old log. Keep the default Application unchanged.
"""
from __future__ import annotations

import re

_EOS_LINK = re.compile(r'/account/link/epiceos/[A-Za-z0-9_-]{1,256}')


def is_eos_account_link(endpoint: str) -> bool:
    """Match only this one provider and exactly one bounded identity segment.

    No arbitrary provider fallback, trailing slash normalisation, URL decoding
    or authentication shortcut is introduced.
    """
    return isinstance(endpoint, str) and _EOS_LINK.fullmatch(endpoint) is not None
