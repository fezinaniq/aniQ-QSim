"""Fast path: apply gates directly to the amplitude list, in place.

No 2^N x 2^N matrix is ever built. Each gate touches the amplitudes in pairs whose
indices differ in exactly one bit, so a gate costs O(2^N) instead of O(4^N).
"""

from __future__ import annotations

from .linalg import Matrix, Vector


def apply_single_qubit(amps: Vector, gate: Matrix, target: int) -> None:
    """Apply a 2x2 gate to qubit `target`.

    Indices i and j = i | (1 << target) differ only in the target bit. Their
    amplitudes (x, y) are mixed by the gate's 2x2 matrix.
    """
    bit = 1 << target
    a, b = gate[0]
    c, d = gate[1]
    for i in range(len(amps)):
        if i & bit:
            continue
        j = i | bit
        x, y = amps[i], amps[j]
        amps[i] = a * x + b * y
        amps[j] = c * x + d * y


def apply_controlled(amps: Vector, gate: Matrix, control: int, target: int) -> None:
    """Apply a 2x2 gate to `target` only on basis states where `control` bit is 1."""
    cbit = 1 << control
    tbit = 1 << target
    a, b = gate[0]
    c, d = gate[1]
    for i in range(len(amps)):
        if not (i & cbit) or (i & tbit):
            continue
        j = i | tbit
        x, y = amps[i], amps[j]
        amps[i] = a * x + b * y
        amps[j] = c * x + d * y


def apply_swap(amps: Vector, qa: int, qb: int) -> None:
    """Swap qubits qa and qb: exchange amplitudes of |..1..0..> and |..0..1..>."""
    abit = 1 << qa
    bbit = 1 << qb
    for i in range(len(amps)):
        if (i & abit) and not (i & bbit):
            j = (i ^ abit) | bbit
            amps[i], amps[j] = amps[j], amps[i]
