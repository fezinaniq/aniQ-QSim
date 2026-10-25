"""Workbench geometry and block palette. Everything here is configurable.

Geometry (matches the plan, viewed from above):
    x axis = time (step 0 on the left), z axis = qubit wires (row 0 = q0).
    One fixed y layer ("the layer") holds the circuit; the compiler reads only it.
The layer sits one block above the ground, so wires and gates stand on the floor
and rows without a wire are simply empty air.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .blocks import LEGACY

Pos = tuple[int, int, int]

# token -> block name
DEFAULT_TOKENS: dict[str, str] = {
    "wire": "light_blue_stained_glass",
    "h": "gold_block",
    "x": "iron_block",
    "y": "red_sandstone",
    "z": "emerald_block",
    "s": "lapis_block",
    "t": "purpur_block",
    "control": "redstone_block",
    "target": "coal_block",
    "swap": "quartz_block",
    "measure": "observer",
}
SINGLE_QUBIT_TOKENS = ("h", "x", "y", "z", "s", "t")


@dataclass(frozen=True)
class Palette:
    tokens: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_TOKENS))

    def __post_init__(self) -> None:
        missing = set(DEFAULT_TOKENS) - set(self.tokens)
        if missing:
            raise ValueError(f"palette is missing tokens: {sorted(missing)}")
        blocks = list(self.tokens.values())
        if len(set(blocks)) != len(blocks):
            raise ValueError("palette blocks must all be different (the world is read by id)")
        for block in blocks:
            if block not in LEGACY or block.endswith("_concrete") or block == "air":
                raise ValueError(f"'{block}' cannot be used as a palette block")

    def block(self, token: str) -> str:
        return self.tokens[token]

    def token(self, block: str) -> str | None:
        """Reverse lookup: which token does this block mean? None if it isn't ours."""
        for token, name in self.tokens.items():
            if name == block:
                return token
        return None


DEFAULT_PALETTE = Palette()


@dataclass(frozen=True)
class WorkbenchConfig:
    origin: Pos = (0, 0, 0)  # block of step 0, qubit 0 (on the circuit layer)
    max_steps: int = 12
    max_qubits: int = 5
    bar_height: int = 10
    palette: Palette = DEFAULT_PALETTE

    def __post_init__(self) -> None:
        if self.max_steps < 1 or not 1 <= self.max_qubits <= 5:
            raise ValueError("need max_steps >= 1 and 1 <= max_qubits <= 5")

    # ---- workbench ---------------------------------------------------------

    def cell(self, step: int, qubit: int) -> Pos:
        x, y, z = self.origin
        return (x + step, y, z + qubit)

    @property
    def grid_min(self) -> Pos:
        return self.origin

    @property
    def grid_max(self) -> Pos:
        x, y, z = self.origin
        return (x + self.max_steps - 1, y, z + self.max_qubits - 1)

    @property
    def lever_pos(self) -> Pos:
        x, y, z = self.origin
        return (x - 2, y, z + self.max_qubits // 2)

    # ---- display (bars sit beyond the +z edge of the workbench) ------------

    @property
    def lamp_z(self) -> int:
        return self.origin[2] + self.max_qubits + 2

    @property
    def bar_z(self) -> int:
        return self.origin[2] + self.max_qubits + 5

    def bar_spacing(self, n_qubits: int) -> int:
        return 2 if 2**n_qubits <= 16 else 1

    def bar_x(self, index: int, n_qubits: int) -> int:
        return self.origin[0] + index * self.bar_spacing(n_qubits)

    def lamp_x(self, qubit: int) -> int:
        return self.origin[0] + qubit * 2
