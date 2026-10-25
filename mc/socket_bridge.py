"""SocketBridge: talks to a real server through the RaspberryJuice (mcpi) socket protocol.

Written from scratch on plain sockets (no mcpi dependency). The protocol is text lines:
    world.setBlock(x,y,z,id,data)       world.setBlocks(x1,y1,z1,x2,y2,z2,id,data)
    world.getBlock(x,y,z)    -> id      world.getBlockWithData(x,y,z) -> id,data
    world.getBlocks(x1,y1,z1,x2,y2,z2)  -> id,id,id,...
    player.getTile()         -> x,y,z   events.block.hits() -> x,y,z,face,entity|...
    chat.post(msg)           events.clear()

Setup requirements (see docs/PHASE2_SETUP.md): the plugin must use `location: ABSOLUTE`
so socket coordinates agree with RCON/vanilla commands. RCON is optional, but gives a
reliable lever read (modern block state) and lets us run commands.
"""

from __future__ import annotations

import socket

from .blocks import LEVER_FLOOR_DATA, LEVER_ID, LEVER_POWERED_BIT, legacy, name_from_id
from .bridge import BridgeError, WorldBridge, ascii_safe
from .config import Pos
from .rcon import RconClient


def _check_pos(pos: Pos) -> None:
    if len(pos) != 3 or not all(isinstance(c, int) for c in pos):
        raise ValueError(f"position must be three ints, got {pos!r}")


class SocketBridge(WorldBridge):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 4711,
        token: str | None = None,
        timeout: float = 5.0,
        rcon: RconClient | None = None,
        lever_mode: str = "auto",
    ) -> None:
        if lever_mode not in ("auto", "rcon", "socket"):
            raise ValueError("lever_mode must be 'auto', 'rcon' or 'socket'")
        self.rcon = rcon
        self.lever_mode = lever_mode
        self._buf = b""
        self._timeout = timeout
        try:
            self._sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            raise BridgeError(
                f"cannot reach the RaspberryJuice socket at {host}:{port}: {exc}"
            ) from None
        if token:
            self._send(f"auth({token})")

    # ---- low-level protocol ------------------------------------------------

    def _drain(self) -> None:
        """Throw away stale replies (e.g. 'Fail' lines) so reads stay in step."""
        self._sock.settimeout(0.0)
        try:
            while True:
                if not self._sock.recv(4096):
                    raise BridgeError("server closed the connection")
        except (TimeoutError, BlockingIOError):
            pass
        finally:
            self._sock.settimeout(self._timeout)
        self._buf = b""

    def _send(self, *lines: str) -> None:
        data = "".join(line.replace("\n", " ") + "\n" for line in lines).encode("utf-8")
        try:
            self._sock.sendall(data)
        except OSError as exc:
            raise BridgeError(f"lost connection while sending: {exc}") from None

    def _recv_line(self) -> str:
        while b"\n" not in self._buf:
            try:
                chunk = self._sock.recv(65536)
            except OSError as exc:
                raise BridgeError(f"no reply from server: {exc}") from None
            if not chunk:
                raise BridgeError("server closed the connection")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        return line.decode("utf-8", "replace").strip()

    def _ask(self, command: str) -> str:
        self._drain()
        self._send(command)
        reply = self._recv_line()
        if reply == "Fail":
            raise BridgeError(f"server refused: {command}")
        return reply

    # ---- WorldBridge -------------------------------------------------------

    def get_block(self, pos: Pos) -> str:
        _check_pos(pos)
        reply = self._ask(f"world.getBlock({pos[0]},{pos[1]},{pos[2]})").strip()
        val = int(reply) if reply.lstrip("-").isdigit() else reply
        return name_from_id(val)

    def get_region(self, a: Pos, b: Pos) -> dict[Pos, str]:
        """One getBlocks call per x-line (fixed y and z). A line has only one varying axis,
        so the order of the reply is unambiguous whatever nesting the plugin uses."""
        _check_pos(a)
        _check_pos(b)
        x1, x2 = sorted((a[0], b[0]))
        out: dict[Pos, str] = {}
        for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
            for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                reply = self._ask(f"world.getBlocks({x1},{y},{z},{x2},{y},{z})")
                raw_items = [t.strip() for t in reply.split(",") if t.strip()]
                ids = [int(t) if t.lstrip("-").isdigit() else t for t in raw_items]
                if len(ids) != x2 - x1 + 1:
                    raise BridgeError(
                        f"getBlocks returned {len(ids)} blocks, expected {x2 - x1 + 1}"
                    )
                for x, block_id in zip(range(x1, x2 + 1), ids, strict=True):
                    out[(x, y, z)] = name_from_id(block_id)
        return out

    def set_block(self, pos: Pos, block: str) -> None:
        _check_pos(pos)
        bid, data = legacy(block)
        self._send(f"world.setBlock({pos[0]},{pos[1]},{pos[2]},{bid},{data})")

    def fill(self, a: Pos, b: Pos, block: str) -> None:
        _check_pos(a)
        _check_pos(b)
        bid, data = legacy(block)
        self._send(f"world.setBlocks({a[0]},{a[1]},{a[2]},{b[0]},{b[1]},{b[2]},{bid},{data})")

    def lever_powered(self, pos: Pos) -> bool:
        _check_pos(pos)
        use_rcon = self.rcon is not None and self.lever_mode in ("auto", "rcon")
        if self.lever_mode == "rcon" and self.rcon is None:
            raise BridgeError("lever_mode='rcon' but no RCON connection")
        if use_rcon:
            reply = self.rcon.command(  # type: ignore[union-attr]
                f"execute if block {pos[0]} {pos[1]} {pos[2]} minecraft:lever[powered=true]"
            )
            return "passed" in reply.lower()
        reply = self._ask(f"world.getBlockWithData({pos[0]},{pos[1]},{pos[2]})")
        block_id, _, data = reply.partition(",")
        block_id_str = block_id.strip()
        is_lever = (block_id_str == str(LEVER_ID) or block_id_str.upper().replace("MINECRAFT:", "") == "LEVER")
        data_str = (data or "").strip()
        if data_str.lstrip("-").isdigit():
            powered = bool(int(data_str) & LEVER_POWERED_BIT)
        else:
            powered = "powered=true" in data_str.lower() or "true" in data_str.lower()
        return is_lever and powered

    def set_lever(self, pos: Pos, powered: bool) -> None:
        _check_pos(pos)
        if self.rcon is not None and self.lever_mode in ("auto", "rcon"):
            state = "true" if powered else "false"
            self.rcon.command(
                f"setblock {pos[0]} {pos[1]} {pos[2]} "
                f"minecraft:lever[face=floor,facing=north,powered={state}]"
            )
        else:
            data = LEVER_FLOOR_DATA + (LEVER_POWERED_BIT if powered else 0)
            self._send(f"world.setBlock({pos[0]},{pos[1]},{pos[2]},{LEVER_ID},{data})")

    def poll_hits(self) -> list[Pos]:
        reply = self._ask("events.block.hits()")
        hits: list[Pos] = []
        for item in reply.split("|"):
            parts = item.split(",")
            if len(parts) >= 3 and all(p.strip().lstrip("-").isdigit() for p in parts[:3]):
                hits.append((int(parts[0]), int(parts[1]), int(parts[2])))
        return hits

    def say(self, msg: str) -> None:
        self._send(f"chat.post({ascii_safe(msg)})")

    def get_player_tile(self) -> Pos:
        reply = self._ask("player.getTile()")
        try:
            x, y, z = (int(float(v)) for v in reply.split(","))
        except ValueError:
            raise BridgeError(f"unexpected reply to player.getTile(): {reply!r}") from None
        return (x, y, z)

    @property
    def has_commands(self) -> bool:
        return self.rcon is not None

    def run_command(self, cmd: str) -> str:
        if self.rcon is None:
            return super().run_command(cmd)
        return self.rcon.command(cmd)

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass
        if self.rcon is not None:
            self.rcon.close()