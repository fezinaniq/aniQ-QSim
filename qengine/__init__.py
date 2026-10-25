"""qengine: a from-scratch quantum simulation engine. Zero Minecraft imports."""

from .circuit import QuantumCircuit
from .draw import draw_circuit, format_histogram, format_state
from .gates import CNOT, SWAP, H, S, T, X, Y, Z
from .linalg import is_unitary, kron, matvec
from .measure import make_rng, measure_all, measure_qubit, qubit_probabilities, sample
from .operators import (
    cnot_operator,
    controlled_operator,
    single_qubit_operator,
    swap_operator,
)
from .parser import CircuitParseError, circuit_to_text, parse_circuit
from .state import QuantumState

__all__ = [
    "CNOT",
    "SWAP",
    "CircuitParseError",
    "H",
    "QuantumCircuit",
    "QuantumState",
    "S",
    "T",
    "X",
    "Y",
    "Z",
    "circuit_to_text",
    "cnot_operator",
    "controlled_operator",
    "draw_circuit",
    "format_histogram",
    "format_state",
    "is_unitary",
    "kron",
    "make_rng",
    "matvec",
    "measure_all",
    "measure_qubit",
    "parse_circuit",
    "qubit_probabilities",
    "sample",
    "single_qubit_operator",
    "swap_operator",
]
