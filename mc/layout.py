"""Circuit -> block grid: the inverse of the compiler.

A grid is a list of columns (time steps); each column is a list with one block name
per qubit row. Packing rule (same as the ASCII drawing): an instruction goes in the
first column where every qubit row it spans is free, so a CNOT's connecting line never
shares a column with another gate. On top of that, a column holds at most one CNOT and
one SWAP, because the compiler pairs control/target blocks per column.
"""

from __future__ import annotations

from collections.abc import Iterable

from qengine import QuantumCircuit

from .config import DEFAULT_PALETTE, Palette


def schedule(circuit: QuantumCircuit) -> list[list]:
    """Instructions grouped into time columns, in left-to-right order."""
    free = [0] * circuit.n_qubits
    columns: list[list] = []
    kinds: list[set[str]] = []
    for inst in circuit.instructions:
        lo, hi = min(inst.targets), max(inst.targets)
        col = max(free[q] for q in range(lo, hi + 1))
        if inst.name in ("cnot", "swap"):
            while col < len(kinds) and inst.name in kinds[col]:
                col += 1
        while len(columns) <= col:
            columns.append([])
            kinds.append(set())
        columns[col].append(inst)
        kinds[col].add(inst.name)
        for q in range(lo, hi + 1):
            free[q] = col + 1
    return columns


def circuit_to_grid(
    circuit: QuantumCircuit,
    palette: Palette = DEFAULT_PALETTE,
    measure: Iterable[int] = (),
) -> list[list[str]]:
    """Block names for every cell, grid[step][qubit]. Empty cells are the wire block.

    Each qubit in `measure` gets a measurement block one column after its last gate
    (the compiler forbids gates after a measurement).
    """
    n = circuit.n_qubits
    columns = schedule(circuit)
    grid = [[palette.block("wire")] * n for _ in columns]
    last_used = [-1] * n
    for step, insts in enumerate(columns):
        for inst in insts:
            if inst.name == "cnot":
                control, target = inst.targets
                grid[step][control] = palette.block("control")
                grid[step][target] = palette.block("target")
            elif inst.name == "swap":
                for q in inst.targets:
                    grid[step][q] = palette.block("swap")
            else:
                grid[step][inst.targets[0]] = palette.block(inst.name)
            for q in inst.targets:
                last_used[q] = step
    for q in sorted(set(measure)):
        if not 0 <= q < n:
            raise ValueError(f"cannot measure qubit {q}: circuit has {n} qubits")
        step = last_used[q] + 1
        while len(grid) <= step:
            grid.append([palette.block("wire")] * n)
        grid[step][q] = palette.block("measure")
    return grid
