"""M2 tests: Kronecker product, Y/Z/S/T, N-qubit single-gate operators."""

import cmath
import math

import pytest

from qengine.gates import H, S, T, X, Y, Z
from qengine.linalg import identity, is_unitary, kron, mat_close, matmul, vec_close
from qengine.operators import single_qubit_operator
from qengine.state import QuantumState

R = 1 / math.sqrt(2)


def scale(M, c):
    return [[c * x for x in row] for row in M]


# ---- new gates ---------------------------------------------------------------

@pytest.mark.parametrize("gate", [H, X, Y, Z, S, T], ids="HXYZST")
def test_all_gates_unitary(gate):
    assert is_unitary(gate)


@pytest.mark.parametrize("gate", [X, Y, Z], ids="XYZ")
def test_paulis_square_to_identity(gate):
    assert mat_close(matmul(gate, gate), identity(2))


def test_s_squared_is_z():
    assert mat_close(matmul(S, S), Z)


def test_t_squared_is_s():
    assert mat_close(matmul(T, T), S)


def test_zxz_is_minus_x():
    assert mat_close(matmul(matmul(Z, X), Z), scale(X, -1))


def test_xy_is_i_z():
    assert mat_close(matmul(X, Y), scale(Z, 1j))


def test_hzh_is_x():
    # Conjugating Z by H turns a phase flip into a bit flip
    assert mat_close(matmul(matmul(H, Z), H), X)


def test_t_phase_value():
    assert abs(T[1][1] - cmath.exp(1j * math.pi / 4)) < 1e-12


# ---- kron --------------------------------------------------------------------

def test_kron_known_example():
    A = [[1, 2], [3, 4]]
    B = [[0, 5], [6, 7]]
    expected = [
        [0, 5, 0, 10],
        [6, 7, 12, 14],
        [0, 15, 0, 20],
        [18, 21, 24, 28],
    ]
    assert mat_close(kron(A, B), expected)


def test_kron_shapes():
    out = kron([[1, 2, 3]], [[1], [2]])  # (1x3) (x) (2x1) -> (2x3)
    assert len(out) == 2 and len(out[0]) == 3


def test_kron_identity_identity_is_bigger_identity():
    assert mat_close(kron(identity(2), identity(2)), identity(4))


def test_kron_mixed_product_property():
    # (A (x) B)(C (x) D) = AC (x) BD
    left = matmul(kron(H, X), kron(Z, S))
    right = kron(matmul(H, Z), matmul(X, S))
    assert mat_close(left, right)


# ---- single_qubit_operator ---------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_operator_size_and_unitarity_for_every_target(n):
    for t in range(n):
        op = single_qubit_operator(H, t, n)
        assert len(op) == 2**n and len(op[0]) == 2**n
        assert is_unitary(op)


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_x_operator_flips_bit_t_of_the_index(n):
    # Column i of X-on-qubit-t is the basis vector with index i XOR (1 << t)
    for t in range(n):
        op = single_qubit_operator(X, t, n)
        for i in range(2**n):
            for row in range(2**n):
                expected = 1 if row == (i ^ (1 << t)) else 0
                assert op[row][i] == expected


def test_operator_matches_explicit_kron_for_two_qubits():
    # little-endian: qubit 0 is the RIGHT factor, qubit 1 the LEFT factor
    assert mat_close(single_qubit_operator(Z, 0, 2), kron(identity(2), Z))
    assert mat_close(single_qubit_operator(Z, 1, 2), kron(Z, identity(2)))


def test_operator_matches_explicit_kron_for_three_qubits_middle():
    assert mat_close(
        single_qubit_operator(Y, 1, 3), kron(kron(identity(2), Y), identity(2))
    )


def test_asymmetric_x_on_q0_only():
    # The qubit-order canary: X on q0 of 3 qubits must give |001>, not |100>
    s = QuantumState(3).apply(single_qubit_operator(X, 0, 3))
    assert repr(s) == "|001\u27e9"


def test_x_on_q2_gives_100():
    s = QuantumState(3).apply(single_qubit_operator(X, 2, 3))
    assert repr(s) == "|100\u27e9"


def test_h_on_q0_of_two_qubits():
    s = QuantumState(2).apply(single_qubit_operator(H, 0, 2))
    assert vec_close(s.amps, [R, R, 0, 0])
    assert repr(s) == "(|00\u27e9 + |01\u27e9)/\u221a2"


def test_h_on_q1_of_two_qubits():
    s = QuantumState(2).apply(single_qubit_operator(H, 1, 2))
    assert vec_close(s.amps, [R, 0, R, 0])
    assert repr(s) == "(|00\u27e9 + |10\u27e9)/\u221a2"


def test_h_on_every_qubit_makes_uniform_superposition():
    n = 3
    s = QuantumState(n)
    for t in range(n):
        s.apply(single_qubit_operator(H, t, n))
    assert vec_close(s.amps, [1 / math.sqrt(8)] * 8)
    assert s.is_normalized()


def test_norm_preserved_through_mixed_circuit():
    s = QuantumState(3)
    for gate, t in [(H, 0), (T, 0), (X, 2), (H, 1), (Y, 2), (S, 1), (H, 2)]:
        s.apply(single_qubit_operator(gate, t, 3))
        assert s.is_normalized()


def test_invalid_targets_and_gate_shapes():
    with pytest.raises(ValueError):
        single_qubit_operator(H, 2, 2)
    with pytest.raises(ValueError):
        single_qubit_operator(H, -1, 2)
    with pytest.raises(ValueError):
        single_qubit_operator(identity(4), 0, 2)
