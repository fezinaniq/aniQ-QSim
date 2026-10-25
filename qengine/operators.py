"""Build full 2^N x 2^N operators from small gates (the "reference path").

Little-endian convention: qubit 0 is the least significant bit of the basis index.
The Kronecker product lists the most significant factor first, so the factors run
from qubit N-1 on the left down to qubit 0 on the right:

    gate on qubit t of N  =  f(N-1) (x) f(N-2) (x) ... (x) f(0)
    where f(q) = gate if q == t else I
"""

from __future__ import annotations

from .gates import X
from .linalg import Matrix, identity, kron, mat_add

# Projectors and "ladder" matrices used to build multi-qubit gates:
P0: Matrix = [[1 + 0j, 0j], [0j, 0j]]  # |0><0|
P1: Matrix = [[0j, 0j], [0j, 1 + 0j]]  # |1><1|


def _check_qubit(q: int, n_qubits: int, what: str = "qubit") -> None:
    if not 0 <= q < n_qubits:
        raise ValueError(f"{what} {q} out of range for {n_qubits} qubits")


def chain(factors: dict[int, Matrix], n_qubits: int) -> Matrix:
    """Kronecker chain: factors[q] on qubit q, identity on every other qubit."""
    I2 = identity(2)
    result: Matrix = [[1 + 0j]]  # 1x1 identity: the start of the product
    for q in range(n_qubits - 1, -1, -1):
        result = kron(result, factors.get(q, I2))
    return result


def single_qubit_operator(gate: Matrix, target: int, n_qubits: int) -> Matrix:
    """Expand a 2x2 `gate` acting on qubit `target` into a 2^N x 2^N operator."""
    if len(gate) != 2 or any(len(row) != 2 for row in gate):
        raise ValueError("gate must be a 2x2 matrix")
    _check_qubit(target, n_qubits, "target")
    return chain({target: gate}, n_qubits)


def controlled_operator(gate: Matrix, control: int, target: int, n_qubits: int) -> Matrix:
    """Apply `gate` to `target` only when `control` is 1, for any qubit positions.

        C-U = |0><0|_control (x) I   +   |1><1|_control (x) U_target

    Each term is one Kronecker chain; adding them gives the full operator without
    any matrix-matrix multiplication.
    """
    if len(gate) != 2 or any(len(row) != 2 for row in gate):
        raise ValueError("gate must be a 2x2 matrix")
    _check_qubit(control, n_qubits, "control")
    _check_qubit(target, n_qubits, "target")
    if control == target:
        raise ValueError("control and target must be different qubits")
    control_off = chain({control: P0}, n_qubits)
    control_on = chain({control: P1, target: gate}, n_qubits)
    return mat_add(control_off, control_on)


def cnot_operator(control: int, target: int, n_qubits: int) -> Matrix:
    """CNOT = controlled-X."""
    return controlled_operator(X, control, target, n_qubits)


def swap_operator(a: int, b: int, n_qubits: int) -> Matrix:
    """SWAP of qubits a and b.

        SWAP = sum over i,j in {0,1} of  (|i><j|)_a (x) (|j><i|)_b

    On |x>_a |y>_b only the term with j = x and i = y survives, giving |y>_a |x>_b.
    """
    _check_qubit(a, n_qubits, "qubit")
    _check_qubit(b, n_qubits, "qubit")
    if a == b:
        raise ValueError("swap needs two different qubits")
    total: Matrix | None = None
    for i in (0, 1):
        for j in (0, 1):
            e_ij: Matrix = [[0j, 0j], [0j, 0j]]
            e_ij[i][j] = 1 + 0j  # |i><j|
            e_ji: Matrix = [[0j, 0j], [0j, 0j]]
            e_ji[j][i] = 1 + 0j  # |j><i|
            term = chain({a: e_ij, b: e_ji}, n_qubits)
            total = term if total is None else mat_add(total, term)
    assert total is not None
    return total
