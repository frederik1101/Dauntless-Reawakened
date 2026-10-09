"""Loopback-only HTTP(S) transport. Does not alter Windows, the game or DNS.

Research EOS identity extraction is explicit opt-in, NOT signature verification.
"""
from __future__ import annotations

import argparse
import ipaddress
import logging
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .application import Application, Response
from .database import Database

LOG = logging.getLogger('reawakened.requests')
MAX_BODY = 1048576


def make_handler(app: Application, *, secure: bool = False):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'
        server_version = 'ReawakenedResearch/0.2'
        sys_version = ''

        def setup(self):
            self.request.settimeout(5)
            super().setup()

        def log_message(self, *_):
            # Base class logs URLs verbatim. Never log tokens, queries, IDs or request bodies.
            pass

        def send_error(self, code, message=None, explain=None):
            self._send(Response(code, route='http-parser'))

        def _send(self, response):
            body = response.body()
            # Record the fixed route before sending the response, so a completed
            # request cannot race ahead of its audit entry in tests/diagnostics.
            method = self.command if self.command in {'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH'} else 'OTHER'
            LOG.info('method=%s route=%s status=%d', method, response.route, response.status)
            self.send_response(response.status)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            if body:
                self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            if self.command != 'HEAD' and body:
                self.wfile.write(body)
            self.close_connection = True

        def _dispatch(self):
            try:
                if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                    return self._send(Response(403, route='non-loopback'))
                for name in ('Host', 'Content-Length', 'Authorization', 'Origin', 'X-Reawakened-Lab-Key'):
                    if len(self.headers.get_all(name, [])) > 1:
                        return self._send(Response(400, route='duplicate-header'))
                if self.headers.get('Transfer-Encoding'):
                    return self._send(Response(400, route='unsupported-transfer-encoding'))
                raw_length = self.headers.get('Content-Length', '0')
                if not raw_length.isascii() or not raw_length.isdecimal() or len(raw_length) > 10:
                    return self._send(Response(400, route='invalid-length'))
                length = int(raw_length)
                if length > MAX_BODY:
                    return self._send(Response(413, route='body-limit'))
                body = self.rfile.read(length)
                if len(body) != length:
                    return self._send(Response(400, route='truncated-body'))
                reply = app.handle(self.command, self.headers.get('Host', ''), self.path,
                                   dict(self.headers.items()), body, secure=secure)
                return self._send(reply)
            except (TimeoutError, socket.timeout):
                self.close_connection = True
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            except Exception:
                # No tracebacks with local data on the public log stream.
                LOG.error('backend-internal-error')
                self._send(Response(500, route='internal-error'))

        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_OPTIONS = do_PATCH = _dispatch
    return Handler


def make_server(app: Application, host: str = '127.0.0.1', port: int = 8765,
                tls: ssl.SSLContext | None = None) -> ThreadingHTTPServer:
    if host not in {'127.0.0.1', '::1'}:
        raise ValueError('Only explicit loopback addresses are allowed')
    class LocalServer(ThreadingHTTPServer):
        address_family = socket.AF_INET6 if host == '::1' else socket.AF_INET
        daemon_threads = False
        allow_reuse_address = False

        def handle_error(self, request, client_address):
            LOG.warning('transport-request-failed')

        def server_bind(self):
            if self.address_family == socket.AF_INET6:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            super().server_bind()

        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(5)
            if tls:
                # Handshake in the request worker, not in the accept loop.
                try:
                    connection = tls.wrap_socket(connection, server_side=True, do_handshake_on_connect=False)
                except Exception:
                    connection.close()
                    raise
            return connection, address

    return LocalServer((host, port), make_handler(app, secure=tls is not None))


def tls_context(cert: str | Path, key: str | Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_alpn_protocols(['http/1.1'])
    context.load_cert_chain(str(cert), str(key))
    return context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='local-data/reawakened.sqlite3')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ipv6', action='store_true', help='Also require an independent ::1 listener')
    parser.add_argument('--cert')
    parser.add_argument('--key')
    parser.add_argument('--allow-unverified-eos-sub', action='store_true',
                        help='LOCAL RESEARCH ONLY: read an unverified JWT subject; not authentication')
    args = parser.parse_args()
    if bool(args.cert) != bool(args.key):
        parser.error('--cert and --key must be supplied together')
    if not 1 <= args.port <= 65535:
        parser.error('Invalid port')
    if args.allow_unverified_eos_sub and not args.cert:
        parser.error('Research EOS identity extraction requires TLS')
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    database = None
    servers, workers = [], []
    try:
        context = tls_context(args.cert, args.key) if args.cert else None
        database = Database(args.data)
        app = Application(database, allow_unverified_eos_sub=args.allow_unverified_eos_sub)
        # Bind every listener before starting any; do not leave a partial stack running.
        for host in ['127.0.0.1'] + (['::1'] if args.ipv6 else []):
            servers.append(make_server(app, host, args.port, context))
        for server in servers:
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
            thread.start()
            workers.append(thread)
        print('Local research backend running. Game compatibility: NOT VERIFIED.', flush=True)
        if args.allow_unverified_eos_sub:
            print('WARNING: JWT subjects are lookup keys only. This is NOT Epic authentication.', flush=True)
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as error:
        parser.exit(1, f'Could not start local backend: {error}\n')
    finally:
        for server in servers[:len(workers)]:
            server.shutdown()
        for server in servers:
            server.server_close()
        for thread in workers:
            thread.join(timeout=6)
        if database:
            database.close()


if __name__ == '__main__':
    main()
