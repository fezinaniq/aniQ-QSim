"""Plain-text circuits: parse them into a QuantumCircuit and write them back out.

Format: one instruction per line, or several separated by ';'. '#' starts a comment.

    h 0
    cnot 0 1      # control first, then target
    swap 0 2

Gate names (case-insensitive): h x y z s t cnot swap  (alias: cx = cnot).
"""

from __future__ import annotations

import re

from .circuit import SINGLE_QUBIT_GATES, QuantumCircuit

ALIASES = {"cx": "cnot"}
ARITY = {**dict.fromkeys(SINGLE_QUBIT_GATES, 1), "cnot": 2, "swap": 2}


class CircuitParseError(ValueError):
    """Raised for malformed circuit text; the message says which instruction is wrong."""


def parse_circuit(text: str, n_qubits: int | None = None) -> QuantumCircuit:
    """Build a QuantumCircuit from text. If n_qubits is None it is inferred as
    (highest qubit index used) + 1."""
    parsed: list[tuple[str, tuple[int, ...]]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        code = raw.split("#", 1)[0]
        for chunk in re.split(r";", code):
            tokens = chunk.split()
            if not tokens:
                continue
            name = ALIASES.get(tokens[0].lower(), tokens[0].lower())
            where = f"line {line_no}: '{chunk.strip()}'"
            if name not in ARITY:
                raise CircuitParseError(f"{where}: unknown gate '{tokens[0]}'")
            args = tokens[1:]
            if len(args) != ARITY[name]:
                raise CircuitParseError(
                    f"{where}: '{name}' takes {ARITY[name]} qubit(s), got {len(args)}"
                )
            try:
                qubits = tuple(int(a) for a in args)
            except ValueError:
                raise CircuitParseError(f"{where}: qubit indices must be integers") from None
            parsed.append((name, qubits))

    if n_qubits is None:
        n_qubits = max(1, max((q for _, qs in parsed for q in qs), default=0) + 1)
    circuit = QuantumCircuit(n_qubits)
    for name, qubits in parsed:
        try:
            circuit.add(name, *qubits)
        except ValueError as exc:
            raise CircuitParseError(f"'{name} {' '.join(map(str, qubits))}': {exc}") from None
    return circuit


def circuit_to_text(circuit: QuantumCircuit) -> str:
    """One instruction per line; parse_circuit(circuit_to_text(c)) rebuilds the circuit."""
    return "\n".join(f"{i.name} {' '.join(map(str, i.targets))}" for i in circuit.instructions)
