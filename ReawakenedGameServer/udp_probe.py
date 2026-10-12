"""Loopback-only UDP transport probe; NOT an Unreal NetDriver or game server.

Reports datagram lengths only, never packet contents or peer identifiers.
"""
import argparse
import socket
import time


def listen(port: int, seconds: float) -> int:
    if not 1 <= port <= 65535 or not 0 < seconds <= 300:
        raise ValueError("Invalid port or duration")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", port))
        sock.settimeout(0.25)
        end = time.monotonic() + seconds
        count = 0
        print("Local UDP transport probe ready; NOT a UE game server", flush=True)
        while time.monotonic() < end:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            count += 1
            print(f"datagram={count} bytes={len(data)}", flush=True)
        print(f"completed datagrams={count}", flush=True)
        return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=17777)
    parser.add_argument("--seconds", type=float, default=30)
    args = parser.parse_args()
    listen(args.port, args.seconds)
