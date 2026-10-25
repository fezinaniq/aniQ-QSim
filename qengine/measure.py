"""Measurement: probabilities, sampling, and collapse.

Everything that needs randomness takes an optional `rng` (a random.Random). Pass
`make_rng(seed)` to get reproducible results; pass nothing for fresh randomness.

Qubit ordering is the project convention: qubit 0 is the least significant bit of
the basis index, and bitstrings print as q(n-1) ... q0.
"""

from __future__ import annotations

import math
import random
from collections import Counter

from .state import QuantumState


def make_rng(seed: int | None = None) -> random.Random:
    """A private random generator. Same seed -> same sequence of results."""
    return random.Random(seed)


def bitstring(index: int, n_qubits: int) -> str:
    """Basis index -> bitstring, e.g. index 5 on 3 qubits -> '101' (q2 q1 q0)."""
    return format(index, f"0{n_qubits}b")


def _check_qubit(state: QuantumState, qubit: int) -> None:
    if not isinstance(qubit, int) or not 0 <= qubit < state.n_qubits:
        raise ValueError(f"qubit {qubit} out of range for {state.n_qubits} qubits")


def qubit_probabilities(state: QuantumState, qubit: int) -> tuple[float, float]:
    """(P(qubit = 0), P(qubit = 1)): add up the probabilities of every basis state
    whose `qubit` bit is 0, and of every one whose bit is 1. Does not change the state."""
    _check_qubit(state, qubit)
    bit = 1 << qubit
    p0 = p1 = 0.0
    for i, a in enumerate(state.amps):
        if i & bit:
            p1 += abs(a) ** 2
        else:
            p0 += abs(a) ** 2
    return p0, p1


def measure_qubit(state: QuantumState, qubit: int, rng: random.Random | None = None) -> int:
    """Measure one qubit. Returns 0 or 1 and collapses the state in place:

    1. compute P(0) and P(1) for that qubit,
    2. pick an outcome at random with those weights,
    3. zero every amplitude whose `qubit` bit disagrees with the outcome,
    4. divide the survivors by sqrt(P(outcome)) so the norm is 1 again.
    """
    rng = rng if rng is not None else random.Random()
    p0, p1 = qubit_probabilities(state, qubit)
    outcome = rng.choices([0, 1], weights=[p0, p1])[0]
    scale = 1 / math.sqrt(p1 if outcome else p0)
    for i, a in enumerate(state.amps):
        state.amps[i] = a * scale if ((i >> qubit) & 1) == outcome else 0j
    return outcome


def measure_all(state: QuantumState, rng: random.Random | None = None) -> int:
    """Measure every qubit at once. Returns the basis index and collapses the state
    to that single basis state."""
    rng = rng if rng is not None else random.Random()
    index = rng.choices(range(len(state.amps)), weights=state.probabilities())[0]
    state.amps = [0j] * len(state.amps)
    state.amps[index] = 1 + 0j
    return index


def sample(
    state: QuantumState, shots: int = 1000, rng: random.Random | None = None
) -> dict[str, int]:
    """Measure `shots` fresh copies of the state and count the outcomes.

    The state itself is NOT collapsed or changed. Returns {bitstring: count},
    sorted by bitstring, only listing outcomes that actually occurred.
    """
    if not isinstance(shots, int) or shots < 1:
        raise ValueError("shots must be an integer >= 1")
    rng = rng if rng is not None else random.Random()
    indices = rng.choices(range(len(state.amps)), weights=state.probabilities(), k=shots)
    counts = Counter(indices)
    return {bitstring(i, state.n_qubits): counts[i] for i in sorted(counts)}
