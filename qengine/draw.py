"""Terminal visuals: ASCII circuit diagrams, state tables, and histograms.

Pass ascii_only=True for plain ASCII (for terminals/log files that mangle Unicode).
Qubit 0 is drawn on the top row, matching the Minecraft workbench (row 0 = q0).
"""

from __future__ import annotations

from .circuit import QuantumCircuit
from .measure import bitstring
from .state import QuantumState

CELL = 5  # characters per circuit column


def _glyphs(ascii_only: bool) -> dict[str, str]:
    if ascii_only:
        return {"wire": "-", "bar": "#", "vline": "|", "cross": "|", "control": "*",
                "target": "(+)", "swap": "x", "ket_r": ">"}
    return {"wire": "\u2500", "bar": "\u2588", "vline": "\u2502", "cross": "\u253c",
            "control": "\u25cf", "target": "\u2295", "swap": "\u2715", "ket_r": "\u27e9"}


def _cell(symbol: str, wire: str) -> str:
    """Center `symbol` in a CELL-wide slot padded with wire characters."""
    left = (CELL - len(symbol)) // 2
    return wire * left + symbol + wire * (CELL - len(symbol) - left)


def draw_circuit(circuit: QuantumCircuit, ascii_only: bool = False) -> str:
    """Draw the circuit as text, one wire per qubit, gates packed into time columns."""
    g = _glyphs(ascii_only)
    n = circuit.n_qubits
    free = [0] * n  # first free column for each qubit
    columns: list[dict[int, str]] = []
    connectors: list[set[int]] = []  # per column: gaps i (between q_i and q_i+1) to draw

    def ensure(col: int) -> None:
        while len(columns) <= col:
            columns.append({})
            connectors.append(set())

    for inst in circuit.instructions:
        lo, hi = min(inst.targets), max(inst.targets)
        col = max(free[q] for q in range(lo, hi + 1))
        ensure(col)
        if inst.name == "cnot":
            columns[col][inst.targets[0]] = g["control"]
            columns[col][inst.targets[1]] = g["target"]
        elif inst.name == "swap":
            for q in inst.targets:
                columns[col][q] = g["swap"]
        else:
            columns[col][inst.targets[0]] = f"[{inst.name.upper()}]"
        for gap in range(lo, hi):
            connectors[col].add(gap)
        for q in range(lo, hi + 1):
            free[q] = col + 1
            if q not in columns[col] and lo < q < hi:
                columns[col][q] = g["cross"]

    label_w = len(f"q{n - 1}")
    lines: list[str] = []
    for q in range(n):
        row = f"{('q' + str(q)).ljust(label_w)}: "
        for col in columns:
            row += _cell(col.get(q, ""), g["wire"])
        row += g["wire"] * 2
        lines.append(row)
        if q < n - 1:
            spacer = " " * (label_w + 2)
            for col, gaps in zip(columns, connectors, strict=True):
                spacer += _cell(g["vline"], " ") if q in gaps else " " * CELL
            lines.append(spacer.rstrip())
    return "\n".join(lines)


def _fmt_amp(a: complex, tol: float = 1e-9) -> str:
    if abs(a.imag) < tol:
        return f"{a.real:+.4f}"
    if abs(a.real) < tol:
        return f"{a.imag:+.4f}i"
    return f"{a.real:+.3f}{a.imag:+.3f}i"


def format_state(
    state: QuantumState,
    show_zero: bool = False,
    width: int = 30,
    ascii_only: bool = False,
    max_rows: int = 16,
    tol: float = 1e-9,
) -> str:
    """Table of basis states with amplitude, probability and a bar.

    Zero-probability rows are hidden unless show_zero. If more than max_rows rows
    qualify, the max_rows most probable are shown and the rest summarised.
    """
    g = _glyphs(ascii_only)
    rows = []
    for i, a in enumerate(state.amps):
        p = abs(a) ** 2
        if p < tol and not show_zero:
            continue
        rows.append((i, a, p))
    hidden = 0
    if len(rows) > max_rows:
        rows = sorted(rows, key=lambda r: (-r[2], r[0]))[:max_rows]
        rows.sort(key=lambda r: r[0])
        hidden = sum(1 for a in state.amps if abs(a) ** 2 >= tol or show_zero) - len(rows)
    lines = []
    for i, a, p in rows:
        label = f"|{bitstring(i, state.n_qubits)}{g['ket_r']}"
        bar = g["bar"] * round(width * p)
        lines.append(f"{label}  amp {_fmt_amp(a):>16}  P {p:6.3f}  {bar}".rstrip())
    if hidden:
        lines.append(f"... and {hidden} more basis states")
    return "\n".join(lines)


def format_histogram(
    counts: dict[str, int], width: int = 30, ascii_only: bool = False
) -> str:
    """Horizontal histogram of measurement counts; the largest bar fills `width`."""
    g = _glyphs(ascii_only)
    total = sum(counts.values())
    top = max(counts.values())
    lines = []
    for key, c in counts.items():
        bar = g["bar"] * max(1, round(width * c / top))
        lines.append(f"|{key}{g['ket_r']}  {c:>6}  {100 * c / total:5.1f}%  {bar}")
    return "\n".join(lines)
