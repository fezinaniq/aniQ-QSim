"""WorldBridge: the only thing the rest of mc/ knows about Minecraft.

Compiler, renderer and controller talk to this interface. Two implementations:
    FakeBridge   (here)              in-memory world, for tests and offline demos
    SocketBridge (mc/socket_bridge)  real server: RaspberryJuice socket + optional RCON
Blocks are always names like "gold_block"; positions are absolute (x, y, z).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Self

from .blocks import glyph
from .config import Pos


class BridgeError(RuntimeError):
    """Anything that goes wrong talking to the world."""


def ascii_safe(msg: str) -> str:
    """Chat-safe text: ASCII only, one line, no characters the protocol treats specially."""
    msg = msg.replace("\u27e9", ">").replace("\u221a", "sqrt").replace("\u2013", "-")
    msg = msg.replace(",", ";").replace("(", "[").replace(")", "]")
    return " ".join(msg.encode("ascii", "replace").decode("ascii").split())


class WorldBridge(ABC):
    @abstractmethod
    def get_block(self, pos: Pos) -> str: ...

    @abstractmethod
    def get_region(self, a: Pos, b: Pos) -> dict[Pos, str]:
        """Every block in the cuboid spanned by corners a and b, as {pos: name}."""

    @abstractmethod
    def set_block(self, pos: Pos, block: str) -> None: ...

    @abstractmethod
    def fill(self, a: Pos, b: Pos, block: str) -> None: ...

    @abstractmethod
    def lever_powered(self, pos: Pos) -> bool: ...

    @abstractmethod
    def set_lever(self, pos: Pos, powered: bool) -> None: ...

    @abstractmethod
    def poll_hits(self) -> list[Pos]:
        """Blocks a player has hit (sword right-click) since the last poll."""

    @abstractmethod
    def say(self, msg: str) -> None: ...

    @abstractmethod
    def get_player_tile(self) -> Pos: ...

    @property
    def has_commands(self) -> bool:
        """True if run_command works (RCON connected)."""
        return False

    def run_command(self, cmd: str) -> str:
        raise BridgeError("no command channel (RCON) is configured")

    def close(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def cuboid(a: Pos, b: Pos):
    """Yield every position in the cuboid between corners a and b (inclusive)."""
    for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
        for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                yield (x, y, z)


class FakeBridge(WorldBridge):
    """A dictionary world. Counts operations so tests can check batching and diffing."""

    def __init__(self, player: Pos = (0, 0, 0)) -> None:
        self.blocks: dict[Pos, str] = {}
        self.powered: set[Pos] = set()
        self.hits: deque[Pos] = deque()
        self.chat: list[str] = []
        self.commands: list[str] = []
        self.player = player
        self.set_calls = 0
        self.fill_calls = 0
        self.get_calls = 0

    # ---- WorldBridge -------------------------------------------------------

    def get_block(self, pos: Pos) -> str:
        self.get_calls += 1
        return self.blocks.get(pos, "air")

    def get_region(self, a: Pos, b: Pos) -> dict[Pos, str]:
        self.get_calls += 1
        return {p: self.blocks.get(p, "air") for p in cuboid(a, b)}

    def set_block(self, pos: Pos, block: str) -> None:
        self.set_calls += 1
        self._put(pos, block)

    def fill(self, a: Pos, b: Pos, block: str) -> None:
        self.fill_calls += 1
        for p in cuboid(a, b):
            self._put(p, block)

    def _put(self, pos: Pos, block: str) -> None:
        if block == "air":
            self.blocks.pop(pos, None)
        else:
            self.blocks[pos] = block
        if block != "lever":
            self.powered.discard(pos)

    def lever_powered(self, pos: Pos) -> bool:
        return self.blocks.get(pos) == "lever" and pos in self.powered

    def set_lever(self, pos: Pos, powered: bool) -> None:
        self.set_calls += 1
        self.blocks[pos] = "lever"
        (self.powered.add if powered else self.powered.discard)(pos)

    def poll_hits(self) -> list[Pos]:
        out = list(self.hits)
        self.hits.clear()
        return out

    def say(self, msg: str) -> None:
        self.chat.append(ascii_safe(msg))

    def get_player_tile(self) -> Pos:
        return self.player

    @property
    def has_commands(self) -> bool:
        return True

    def run_command(self, cmd: str) -> str:
        self.commands.append(cmd)
        return ""

    # ---- test / demo helpers ----------------------------------------------

    def flip_lever(self, pos: Pos) -> None:
        """What a player does: toggle the lever."""
        if pos in self.powered:
            self.powered.discard(pos)
        else:
            self.powered.add(pos)

    def top_view(self, x1: int, x2: int, z1: int, z2: int, y: int) -> str:
        """ASCII picture of one layer seen from above (z down the page, x across)."""
        return "\n".join(
            "".join(glyph(self.blocks.get((x, y, z), "air")) for x in range(x1, x2 + 1)).rstrip()
            for z in range(z1, z2 + 1)
        )

    def front_view(self, x1: int, x2: int, y1: int, y2: int, z: int) -> str:
        """ASCII picture of one z slice seen from the front (highest y on top)."""
        return "\n".join(
            "".join(glyph(self.blocks.get((x, y, z), "air")) for x in range(x1, x2 + 1)).rstrip()
            for y in range(y2, y1 - 1, -1)
        )
