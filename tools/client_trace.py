# SPDX-License-Identifier: AGPL-3.0-only
"""Drain the OWNED client's stdout; retain only fixed, bounded error markers.

No raw lines, URLs, exception text, IDs or tokens are persisted. The stock client
may ignore logging flags; an empty report is INCONCLUSIVE, not a successful login.
This is ordinary subprocess output handling, not injection or a memory patch.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import re
import threading
import time

# The singular FullStdOutLogOutput and the other flag names occur in the reviewed
# 2.1.1 image. Literal presence is not evidence that a shipping build enables them.
TRACE_FLAGS = ('-stdout', '-FullStdOutLogOutput', '-FORCELOGFLUSH', '-UTF8Output')
MAX_LINE_BYTES = 16384
MAX_CHUNK_BYTES = 4096
MAX_COUNT = 100000
MAX_EVENTS = 64
LOG_PREFIX = re.compile(r'^(?:\[[^\]\r\n]{0,80}\])*\s*Log[A-Za-z0-9_]{1,80}:')
MARKERS = (
    ('character_required_fields_missing', 'OnGetHttpRequestComplete Failed To Parse All Required Fields'),
    ('character_data_wrong_type', 'Data Field Is Not A String Or Null'),
    ('character_save_data_missing', 'OnSetHttpRequestComplete Failed To Parse, Missing Data Field'),
    ('character_version_conflict', 'Conflict Detected, Clearing Cache & Retrying'),
    ('character_deserialization_failed', 'Failed To Deserialize Response'),
    ('login_operation_failed', 'LoginOperation Failed - Error ='),
    ('login_data_read_failed', 'return from character data was not successful'),
    ('login_flag_write_failed', 'error setting flag value'),
    ('login_time_write_failed', 'RecordLoginTime: Unable to write character data'),
    ('player_progress_flag_write_failed', 'Failed to update player account progress flag'),
    ('json_type_mismatch', "Json Value of type"),
    ('login_queue_parse_failed', 'Failed to deserialize a response from the query login queue endpoint'),
    ('login_queue_connect_failed', 'Failed to connect to the query login queue endpoint'),
    ('inventory_read_failed', "Failed to retrieve your character's inventory"),
    ('inventory_load_failed', 'Failed to retrieve player inventory'),
    ('xmpp_login_failed', 'OnXmppLoginComplete: XMPP login failed'),
    ('xmpp_login_success', 'OnXmppLoginComplete: XMPP login sucess'),
    ('native_network_failure', 'BroadcastNetworkFailure'),
    ('native_disconnect_message', 'Disconnect Error Message:'),
    ('native_disconnect_enqueued', 'EnqueueDisconnectError'),
    ('native_login_callbacks_finished', 'FOnlineIdentityPhoenix - LoginCompleteCallbacksFinished'),
)


def classify_line(line: bytes) -> tuple[str, ...]:
    if not isinstance(line, bytes) or len(line) > MAX_LINE_BYTES:
        return ()
    # UTF8Output is requested, but tolerate an ASCII UTF-16LE log line without
    # retaining the original. Do not try arbitrary character-set guessing.
    if b'\x00' in line:
        line = line.replace(b'\x00', b'')
    text = line.decode('utf-8', errors='replace').lstrip('\ufeff')
    if not LOG_PREFIX.match(text):
        return ()
    result = [label for label, literal in MARKERS if literal in text]
    if 'UTuningDataProvider' in text and ('failed to load' in text or 'failed' in text.lower()):
        result.append('game_tuning_load_failed')
    if 'FUserManagerEOS' in text and 'failed' in text.lower():
        result.append('eos_user_manager_failed')
    if 'Failed to refresh ConnectLogin' in text:
        result.append('eos_connect_refresh_failed')
    # Preserve cancellation only when the error itself explicitly names it.
    # Never infer cancellation merely from a generic failure or the user closing.
    cancellation = re.search(r'LoginOperation Failed - Error = (?:EOS_)?(?:Canceled|Cancelled|UserCanceled|UserCancelled)(?=$|[\s,;])', text)
    if cancellation:
        result.append('login_cancelled_explicit')
    # Fixed hints from the actual failure line; never persist arbitrary errors.
    anchor = 'LoginOperation Failed - Error ='
    if anchor in text:
        reason = text.split(anchor, 1)[1][:256].lower()
        if 'character' in reason:
            result.append('login_error_text_mentions_character')
        if 'compatib' in reason:
            result.append('login_error_text_mentions_compatibility')
        if 'version' in reason or 'changelist' in reason:
            result.append('login_error_text_mentions_version')
        if 'timeout' in reason or 'timedout' in reason:
            result.append('login_error_text_mentions_timeout')
        if 'account' in reason:
            result.append('login_error_text_mentions_account')
        if 'eos_' in reason or 'epic' in reason:
            result.append('login_error_text_mentions_epic')
    # A marker means the LINE was observed, not that its message is authoritative.
    return tuple(dict.fromkeys(result))


class ClientTrace:
    def __init__(self):
        self._lock = threading.Lock()
        self._pending = bytearray()
        self._dropping = False
        self._started = time.monotonic()
        self._counts = {}
        self._events = deque(maxlen=MAX_EVENTS)
        self._bytes = self._lines = self._oversized = 0
        self._state = 'not_started'
        self._worker = None

    def feed(self, chunk: bytes) -> None:
        if not isinstance(chunk, bytes):
            raise TypeError('Client trace expects bytes')
        with self._lock:
            self._bytes = min(self._bytes + len(chunk), 2**63 - 1)
            # Chunk iterating bounds intermediate storage even for a faulty reader.
            for offset in range(0, len(chunk), MAX_CHUNK_BYTES):
                for part in chunk[offset:offset + MAX_CHUNK_BYTES].splitlines(keepends=True):
                    newline = part.endswith(b'\n') or part.endswith(b'\r')
                    if not self._dropping:
                        if len(self._pending) + len(part) > MAX_LINE_BYTES:
                            self._pending.clear()
                            self._dropping = True
                            self._oversized = min(self._oversized + 1, MAX_COUNT)
                        else:
                            self._pending.extend(part)
                    if newline:
                        if not self._dropping:
                            self._line(bytes(self._pending))
                        self._pending.clear()
                        self._dropping = False

    def _line(self, line: bytes) -> None:
        self._lines = min(self._lines + 1, MAX_COUNT)
        for label in classify_line(line):
            self._counts[label] = min(self._counts.get(label, 0) + 1, MAX_COUNT)
            self._events.append({
                'label': label,
                'observed_utc': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                'elapsed_seconds': round(time.monotonic() - self._started, 3),
            })

    def eof(self) -> None:
        with self._lock:
            if self._pending and not self._dropping:
                self._line(bytes(self._pending))
            self._pending.clear()
            self._dropping = False
            self._state = 'eof'

    def start(self, stream) -> None:
        if stream is None or self._worker is not None:
            raise ValueError('Client trace needs one owned process pipe')
        self._state = 'reading'

        def drain():
            try:
                reader = getattr(stream, 'read1', stream.read)
                while True:
                    chunk = reader(MAX_CHUNK_BYTES)
                    if not chunk:
                        self.eof()
                        break
                    self.feed(chunk)
            except (OSError, ValueError, TypeError):
                with self._lock:
                    self._pending.clear()
                    self._state = 'pipe_read_error'
            finally:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass

        self._worker = threading.Thread(target=drain, name='owned-client-log-drain', daemon=True)
        self._worker.start()

    def finish(self, timeout: float = 2.0) -> dict:
        if self._worker is not None:
            self._worker.join(timeout)
        return self.report()

    def report(self) -> dict:
        with self._lock:
            return {
                'source': 'owned_client_stdout', 'raw_lines_retained': False,
                'stream_status': self._state,
                'bytes_observed': self._bytes, 'lines_observed': self._lines,
                'oversized_lines_discarded': self._oversized,
                'marker_counts': dict(self._counts),
                'recent_markers': [dict(event) for event in self._events],
                'meaning': 'Marker observations only; no markers or no output is inconclusive. '
                           'Neither login nor gameplay is verified by this report.',
            }

# Exact log-message literals present in the supplied 2.1.1 image. Presence in
# the image establishes spelling only, not that a particular branch executed.
MARKERS += (
    ('identity_mapping_empty', 'FOnlineUserPhoenix::QueryExternalIdMappings - No Valid mappings came back'),
    ('identity_mapping_request_failed', 'QueryExternalIdMappings request failed.'),
    ('identity_mapping_callback', 'FOnlineUserPhoenix::QueryExternalIdMappings - OnPhoenixMappingComplete'),
    ('login_user_account_unavailable', 'FArchonAdditionalLoginSteps::CheckCharacterCompatibility: Unable to retrieve user account.'),
    ('login_attributes_user_id_unavailable', 'ResolveUserAttributesOnLogin: Unable to get user ID for local player'),
    ('login_attributes_account_unavailable', 'ResolveUserAttributesOnLogin: Unable to get user account for local player'),
    ('login_attributes_character_unavailable', 'ResolveUserAttributesOnLogin: Unable to get character ID for local player'),
    ('login_time_read_failed', 'RecordLoginTime: Unable to read character data'),
    ('login_time_saved', 'RecordLoginTime: New login time set successfully'),
    ('login_previous_time_saved', 'RecordLoginTime: Last login time & last changelist set successfully'),
)

# Reviewed 2.1.1 literals; observation is NOT proof of completed migration/login.
MARKERS += (
    ('migration_trigger_no_response', 'Trigger from service sent no response'),
    ('migration_response_invalid', 'Player Data Migration Failed with invalid response'),
    ('migration_not_finished', "Data migration rework - migration didn't finish"),
    ('inventory_migration_failed', 'FAILED INVENTORY MIGRATION'),
    ('character_previous_build_missing', "Character's last active session was on an unknown CL."),
    ('character_previous_build_checked', "Character's last active session was on changelist"),
)
