# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only, bounded login diagnosis. Outputs fixed labels, never raw log lines.

No launch, network, trust/config edit or token verification is performed.
Marker matches are diagnostic hints, not proof of a root cause or game login.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import stat
from collections import Counter
from pathlib import Path

REPORT_REVISION = 'login-report-20261011.1'
MAX_BYTES = 2 * 1024 * 1024
MAX_LINE = 16384
MAX_DIRECTORY_ENTRIES = 512

# Output labels below are constants. Input filenames, IDs, URLs and messages
# are never interpolated into the report, including exception messages.
PROBE_STAGES = (
    ('platform_features', 'GET', 'gamesession-prod', '/features/platform/{platform}'),
    ('account_link', 'GET', 'gamesession-prod', '/account/link/epic/{id}'),
    ('account_link', 'GET', 'gamesession-prod', '/account/link/epiceos/{id}'),
    ('login_queue', 'POST', 'login-queue-prod', '/login'),
    ('local_session_response', 'PUT', 'gamesession-prod', '/gamesession/epiceos'),
    ('account_info', 'GET', 'auth-prod', '/accountinfo'),
    ('account_tags', 'GET', 'auth-prod', '/tags'),
    ('ban_state', 'GET', 'auth-prod', '/isbanned'),
    ('character_list', 'GET', 'dauntless-prod', '/character'),
    ('character_create', 'PUT', 'dauntless-prod', '/character'),
    ('character_save', 'POST', 'dauntless-prod', '/character'),
    ('inventory_migration', 'POST', 'dauntless-prod', '/inventory/{character}/{build}'),
    ('inventory_read', 'GET', 'dauntless-prod', '/inventory/{account}/{character}'),
    ('loadout_read', 'GET', 'loadout-prod', '/loadout/{account}/{character}/all'),
    ('matchmaking_request', 'POST', 'mm2-prod', '/candidate/join'),
)
_STAGE_BY_ROUTE = {(m, s, p): label for label, m, s, p in PROBE_STAGES}
_PROBE = re.compile(r'\bmethod=(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH) '
                    r'route=[a-z0-9-]+ status=([1-5][0-9]{2}) '
                    r'service=([a-z0-9-]+) endpoint=(\S+)')

# Case-insensitive, complete known error/result symbols, not a free-form
# EOS_* regular expression that could accidentally disclose a token suffix.
EOS_CODES = (
    'EOS_Success', 'EOS_NoConnection', 'EOS_InvalidCredentials', 'EOS_InvalidAuth',
    'EOS_AccessDenied', 'EOS_MissingPermissions', 'EOS_Auth_AccountLocked',
    'EOS_Auth_InvalidRefreshToken', 'EOS_Auth_InvalidToken',
    'EOS_Auth_AuthenticationFailure', 'EOS_Auth_AccountFeatureRestricted',
    'EOS_Auth_CorrectiveActionRequired', 'EOS_Auth_PinGrantCode',
    'EOS_Auth_MFARequired', 'EOS_Auth_UserInterfaceRequired',
    'EOS_Auth_ExternalAuthNotLinked', 'EOS_Auth_Expired', 'EOS_Canceled',
    'EOS_TimedOut', 'EOS_TooManyRequests', 'EOS_UnexpectedError',
    'EOS_InvalidUser', 'EOS_Connect_ExternalTokenValidationFailed',
)
_RESULT_RULES = tuple((re.compile(r'(?<![\w])' + re.escape(code) + r'(?![\w])', re.I), code)
                      for code in EOS_CODES)
MARKERS = (
    ('login_operation_failed', r'\bLoginOpFailed\b'),
    ('disconnect_error_queued', r'\bEnqueueDisconnectError\b'),
    ('epic_auth_callback', r'\b(?:EOS_Auth_LoginCallbackInfo|OnAuthLoginComplete|OnAuthLoginCallback)\b'),
    ('epic_connect_callback', r'\b(?:EOS_Connect_LoginCallbackInfo|OnConnectLoginComplete)\b'),
    ('character_list_error', r'Failed to get all characters'),
    ('character_data_error', r'Failed To Parse All Required Fields'),
    ('inventory_read_error', r'Failed to retrieve (?:your character.s|player) inventory'),
    ('inventory_read_error', r'Failed to retrieve your character.s inventory'),
    ('loadout_error', r'Loadout (?:active index is invalid|slot data could not be initialized)'),
    ('tls_verification_error', r'(?:certificate verify failed|SSL peer certificate|SSL certificate problem)'),
    ('http_timeout', r'(?:HTTP request timed out|libcurl error:\s*28\b)'),
    ('connection_timeout', r'\b(?:ConnectionTimeout|NetworkFailure)\b'),
    ('client_exit_requested', r'\b(?:RequestExit|Engine exit requested)\b'),
    ('fatal_error', r'\b(?:Fatal error|Unhandled Exception|EXCEPTION_ACCESS_VIOLATION)\b'),
)
_MARKER_RULES = tuple((label, re.compile(pattern, re.I)) for label, pattern in MARKERS)
# Require a log channel, excluding arbitrary raw headers/body-only lines.
_CHANNEL = re.compile(r'\b(?:LogEOSSDK|LogEOS|LogOnline|LogOnlineIdentity|LogOnlineGame|'
                      r'LogOnlineSession|LogHttp|LogSSL|LogNet|LogInit|LogExit|LogWindows|'
                      r'LogCore|LogOutputDevice|LogArchon|LogPhoenix|LogTemp)\s*:', re.I)


def summarize_probe(text: str) -> dict:
    stages, failures, background, unclassified = [], Counter(), Counter(), 0
    session_seen = False
    for line in text.splitlines():
        if len(line) > MAX_LINE:
            continue
        match = _PROBE.search(line)
        if not match:
            continue
        method, code, service, endpoint = match.groups()
        status = int(code)
        label = _STAGE_BY_ROUTE.get((method, service, endpoint))
        if label:
            if 200 <= status <= 206:
                session_seen = session_seen or label == 'local_session_response'
                if not stages or stages[-1] != label:
                    stages.append(label)
                    stages = stages[-32:]
            else:
                failures[(label, status)] += 1
        elif service == 'tracking-prod' and endpoint == '/heartbeat':
            background[('tracking_heartbeat', status)] += 1
        elif service == 'mailbox-prod':
            background[('mailbox_request_unidentified', status)] += 1
        elif method == 'POST' and service == 'dauntless-prod' and endpoint == '/inventory/{account}/{character}':
            # Older diagnostics used incorrect slot names. Do not invent raw values.
            background[('legacy_inventory_post_unidentified', status)] += 1
        elif status >= 400:
            unclassified += 1
    return {
        'observed_successful_http_stage_sequence': stages,
        'local_session_response_seen': session_seen,
        'stage_failures': [{'stage': k, 'status': s, 'count': n} for (k, s), n in sorted(failures.items())],
        'other_requests': [{'kind': k, 'status': s, 'count': n} for (k, s), n in sorted(background.items())],
        'unclassified_failure_count': unclassified,
        'meaning': 'HTTP responses observed, not proof of client parsing or completed game login',
    }


def summarize_client(text: str) -> dict:
    hits = []
    matched, oversized = 0, 0
    for number, line in enumerate(text.splitlines(), 1):
        if len(line) > MAX_LINE:
            oversized += 1
            continue
        if not _CHANNEL.search(line):
            continue
        labels = {label for label, rule in _MARKER_RULES if rule.search(line)}
        labels.update('result_symbol:' + code for rule, code in _RESULT_RULES if rule.search(line))
        if labels:
            matched += 1
            hits.append({'line_in_scanned_text': number, 'markers': sorted(labels)})
            hits = hits[-32:]
    return {
        'recognised_marker_lines': matched,
        'last_marker_lines': hits,
        'oversized_lines_skipped': oversized,
        'meaning': 'Fixed marker matches only. No matches does not exclude an error; EOS_Success alone does not prove game login',
    }


def _plain(path: Path) -> None:
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('unsupported-path')


def read_tail(path: Path) -> tuple[str, dict]:
    _plain(path)
    if not path.is_file():
        raise ValueError('not-regular-file')
    with path.open('rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('not-regular-file')
        prefix = stream.read(3)
        encoding = ('utf-16-le' if prefix.startswith(b'\xff\xfe') else
                    'utf-16-be' if prefix.startswith(b'\xfe\xff') else 'utf-8-sig')
        offset = max(0, info.st_size - MAX_BYTES)
        if encoding.startswith('utf-16'):
            offset -= offset % 2
        stream.seek(offset)
        raw = stream.read(MAX_BYTES)
    text = raw.decode(encoding, errors='replace').lstrip('\ufeff')
    if offset:
        text = text.partition('\n')[2]  # discard the first, possibly partial line
    metadata = {
        'size_bytes': info.st_size,
        'modified_utc': dt.datetime.fromtimestamp(info.st_mtime, dt.timezone.utc).isoformat(),
        'tail_only': bool(offset), 'scanned_bytes': len(raw), 'encoding': encoding,
        'incomplete_final_line_possible': bool(text and not text.endswith(('\n', '\r'))),
    }
    return text, metadata


def _one(path: Path, kind: str) -> dict:
    try:
        text, metadata = read_tail(path)
        summary = summarize_probe(text) if kind == 'probe' else summarize_client(text)
        return {'read_status': 'read', **metadata, **summary}
    except FileNotFoundError:
        return {'read_status': 'not_found'}
    except (OSError, ValueError, OverflowError):
        return {'read_status': 'unreadable_or_unsupported'}


def collect_report(state: Path, game_logs: Path) -> dict:
    """Read current probe plus up to two newest *.log files in one known folder.

    Selection is not evidence that a game log belongs to the current probe run.
    No files or directories are created, modified, moved or uploaded.
    """
    report = {'report_revision': REPORT_REVISION, 'read_only': True,
              'client_log_correlation': 'not_established; game logs selected by modification time',
              'probe_current': _one(state / 'active' / 'probe.log', 'probe'),
              'game_log_scan': 'no_log_files', 'game_logs': []}
    try:
        _plain(game_logs)
        candidates = []
        with os.scandir(game_logs) as items:
            for count, item in enumerate(items):
                if count >= MAX_DIRECTORY_ENTRIES:
                    report['game_log_scan'] = 'directory_limit_no_files_selected'
                    return report
                if item.name.lower().endswith('.log') and item.is_file(follow_symlinks=False):
                    candidates.append((item.stat(follow_symlinks=False).st_mtime_ns, Path(item.path)))
        for index, (_, path) in enumerate(sorted(candidates, key=lambda v: v[0], reverse=True)[:2], 1):
            report['game_logs'].append({'source': 'game_log_' + str(index), **_one(path, 'client')})
        if candidates:
            report['game_log_scan'] = 'selected_up_to_two_latest_logs'
    except FileNotFoundError:
        report['game_log_scan'] = 'log_directory_not_found'
    except (OSError, ValueError):
        report['game_log_scan'] = 'log_directory_unreadable_or_unsupported'
    return report


def main() -> int:
    local = os.environ.get('LOCALAPPDATA')
    if not local:
        print(json.dumps({'report_revision': REPORT_REVISION, 'read_only': True,
                          'status': 'LOCALAPPDATA_not_available'}, indent=2))
        return 0
    report = collect_report(Path(local) / 'DauntlessReawakenedProbe',
                            Path(local) / 'Archon' / 'Saved' / 'Logs')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
