"""QuantumCircuit: an ordered list of instructions, stored as plain data.

An instruction is (name, targets, params), e.g. ("h", (0,), ()) or ("cnot", (0, 1), ()).
For cnot, targets = (control, target). The Minecraft compiler will emit this same
structure, so the engine never needs to know where a circuit came from.
"""

from __future__ import annotations

from typing import NamedTuple

from . import fastpath
from .gates import H, S, T, X, Y, Z
from .linalg import Matrix
from .measure import make_rng, sample
from .operators import cnot_operator, single_qubit_operator, swap_operator
from .state import QuantumState

SINGLE_QUBIT_GATES: dict[str, Matrix] = {"h": H, "x": X, "y": Y, "z": Z, "s": S, "t": T}
TWO_QUBIT_GATES = ("cnot", "swap")


class Instruction(NamedTuple):
    name: str
    targets: tuple[int, ...]
    params: tuple[float, ...] = ()


class QuantumCircuit:
    def __init__(self, n_qubits: int) -> None:
        if not isinstance(n_qubits, int) or n_qubits < 1:
            raise ValueError("n_qubits must be an integer >= 1")
        self.n_qubits = n_qubits
        self.instructions: list[Instruction] = []

    # ---- building ---------------------------------------------------------

    def add(self, name: str, *targets: int, params: tuple[float, ...] = ()) -> QuantumCircuit:
        """Validate and append an instruction by name. Returns self for chaining."""
        name = name.lower()
        if name in SINGLE_QUBIT_GATES:
            expected = 1
        elif name in TWO_QUBIT_GATES:
            expected = 2
        else:
            raise ValueError(f"unknown gate '{name}'")
        if len(targets) != expected:
            raise ValueError(f"gate '{name}' takes {expected} qubit(s), got {len(targets)}")
        for q in targets:
            if not isinstance(q, int) or not 0 <= q < self.n_qubits:
                raise ValueError(f"qubit {q} out of range for {self.n_qubits} qubits")
        if len(set(targets)) != len(targets):
            raise ValueError(f"gate '{name}' needs distinct qubits, got {targets}")
        self.instructions.append(Instruction(name, tuple(targets), tuple(params)))
        return self

    def h(self, q: int) -> QuantumCircuit:
        return self.add("h", q)

    def x(self, q: int) -> QuantumCircuit:
        return self.add("x", q)

    def y(self, q: int) -> QuantumCircuit:
        return self.add("y", q)

    def z(self, q: int) -> QuantumCircuit:
        return self.add("z", q)

    def s(self, q: int) -> QuantumCircuit:
        return self.add("s", q)

    def t(self, q: int) -> QuantumCircuit:
        return self.add("t", q)

    def cnot(self, control: int, target: int) -> QuantumCircuit:
        return self.add("cnot", control, target)

    def swap(self, a: int, b: int) -> QuantumCircuit:
        return self.add("swap", a, b)

    def __len__(self) -> int:
        return len(self.instructions)

    # ---- running ----------------------------------------------------------

    def run(self, method: str = "fast") -> QuantumState:
        """Run from |00...0> and return the final QuantumState.

        method="fast":      in-place pair updates, O(2^N) per gate.
        method="reference": build the full 2^N x 2^N operator for each gate with
                            Kronecker products, then matrix-vector multiply.
        Both must give identical results; a test enforces it.
        """
        if method not in ("fast", "reference"):
            raise ValueError("method must be 'fast' or 'reference'")
        state = QuantumState(self.n_qubits)
        for inst in self.instructions:
            if method == "fast":
                self._apply_fast(state, inst)
            else:
                state.apply(self._operator(inst))
        return state

    def _apply_fast(self, state: QuantumState, inst: Instruction) -> None:
        if inst.name in SINGLE_QUBIT_GATES:
            fastpath.apply_single_qubit(state.amps, SINGLE_QUBIT_GATES[inst.name], inst.targets[0])
        elif inst.name == "cnot":
            fastpath.apply_controlled(state.amps, X, inst.targets[0], inst.targets[1])
        else:  # swap
            fastpath.apply_swap(state.amps, inst.targets[0], inst.targets[1])

    def _operator(self, inst: Instruction) -> Matrix:
        n = self.n_qubits
        if inst.name in SINGLE_QUBIT_GATES:
            return single_qubit_operator(SINGLE_QUBIT_GATES[inst.name], inst.targets[0], n)
        if inst.name == "cnot":
            return cnot_operator(inst.targets[0], inst.targets[1], n)
        return swap_operator(inst.targets[0], inst.targets[1], n)

    def sample(self, shots: int = 1000, seed: int | None = None, method: str = "fast") -> dict[str, int]:
        """Run the circuit once, then measure the final state `shots` times.

        Returns {bitstring: count}, e.g. {'00': 507, '11': 493} for a Bell state.
        Pass `seed` for reproducible counts.
        """
        return sample(self.run(method), shots, make_rng(seed))
