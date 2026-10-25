"""Build the physical workbench in the world, and place circuits onto it as blocks."""

from __future__ import annotations

from collections.abc import Iterable

from qengine import QuantumCircuit

from .bridge import WorldBridge
from .config import WorkbenchConfig
from .layout import circuit_to_grid
from .style import Stylist, dress_workbench


def clear_workbench(bridge: WorldBridge, cfg: WorkbenchConfig) -> None:
    """Empty the circuit layer (all steps, all qubit rows) but leave the frame alone."""
    bridge.fill(cfg.grid_min, cfg.grid_max, "air")


def build_workbench(bridge: WorldBridge, cfg: WorkbenchConfig, qubits: int = 3) -> None:
    """Frame, wire rows for `qubits` qubits, and the RUN lever.

    Idempotent: running it again resets the board to bare wires.
    """
    if not 1 <= qubits <= cfg.max_qubits:
        raise ValueError(f"qubits must be between 1 and {cfg.max_qubits}")
    (x1, y, z1), (x2, _, _) = cfg.grid_min, cfg.grid_max
    wire = cfg.palette.block("wire")

    clear_workbench(bridge, cfg)
    dress_workbench(bridge, cfg, qubits)  # floor, frame, light posts, console
    bridge.fill((x1, y, z1), (x2, y, z1 + qubits - 1), wire)
    bridge.set_lever(cfg.lever_pos, False)
    stylist = Stylist(bridge, cfg)
    stylist.clear()  # old labels from any earlier build
    stylist.board(qubits)


def place_circuit(
    bridge: WorldBridge,
    cfg: WorkbenchConfig,
    circuit: QuantumCircuit,
    measure: Iterable[int] = (),
) -> int:
    """Lay `circuit` out as blocks on a fresh workbench. Returns the number of columns used."""
    if circuit.n_qubits > cfg.max_qubits:
        raise ValueError(f"circuit has {circuit.n_qubits} qubits, workbench holds {cfg.max_qubits}")
    grid = circuit_to_grid(circuit, cfg.palette, measure)
    if len(grid) > cfg.max_steps:
        raise ValueError(f"circuit needs {len(grid)} columns, workbench holds {cfg.max_steps}")
    build_workbench(bridge, cfg, qubits=circuit.n_qubits)
    for step, column in enumerate(grid):
        for q, block in enumerate(column):
            if block != cfg.palette.block("wire"):
                bridge.set_block(cfg.cell(step, q), block)
    Stylist(bridge, cfg).gates(grid)
    return len(grid)

