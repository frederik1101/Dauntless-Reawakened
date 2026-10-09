"""Loopback-only 2.1.1 contract prototype. NOT a real authentication or game server.

All account and character endpoints use an explicitly hard-coded demo identity.
Never expose this service to the internet or route a real game client to it.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from .contract import login_queue, linked_account
from .persistence import JsonCharacterRepository
from .protocol_211 import account_info, character_seed, features, game_session_response
from .sessions import DemoSessionManager

HOST = "127.0.0.1"
PORT = 8765
DEMO_ACCOUNT = "offline-demo-account"
DATA_FILE = Path(__file__).resolve().parent.parent / "local-data" / "characters.json"
store = JsonCharacterRepository(DATA_FILE)
sessions = DemoSessionManager()


class Handler(BaseHTTPRequestHandler):
    def respond(self, status: int, payload) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond_empty_404(self) -> None:
        """Unknown routes must have a body-less 404 (per 2.1.1 findings)."""
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def read_json(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 65536:
                raise ValueError("invalid content length")
            return json.loads(self.rfile.read(size))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("invalid JSON request")

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            return self.respond(200, {"status": "ok", "game_compatible": False})
        if path == "/gamesession-prod/features/platform/win":
            return self.respond(200, features())
        if path.startswith("/gamesession-prod/account/link/epic/") and path.rsplit("/", 1)[-1]:
            return self.respond(200, linked_account())
        if path == "/auth-prod/accountinfo":
            return self.respond(200, account_info(DEMO_ACCOUNT, "LocalSlayer"))
        if path == "/dauntless-prod/character":
            return self.respond(200, store.get(DEMO_ACCOUNT))
        return self.respond_empty_404()

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/login-queue-prod/login":
            return self.respond(200, login_queue())
        if path == "/dauntless-prod/character":
            try:
                body = self.read_json()
                character_id = body["id"]
                data = body["data"]
                version = body["updateVersion"]
                return self.respond(200, store.save(DEMO_ACCOUNT, character_id, data, version))
            except (ValueError, KeyError, TypeError):
                return self.respond(400, {"error": "invalid_character_update"})
        return self.respond(404, {"error": "not_implemented"})

    def do_PUT(self) -> None:
        if urlsplit(self.path).path == "/gamesession-prod/gamesession/epiceos":
            # Explicitly offline demo fixture. Does not validate EOS credentials.
            session = sessions.create(DEMO_ACCOUNT)
            return self.respond(200, game_session_response(session.session_id, session.session_token))
        if urlsplit(self.path).path != "/dauntless-prod/character":
            return self.respond(404, {"error": "not_implemented"})
        try:
            body = self.read_json()
            created = store.create(DEMO_ACCOUNT, body["name"])
            # Set the documented initial progress state, with a client-supplied
            # version number of 1 in this isolated fixture.
            store.save(DEMO_ACCOUNT, created["id"], character_seed(), 1)
            return self.respond(200, created)
        except (ValueError, KeyError, TypeError):
            return self.respond(400, {"error": "invalid_character"})


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Offline contract prototype: http://{HOST}:{PORT}/health")
    print("No EOS authentication, HTTPS, real session, client compatibility or gameplay.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
