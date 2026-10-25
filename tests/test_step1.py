"""Step 1 tests: QuantumState, H, X, matvec, is_unitary."""

import math

import pytest

from qengine.gates import H, X
from qengine.linalg import identity, is_unitary, mat_close, matmul, matvec, vec_close
from qengine.state import QuantumState

R = 1 / math.sqrt(2)


# ---- gates ------------------------------------------------------------------

@pytest.mark.parametrize("gate", [H, X], ids=["H", "X"])
def test_gates_are_unitary(gate):
    assert is_unitary(gate)


def test_is_unitary_rejects_non_unitary():
    assert not is_unitary([[1, 1], [0, 1]])
    assert not is_unitary([[1, 0, 0], [0, 1, 0]])  # not square


def test_hh_is_identity():
    assert mat_close(matmul(H, H), identity(2))


def test_xx_is_identity():
    assert mat_close(matmul(X, X), identity(2))


# ---- matvec -----------------------------------------------------------------

def test_matvec_basic():
    assert vec_close(matvec(X, [1, 0]), [0, 1])


def test_matvec_shape_mismatch():
    with pytest.raises(ValueError):
        matvec(H, [1, 0, 0])


# ---- state ------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3, 5])
def test_initial_state_is_all_zeros_ket(n):
    s = QuantumState(n)
    assert len(s.amps) == 2**n
    assert s.amps[0] == 1
    assert all(a == 0 for a in s.amps[1:])
    assert s.is_normalized()
    assert s.probabilities()[0] == pytest.approx(1.0)


def test_invalid_constructor_args():
    with pytest.raises(ValueError):
        QuantumState(0)
    with pytest.raises(ValueError):
        QuantumState(2, amplitudes=[1, 0, 0])


def test_h_on_zero_gives_plus_state():
    s = QuantumState(1).apply(H)
    assert vec_close(s.amps, [R, R])
    assert s.norm() == pytest.approx(1.0)
    assert s.probabilities() == pytest.approx([0.5, 0.5])


def test_x_on_zero_gives_one():
    s = QuantumState(1).apply(X)
    assert vec_close(s.amps, [0, 1])


def test_h_on_one_gives_minus_state():
    s = QuantumState(1).apply(X).apply(H)
    assert vec_close(s.amps, [R, -R])


def test_hh_returns_to_zero():
    s = QuantumState(1).apply(H).apply(H)
    assert vec_close(s.amps, [1, 0])


def test_norm_preserved_through_gate_sequence():
    s = QuantumState(1)
    for gate in (H, X, H, H, X, H):
        s.apply(gate)
        assert s.is_normalized()


def test_apply_wrong_size_operator():
    with pytest.raises(ValueError):
        QuantumState(2).apply(H)


# ---- ket display + qubit ordering convention ---------------------------------

def test_ket_zero_state():
    assert repr(QuantumState(1)) == "|0\u27e9"


def test_ket_plus_state():
    assert repr(QuantumState(1).apply(H)) == "(|0\u27e9 + |1\u27e9)/\u221a2"


def test_ket_minus_state():
    assert repr(QuantumState(1).apply(X).apply(H)) == "(|0\u27e9 - |1\u27e9)/\u221a2"


def test_ket_uniform_two_qubits_uses_integer_denominator():
    s = QuantumState(2, amplitudes=[0.5, 0.5, 0.5, 0.5])
    assert repr(s) == "(|00\u27e9 + |01\u27e9 + |10\u27e9 + |11\u27e9)/2"


def test_ket_bell_state():
    s = QuantumState(2, amplitudes=[R, 0, 0, R])
    assert repr(s) == "(|00\u27e9 + |11\u27e9)/\u221a2"


def test_ket_imaginary_phase():
    s = QuantumState(1, amplitudes=[R, 1j * R])
    assert repr(s) == "(|0\u27e9 + i|1\u27e9)/\u221a2"


def test_ket_uneven_amplitudes_fall_back_to_decimals():
    s = QuantumState(1, amplitudes=[math.sqrt(0.9), -math.sqrt(0.1)])
    assert repr(s) == "0.9487|0\u27e9 - 0.3162|1\u27e9"


def test_little_endian_ordering():
    # Index 5 = 0b101 -> q2=1, q1=0, q0=1 -> printed |q2 q1 q0> = |101>
    amps = [0] * 8
    amps[5] = 1
    assert repr(QuantumState(3, amplitudes=amps)) == "|101\u27e9"
    # Index 1 is "q0 = 1 and nothing else" -> |001>, not |100>
    amps = [0] * 8
    amps[1] = 1
    assert repr(QuantumState(3, amplitudes=amps)) == "|001\u27e9"
