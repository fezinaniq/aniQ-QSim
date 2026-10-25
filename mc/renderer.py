"""State vector -> blocks. Probability bars, phase colours, bit read-out, measurement lamps.

Layout (see WorkbenchConfig): one bar per basis state along x, beyond the +z edge of the
workbench. Bar height = probability * bar_height, colour = phase. Under each bar a small
grid shows its bitstring (white = 1, black = 0) with qubit 0 nearest the bar.

Performance: the renderer remembers what it drew and only writes what changed; each
changed bar costs at most two fill calls. Drawing the same state twice writes nothing.
"""

from __future__ import annotations

from qengine import QuantumState

from .bridge import WorldBridge
from .colors import phase_block, reference_amplitude
from .config import WorkbenchConfig
from .style import PEDESTAL, Stylist

MIN_VISIBLE = 0.005  # below this a bar is not drawn at all
LAMP_ON, LAMP_OFF = "glowstone", "gray_concrete"
BASE = PEDESTAL  # glowing pad under every bar slot


def bar_height(p: float, max_height: int) -> int:
    """Blocks for probability p: 0 if negligible, else at least 1, at most max_height."""
    if p < MIN_VISIBLE:
        return 0
    return min(max_height, max(1, int(p * max_height + 0.5 + 1e-9)))  # round half up; epsilon absorbs float error


class BarRenderer:
    def __init__(self, bridge: WorldBridge, cfg: WorkbenchConfig) -> None:
        self.bridge = bridge
        self.cfg = cfg
        self._n: int | None = None
        self._bars: dict[int, tuple[int, str | None]] = {}
        self._lamps: dict[int, bool] = {}
        self.stylist = Stylist(bridge, cfg)

    # ---- helpers -----------------------------------------------------------

    def _bar_cell(self, index: int, n: int, level: int) -> tuple[int, int, int]:
        """Block `level` blocks above the layer floor, level 0 = the layer itself."""
        return (self.cfg.bar_x(index, n), self.cfg.origin[1] + level, self.cfg.bar_z)

    def _fill_bar(self, index: int, n: int, lo: int, hi: int, block: str) -> None:
        if hi >= lo:
            self.bridge.fill(self._bar_cell(index, n, lo), self._bar_cell(index, n, hi), block)

    def clear(self) -> None:
        """Remove every bar, read-out block and lamp, and forget the cache."""
        cfg = self.cfg
        y = cfg.origin[1]
        width = 2**cfg.max_qubits * cfg.bar_spacing(cfg.max_qubits)
        x1 = cfg.origin[0]
        self.bridge.fill((x1, y, cfg.bar_z), (x1 + width, y + cfg.bar_height, cfg.bar_z), "air")
        self.bridge.fill(
            (x1, y - 1, cfg.bar_z), (x1 + width, y - 1, cfg.bar_z + cfg.max_qubits + 1), "air"
        )
        self.bridge.fill(
            (x1, y - 1, cfg.lamp_z), (x1 + 2 * cfg.max_qubits, y - 1, cfg.lamp_z), "air"
        )
        self._n, self._bars, self._lamps = None, {}, {}
        self.stylist.clear("qmc_bar")

    # ---- drawing -----------------------------------------------------------

    def draw_state(self, state: QuantumState) -> None:
        cfg, n = self.cfg, state.n_qubits
        if n > cfg.max_qubits:
            raise ValueError(f"state has {n} qubits, display holds {cfg.max_qubits}")
        if self._n != n:
            self.clear()
            self._n = n
            self._draw_readout(n)
        ref = reference_amplitude(state.amps)
        for i, amp in enumerate(state.amps):
            h = bar_height(abs(amp) ** 2, cfg.bar_height)
            color = phase_block(amp, ref) if h else None
            old_h, old_c = self._bars.get(i, (0, None))
            if (h, color) == (old_h, old_c):
                continue
            if h == 0:
                self._fill_bar(i, n, 0, old_h - 1, "air")
            elif color != old_c:
                self._fill_bar(i, n, 0, h - 1, color)  # type: ignore[arg-type]
                self._fill_bar(i, n, h, old_h - 1, "air")
            elif h > old_h:
                self._fill_bar(i, n, old_h, h - 1, color)  # type: ignore[arg-type]
            else:
                self._fill_bar(i, n, h, old_h - 1, "air")
            self._bars[i] = (h, color)
        # labels and sparkles follow the state on every run, even an unchanged one
        heights = {i: h for i, (h, _) in self._bars.items()}
        self.stylist.bars(state, heights)
        self.stylist.effects(state, heights)

    def _draw_readout(self, n: int) -> None:
        """Base line under the bars and one white/black cell per qubit per basis state."""
        cfg = self.cfg
        y = cfg.origin[1] - 1
        for i in range(2**n):
            x = cfg.bar_x(i, n)
            self.bridge.set_block((x, y, cfg.bar_z), BASE)
            for q in range(n):
                bit = (i >> q) & 1
                block = "white_concrete" if bit else "black_concrete"
                self.bridge.set_block((x, y, cfg.bar_z + 1 + q), block)

    def draw_measurement(self, bits: dict[int, int] | None, n_qubits: int) -> None:
        """Lamp row: glowstone = measured 1, grey = measured 0, empty = not measured."""
        cfg = self.cfg
        y = cfg.origin[1] - 1
        bits = bits or {}
        for q in range(n_qubits):
            lit = bool(bits[q]) if q in bits else None
            if lit is None:
                if q in self._lamps:
                    self.bridge.set_block((cfg.lamp_x(q), y, cfg.lamp_z), "air")
                    del self._lamps[q]
                continue
            if self._lamps.get(q) != lit:
                self.bridge.set_block((cfg.lamp_x(q), y, cfg.lamp_z), LAMP_ON if lit else LAMP_OFF)
                self._lamps[q] = lit
