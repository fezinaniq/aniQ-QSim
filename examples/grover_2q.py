"""Grover's search on 2 qubits: find a marked item among 4 with ONE oracle call.

Classically you need up to 3 guesses to be sure. Grover's algorithm on 4 items
amplifies the marked state to probability 1 after a single iteration.

We have no native CZ gate, but CZ(a, b) = H(b) CNOT(a, b) H(b).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qengine import QuantumCircuit, draw_circuit, format_state


def cz(qc: QuantumCircuit, a: int, b: int) -> None:
    """Controlled-Z built from H and CNOT: flips the sign of |11> only."""
    qc.h(b).cnot(a, b).h(b)


def grover_2q(marked: str = "11") -> QuantumCircuit:
    """`marked` is written |q1 q0>, e.g. '10' means q1=1, q0=0."""
    if len(marked) != 2 or set(marked) - {"0", "1"}:
        raise ValueError("marked must be a 2-bit string like '10'")
    qc = QuantumCircuit(2)
    qc.h(0).h(1)  # 1. uniform superposition over all 4 states

    zero_bits = [q for q in (0, 1) if marked[1 - q] == "0"]
    for q in zero_bits:  # 2. oracle: flip the sign of the marked state
        qc.x(q)
    cz(qc, 0, 1)
    for q in zero_bits:
        qc.x(q)

    qc.h(0).h(1).x(0).x(1)  # 3. diffusion: reflect all amplitudes about their mean
    cz(qc, 0, 1)
    qc.x(0).x(1).h(0).h(1)
    return qc


if __name__ == "__main__":
    target = "10"
    qc = grover_2q(target)
    print(f"Searching for |{target}>\n")
    print(draw_circuit(qc))
    print()
    print(format_state(qc.run()))
