"""Looks: floating labels, board dressing and run effects.

Everything here is decoration. The compiler never reads any of it, and it all degrades
quietly: labels and effects need a command channel (RCON), so without one they are skipped.

Labels are `text_display` entities. Every one carries a tag, so a redraw first kills the
old ones with a single command and then spawns the new ones. That is what keeps the world
clean: rebuilding or re-running never stacks duplicates.

    qmc_board   title, qubit names, RUN        (drawn when the workbench is built)
    qmc_gate    one per gate block             (follows the blocks actually on the board)
    qmc_bar     one per visible bar            (|01> 50%)

Text format: Minecraft changed how entity text is written in commands around 1.21.5.
The default ("json") is a JSON string, which is what 1.21.4 and older expect. If your labels
show raw braces, set MC_TEXT_FORMAT=snbt (1.21.5 and newer).
"""

from __future__ import annotations

import json
import os

from qengine import QuantumState

from .bridge import BridgeError, WorldBridge
from .config import Pos, WorkbenchConfig

TAG_BOARD, TAG_GATE, TAG_BAR = "qmc_board", "qmc_gate", "qmc_bar"
ALL_TAGS = (TAG_BOARD, TAG_GATE, TAG_BAR)

# palette token -> (text, colour)
GATE_LABELS: dict[str, tuple[str, str]] = {
    "h": ("H", "gold"),
    "x": ("X", "aqua"),
    "y": ("Y", "yellow"),
    "z": ("Z", "green"),
    "s": ("S", "blue"),
    "t": ("T", "light_purple"),
    "control": ("CTRL", "red"),
    "target": ("NOT", "gray"),
    "swap": ("SWAP", "white"),
    "measure": ("M", "white"),
}

# Decoration blocks
FLOOR = "polished_blackstone"
FRAME = "polished_blackstone_bricks"
POST = "sea_lantern"
GLOW = "sea_lantern"
CONSOLE = "chiseled_polished_blackstone"
PEDESTAL = "sea_lantern"


def text_format() -> str:
    fmt = os.environ.get("MC_TEXT_FORMAT", "json").lower()
    return fmt if fmt in ("json", "snbt") else "json"


def summon_label(
    pos: tuple[float, float, float],
    text: str,
    color: str,
    tag: str,
    scale: float = 1.0,
    bold: bool = True,
    billboard: str = "center",
) -> str:
    """The /summon command for one floating label."""
    if not text.isascii() or any(c in text for c in "'\"\\{}"):
        raise ValueError(f"label text must be plain ASCII without quotes or braces: {text!r}")
    if text_format() == "snbt":
        value = f'{{text:"{text}",color:"{color}",bold:{1 if bold else 0}b}}'
    else:
        comp = json.dumps({"text": text, "color": color, "bold": bold}, separators=(",", ":"))
        value = f"'{comp}'"
    s = f"{scale:.2f}f"
    x, y, z = pos
    return (
        f"summon text_display {x:.2f} {y:.2f} {z:.2f} "
        f'{{text:{value},billboard:"{billboard}",background:0,shadow:1b,line_width:300,'
        f'Tags:["{tag}"],'
        f"transformation:{{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],"
        f"translation:[0f,0f,0f],scale:[{s},{s},{s}]}}}}"
    )


def kill_tag(tag: str) -> str:
    return f"kill @e[type=text_display,tag={tag}]"


def ket_label(index: int, n_qubits: int) -> str:
    """|q(n-1)...q0> for a basis index (little-endian, same as the engine)."""
    return "|" + format(index, f"0{n_qubits}b") + ">"


class Stylist:
    """Draws labels and effects around the workbench and display wall."""

    def __init__(self, bridge: WorldBridge, cfg: WorkbenchConfig) -> None:
        self.bridge = bridge
        self.cfg = cfg

    # ---- plumbing ----------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self.bridge.has_commands

    def _run(self, *commands: str) -> None:
        if not self.enabled:
            return
        for cmd in commands:
            try:
                self.bridge.run_command(cmd)
            except BridgeError:
                return  # decoration must never break a run

    def clear(self, *tags: str) -> None:
        self._run(*(kill_tag(t) for t in (tags or ALL_TAGS)))

    # ---- board -------------------------------------------------------------

    def board(self, qubits: int) -> None:
        """Title, one name per qubit row, and a RUN tag over the lever."""
        if not self.enabled:
            return
        cfg = self.cfg
        x0, y, z0 = cfg.origin
        mid_x = x0 + cfg.max_steps / 2
        cmds = [kill_tag(TAG_BOARD)]
        cmds.append(
            summon_label((mid_x, y + 2.4, z0 - 1.5), "QUANTUM WORKBENCH", "aqua", TAG_BOARD, 2.2)
        )
        for q in range(qubits):
            cmds.append(
                summon_label((x0 - 0.5, y + 1.1, z0 + q + 0.5), f"q{q}", "white", TAG_BOARD, 1.3)
            )
        lx, ly, lz = cfg.lever_pos
        cmds.append(summon_label((lx + 0.5, ly + 1.5, lz + 0.5), "RUN", "green", TAG_BOARD, 1.6))
        self._run(*cmds)

    # ---- gates -------------------------------------------------------------

    def gates(self, grid: list[list[str]]) -> None:
        """One label per gate block in grid[step][qubit]. Wires and unknown blocks get none."""
        if not self.enabled:
            return
        palette = self.cfg.palette
        cmds = [kill_tag(TAG_GATE)]
        for step, column in enumerate(grid):
            for q, block in enumerate(column):
                token = palette.token(block)
                if token is None or token == "wire":
                    continue
                text, color = GATE_LABELS[token]
                x, y, z = self.cfg.cell(step, q)
                cmds.append(summon_label((x + 0.5, y + 1.25, z + 0.5), text, color, TAG_GATE, 1.2))
        self._run(*cmds)

    # ---- bars --------------------------------------------------------------

    def bars(self, state: QuantumState, heights: dict[int, int]) -> None:
        """A `|01> 50%` label over every visible bar. `heights` is {basis index: bar height}."""
        if not self.enabled:
            return
        cfg, n = self.cfg, state.n_qubits
        cmds = [kill_tag(TAG_BAR)]
        for i, h in sorted(heights.items()):
            if h <= 0:
                continue
            p = abs(state.amps[i]) ** 2
            x = cfg.bar_x(i, n) + 0.5
            y = cfg.origin[1] + h + 0.9
            text = f"{ket_label(i, n)} {p * 100:.0f}%"
            cmds.append(summon_label((x, y, cfg.bar_z + 0.5), text, "white", TAG_BAR, 1.0))
        self._run(*cmds)

    # ---- effects -----------------------------------------------------------

    def effects(self, state: QuantumState, heights: dict[int, int]) -> None:
        """Sparkles above every visible bar (count grows with probability) and a chime."""
        if not self.enabled:
            return
        cfg, n = self.cfg, state.n_qubits
        cmds = []
        for i, h in sorted(heights.items()):
            if h <= 0:
                continue
            p = abs(state.amps[i]) ** 2
            x = cfg.bar_x(i, n) + 0.5
            y = cfg.origin[1] + h + 0.3
            count = max(4, int(8 + 70 * p))
            cmds.append(
                f"particle end_rod {x:.2f} {y:.2f} {cfg.bar_z + 0.5:.2f} 0.25 0.5 0.25 0.03 {count} force"
            )
        lx, ly, lz = cfg.lever_pos
        cmds.append(f"playsound minecraft:block.beacon.activate block @a {lx} {ly} {lz} 0.8 1.4")
        self._run(*cmds)


def dress_workbench(bridge: WorldBridge, cfg: WorkbenchConfig, qubits: int) -> None:
    """Floor plate, glowing wire bed, frame with light posts, and a lever console.

    Pure blocks, so it works with or without RCON. Only touches cells outside the
    compiler's scan region, plus the floor one block below the circuit layer.
    """
    (x1, y, z1), (x2, _, z2) = cfg.grid_min, cfg.grid_max
    # dark floor under the board and its frame
    bridge.fill((x1 - 1, y - 1, z1 - 1), (x2 + 1, y - 1, z2 + 1), FLOOR)
    # lit bed under the wires that are in use: the glass wire glows from below
    bridge.fill((x1, y - 1, z1), (x2, y - 1, z1 + qubits - 1), GLOW)
    # frame ring on the circuit layer
    bridge.fill((x1 - 1, y, z1 - 1), (x2 + 1, y, z1 - 1), FRAME)
    bridge.fill((x1 - 1, y, z2 + 1), (x2 + 1, y, z2 + 1), FRAME)
    bridge.fill((x1 - 1, y, z1), (x1 - 1, y, z2), FRAME)
    bridge.fill((x2 + 1, y, z1), (x2 + 1, y, z2), FRAME)
    # light posts, two high, on the four corners
    for cx in (x1 - 1, x2 + 1):
        for cz in (z1 - 1, z2 + 1):
            bridge.fill((cx, y, cz), (cx, y + 1, cz), POST)
    # console under the lever
    lx, ly, lz = cfg.lever_pos
    bridge.set_block((lx, ly - 1, lz), CONSOLE)


def where(cfg: WorkbenchConfig) -> Pos:
    """Centre of the workbench (used to scope clean-up commands)."""
    x, y, z = cfg.origin
    return (x + cfg.max_steps // 2, y, z + cfg.max_qubits // 2)
