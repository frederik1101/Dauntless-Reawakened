"""Loopback-only HTTP contract test server, NOT a playable Dauntless server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlsplit

try:
    from .contract import CharacterStore, login_queue, linked_account
except ImportError:
    from contract import CharacterStore, login_queue, linked_account

HOST = "127.0.0.1"
PORT = 8765
store = CharacterStore()


class Handler(BaseHTTPRequestHandler):
    def respond(self, status: int, payload) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            return self.respond(200, {"status": "ok", "game_compatible": False})
        if path == "/gamesession-prod/account/link/epic/demo":
            return self.respond(200, linked_account())
        if path == "/dauntless-prod/character":
            return self.respond(200, store.list())
        return self.respond(404, {"error": "not_implemented"})

    def do_POST(self) -> None:
        if urlsplit(self.path).path == "/login-queue-prod/login":
            return self.respond(200, login_queue())
        return self.respond(404, {"error": "not_implemented"})

    def do_PUT(self) -> None:
        if urlsplit(self.path).path != "/dauntless-prod/character":
            return self.respond(404, {"error": "not_implemented"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 8192 or length < 1:
                return self.respond(413, {"error": "invalid_size"})
            body = json.loads(self.rfile.read(length))
            return self.respond(200, store.create(body["name"]))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return self.respond(400, {"error": "invalid_character"})


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Dauntless Reawakened contract prototype: http://{HOST}:{PORT}/health")
    print("Loopback only. No TLS, EOS authentication, game session or gameplay support.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
