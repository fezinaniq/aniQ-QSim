"""A tiny RCON client (Source RCON protocol, as used by Minecraft servers).

Packet = int32 length | int32 request id | int32 type | payload | 0x00 0x00  (little endian).
Types: 3 = login, 2 = command, 0 = response. A failed login answers with id -1.
Needs `enable-rcon=true`, `rcon.port` and `rcon.password` in server.properties.
"""

from __future__ import annotations

import socket
import struct

from .bridge import BridgeError

TYPE_RESPONSE, TYPE_COMMAND, TYPE_LOGIN = 0, 2, 3


class RconClient:
    def __init__(
        self, host: str = "localhost", port: int = 25575, password: str = "", timeout: float = 5.0
    ) -> None:
        self._next_id = 1
        try:
            self._sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            raise BridgeError(f"cannot reach RCON at {host}:{port}: {exc}") from None
        self._login(password)

    def _send(self, ptype: int, payload: str) -> int:
        req_id = self._next_id
        self._next_id += 1
        body = struct.pack("<ii", req_id, ptype) + payload.encode("utf-8") + b"\x00\x00"
        self._sock.sendall(struct.pack("<i", len(body)) + body)
        return req_id

    def _recv_exact(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self._sock.recv(n - len(data))
            if not chunk:
                raise BridgeError("RCON connection closed")
            data += chunk
        return data

    def _recv(self) -> tuple[int, int, str]:
        (length,) = struct.unpack("<i", self._recv_exact(4))
        body = self._recv_exact(length)
        req_id, ptype = struct.unpack("<ii", body[:8])
        return req_id, ptype, body[8:-2].decode("utf-8", "replace")

    def _login(self, password: str) -> None:
        sent = self._send(TYPE_LOGIN, password)
        try:
            req_id, _, _ = self._recv()
        except OSError as exc:
            raise BridgeError(f"RCON login failed: {exc}") from None
        if req_id == -1 or req_id != sent:
            raise BridgeError("RCON login rejected: wrong rcon.password?")

    def command(self, cmd: str) -> str:
        sent = self._send(TYPE_COMMAND, cmd)
        try:
            req_id, _, text = self._recv()
        except OSError as exc:
            raise BridgeError(f"RCON command failed: {exc}") from None
        if req_id != sent:
            raise BridgeError("RCON reply did not match the request")
        return text

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass
