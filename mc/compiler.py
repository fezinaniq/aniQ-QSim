"""Block grid -> QuantumCircuit, with strict validation.

Rules (reported all at once, never silently guessed):
  * wire / air cells are identity; any other block must be in the palette
  * every qubit row from 0 up to the highest used row must contain something
  * per column: control and target come as exactly one pair (CNOT); swap markers as
    exactly two; at most one gate per qubit per column (automatic, one block per cell)
  * a measurement block ends that qubit's wire: no gate may follow it, and the engine
    has no mid-circuit measurement yet, so the readout happens at the end of the run
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from qengine import QuantumCircuit

from .bridge import WorldBridge
from .config import DEFAULT_PALETTE, SINGLE_QUBIT_TOKENS, Palette, WorkbenchConfig


@dataclass(frozen=True)
class Diagnostic:
    message: str
    step: int | None = None
    qubit: int | None = None

    def __str__(self) -> str:
        where = []
        if self.step is not None:
            where.append(f"step {self.step}")
        if self.qubit is not None:
            where.append(f"qubit {self.qubit}")
        return f"{', '.join(where)}: {self.message}" if where else self.message


class CompileError(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        super().__init__("; ".join(str(d) for d in diagnostics))


@dataclass(frozen=True)
class CompiledCircuit:
    circuit: QuantumCircuit
    measured: tuple[int, ...]  # qubits with a measurement block, ascending
    steps: int


def compile_grid(
    grid: Sequence[Sequence[str]], palette: Palette = DEFAULT_PALETTE
) -> CompiledCircuit:
    """grid[step][qubit] -> circuit. Raises CompileError listing every problem found."""
    wire = palette.block("wire")
    empty = {"air", wire}
    n_rows = len(grid[0]) if grid else 0
    diags: list[Diagnostic] = []

    used_rows = [q for q in range(n_rows) if any(col[q] != "air" for col in grid)]
    if not used_rows:
        raise CompileError([Diagnostic("the workbench is empty (no wires or gates found)")])
    n_qubits = max(used_rows) + 1
    for q in range(n_qubits):
        if q not in used_rows:
            diags.append(Diagnostic("this row has no wire, but a higher qubit row is in use", qubit=q))

    instructions: list[tuple[str, tuple[int, ...]]] = []
    measured_at: dict[int, int] = {}
    last_step = -1
    for step, column in enumerate(grid):
        controls: list[int] = []
        targets: list[int] = []
        swaps: list[int] = []
        singles: list[tuple[int, str]] = []
        for q in range(n_qubits):
            block = column[q]
            if block in empty:
                continue
            token = palette.token(block)
            if token is None:
                diags.append(Diagnostic(f"unknown block '{block}'", step, q))
                continue
            last_step = step
            if token == "measure":
                if q in measured_at:
                    diags.append(Diagnostic("second measurement on the same qubit", step, q))
                else:
                    measured_at[q] = step
                continue
            if q in measured_at:
                diags.append(
                    Diagnostic(
                        f"gate '{token}' after the measurement at step {measured_at[q]} "
                        "(a measured qubit ends its wire)",
                        step,
                        q,
                    )
                )
                continue
            if token == "control":
                controls.append(q)
            elif token == "target":
                targets.append(q)
            elif token == "swap":
                swaps.append(q)
            elif token in SINGLE_QUBIT_TOKENS:
                singles.append((q, token))

        if len(controls) > 1:
            diags.append(Diagnostic("more than one CNOT control (Toffoli is not supported)", step))
        if len(targets) > 1:
            diags.append(Diagnostic("more than one CNOT target in one column", step))
        if len(controls) == 1 and not targets:
            diags.append(Diagnostic("CNOT control has no target in its column", step, controls[0]))
        if len(targets) == 1 and not controls:
            diags.append(Diagnostic("CNOT target has no control in its column", step, targets[0]))
        if len(swaps) not in (0, 2):
            diags.append(Diagnostic(f"SWAP needs exactly 2 markers in a column, found {len(swaps)}", step))

        for q, token in singles:
            instructions.append((token, (q,)))
        if len(controls) == 1 and len(targets) == 1:
            instructions.append(("cnot", (controls[0], targets[0])))
        if len(swaps) == 2:
            instructions.append(("swap", (swaps[0], swaps[1])))

    if diags:
        raise CompileError(diags)

    circuit = QuantumCircuit(n_qubits)
    for name, qubits in instructions:
        circuit.add(name, *qubits)
    return CompiledCircuit(circuit, tuple(sorted(measured_at)), last_step + 1)


def read_grid(bridge: WorldBridge, cfg: WorkbenchConfig) -> list[list[str]]:
    """Read the workbench layer from the world into grid[step][qubit]."""
    region = bridge.get_region(cfg.grid_min, cfg.grid_max)
    return [
        [region[cfg.cell(step, q)] for q in range(cfg.max_qubits)]
        for step in range(cfg.max_steps)
    ]


def compile_world(bridge: WorldBridge, cfg: WorkbenchConfig) -> CompiledCircuit:
    return compile_grid(read_grid(bridge, cfg), cfg.palette)
