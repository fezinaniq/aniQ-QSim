"""Tiny fake servers speaking the RaspberryJuice and RCON wire protocols over real TCP.

They validate OUR client code (framing, parsing, batching). They cannot prove the real
plugin behaves identically; `python -m mc selftest` is the check against a real server.
"""

from __future__ import annotations

import socket
import struct
import threading

LEVER_ID = "LEVER"  # the server speaks modern material names, like the real RaspberryJuice fork


def _material(token: str):
    """Material names stay strings; bare numbers stay ints (so tests can plant unknown ids)."""
    token = token.strip()
    return int(token) if token.lstrip("-").isdigit() else token


class FakeJuiceServer:
    def __init__(self, player=(5, 70, 5)) -> None:
        self.blocks: dict[tuple[int, int, int], tuple[int | str, int]] = {}
        self.received: list[str] = []
        self.chat: list[str] = []
        self.hits: list[tuple[int, int, int]] = []
        self.player = player
        self.trailing_comma = False
        self._srv = socket.socket()
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(5)
        self.port = self._srv.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn) -> None:
        buf = b""
        with conn:
            while True:
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    reply = self._handle(line.decode())
                    if reply is not None:
                        conn.sendall((reply + "\n").encode())

    def _handle(self, line: str):
        self.received.append(line)
        name, _, rest = line.partition("(")
        arg = rest[:-1]
        nums = [a for a in arg.split(",")] if arg else []
        if name == "world.setBlock":
            x, y, z = (int(v) for v in nums[:3])
            self.blocks[(x, y, z)] = (_material(nums[3]), int(nums[4]))
        elif name == "world.setBlocks":
            x1, y1, z1, x2, y2, z2 = (int(v) for v in nums[:6])
            i, d = _material(nums[6]), int(nums[7])
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    for z in range(min(z1, z2), max(z1, z2) + 1):
                        self.blocks[(x, y, z)] = (i, d)
        elif name == "world.getBlock":
            x, y, z = (int(v) for v in nums[:3])
            return str(self.blocks.get((x, y, z), ("AIR", 0))[0])
        elif name == "world.getBlockWithData":
            x, y, z = (int(v) for v in nums[:3])
            i, d = self.blocks.get((x, y, z), ("AIR", 0))
            return f"{i},{d}"
        elif name == "world.getBlocks":
            x1, y1, z1, x2, y2, z2 = (int(v) for v in nums[:6])
            out = []
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for x in range(min(x1, x2), max(x1, x2) + 1):
                    for z in range(min(z1, z2), max(z1, z2) + 1):
                        out.append(str(self.blocks.get((x, y, z), ("AIR", 0))[0]))
            return ",".join(out) + ("," if self.trailing_comma else "")
        elif name == "player.getTile":
            return ",".join(str(c) for c in self.player)
        elif name == "events.block.hits":
            out = "|".join(f"{x},{y},{z},1,1" for x, y, z in self.hits)
            self.hits.clear()
            return out
        elif name == "chat.post":
            self.chat.append(arg)
        elif name in ("events.clear", "auth"):
            pass
        else:
            return "Fail"
        return None

    def close(self) -> None:
        self._srv.close()


class FakeRconServer:
    def __init__(self, password="secret", responder=None) -> None:
        self.password = password
        self.commands: list[str] = []
        self.responder = responder or (lambda cmd: "")
        self._srv = socket.socket()
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(5)
        self.port = self._srv.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    @staticmethod
    def _read(conn):
        head = b""
        while len(head) < 4:
            c = conn.recv(4 - len(head))
            if not c:
                return None
            head += c
        (n,) = struct.unpack("<i", head)
        body = b""
        while len(body) < n:
            body += conn.recv(n - len(body))
        rid, ptype = struct.unpack("<ii", body[:8])
        return rid, ptype, body[8:-2].decode()

    @staticmethod
    def _send(conn, rid, ptype, text):
        body = struct.pack("<ii", rid, ptype) + text.encode() + b"\x00\x00"
        conn.sendall(struct.pack("<i", len(body)) + body)

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn) -> None:
        with conn:
            while True:
                pkt = self._read(conn)
                if pkt is None:
                    return
                rid, ptype, text = pkt
                if ptype == 3:
                    self._send(conn, rid if text == self.password else -1, 2, "")
                elif ptype == 2:
                    self.commands.append(text)
                    self._send(conn, rid, 0, self.responder(text))

    def close(self) -> None:
        self._srv.close()
