"""M3 tests: CNOT, SWAP, fast path, QuantumCircuit, Bell and GHZ states."""

import math
import random

import pytest

from qengine import QuantumCircuit, QuantumState
from qengine.circuit import SINGLE_QUBIT_GATES
from qengine.fastpath import apply_controlled, apply_single_qubit, apply_swap
from qengine.gates import CNOT, SWAP, X
from qengine.linalg import identity, is_unitary, mat_close, matmul, vec_close
from qengine.operators import (
    cnot_operator,
    controlled_operator,
    single_qubit_operator,
    swap_operator,
)

R = 1 / math.sqrt(2)
BRA = "\u27e9"


def ket_state(n, index):
    amps = [0] * 2**n
    amps[index] = 1
    return QuantumState(n, amplitudes=amps)


def random_state(n, rng):
    amps = [complex(rng.gauss(0, 1), rng.gauss(0, 1)) for _ in range(2**n)]
    norm = math.sqrt(sum(abs(a) ** 2 for a in amps))
    return [a / norm for a in amps]


# ---- gate matrices -----------------------------------------------------------

def test_cnot_and_swap_constants_unitary():
    assert is_unitary(CNOT)
    assert is_unitary(SWAP)


def test_cnot_squared_is_identity():
    assert mat_close(matmul(CNOT, CNOT), identity(4))


def test_swap_squared_is_identity():
    assert mat_close(matmul(SWAP, SWAP), identity(4))


def test_cnot_operator_matches_textbook_matrix():
    # control = q1 (left bit), target = q0 (right bit)
    assert mat_close(cnot_operator(1, 0, 2), CNOT)


def test_swap_operator_matches_textbook_matrix():
    assert mat_close(swap_operator(0, 1, 2), SWAP)
    assert mat_close(swap_operator(1, 0, 2), SWAP)


# ---- CNOT behaviour with asymmetric inputs (qubit-order canaries) -------------

def test_cnot_control0_target1_fires_on_q0_set():
    # |01> means q0=1. Control is q0, so the target q1 flips -> |11>
    out = ket_state(2, 0b01).apply(cnot_operator(0, 1, 2))
    assert repr(out) == f"|11{BRA}"


def test_cnot_control0_target1_ignores_q1_set():
    # |10> means q1=1 but control q0=0, so nothing happens
    out = ket_state(2, 0b10).apply(cnot_operator(0, 1, 2))
    assert repr(out) == f"|10{BRA}"


def test_cnot_control1_target0_fires_on_q1_set():
    out = ket_state(2, 0b10).apply(cnot_operator(1, 0, 2))
    assert repr(out) == f"|11{BRA}"


def test_cnot_non_adjacent_qubits():
    # control q0, target q2 on 3 qubits: |001> -> |101>
    out = ket_state(3, 0b001).apply(cnot_operator(0, 2, 3))
    assert repr(out) == f"|101{BRA}"
    # control not set: |010> unchanged
    out = ket_state(3, 0b010).apply(cnot_operator(0, 2, 3))
    assert repr(out) == f"|010{BRA}"


@pytest.mark.parametrize("n", [2, 3, 4])
def test_all_cnot_and_swap_placements_unitary(n):
    for a in range(n):
        for b in range(n):
            if a != b:
                assert is_unitary(cnot_operator(a, b, n))
                assert is_unitary(swap_operator(a, b, n))


def test_swap_exchanges_bits():
    out = ket_state(3, 0b001).apply(swap_operator(0, 2, 3))
    assert repr(out) == f"|100{BRA}"
    out = ket_state(3, 0b011).apply(swap_operator(0, 2, 3))  # q0=1,q1=1 -> q2=1,q1=1
    assert repr(out) == f"|110{BRA}"


@pytest.mark.parametrize("n", [2, 3, 4])
def test_swap_operator_is_bit_permutation(n):
    for a in range(n):
        for b in range(a + 1, n):
            op = swap_operator(a, b, n)
            for i in range(2**n):
                ba, bb = (i >> a) & 1, (i >> b) & 1
                j = (i & ~((1 << a) | (1 << b))) | (bb << a) | (ba << b)
                assert op[j][i] == 1


def test_controlled_operator_validation():
    with pytest.raises(ValueError):
        controlled_operator(X, 0, 0, 2)
    with pytest.raises(ValueError):
        controlled_operator(X, 0, 5, 2)
    with pytest.raises(ValueError):
        swap_operator(1, 1, 3)


# ---- fast path equals reference path -------------------------------------------

@pytest.mark.parametrize("name", sorted(SINGLE_QUBIT_GATES))
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_fast_single_qubit_matches_reference(name, n):
    rng = random.Random(1234)
    gate = SINGLE_QUBIT_GATES[name]
    for t in range(n):
        amps = random_state(n, rng)
        ref = QuantumState(n, amplitudes=amps).apply(single_qubit_operator(gate, t, n)).amps
        fast = list(amps)
        apply_single_qubit(fast, gate, t)
        assert vec_close(ref, fast)


@pytest.mark.parametrize("n", [2, 3, 4])
def test_fast_cnot_and_swap_match_reference(n):
    rng = random.Random(99)
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            amps = random_state(n, rng)
            ref = QuantumState(n, amplitudes=amps).apply(cnot_operator(a, b, n)).amps
            fast = list(amps)
            apply_controlled(fast, X, a, b)
            assert vec_close(ref, fast)

            ref = QuantumState(n, amplitudes=amps).apply(swap_operator(a, b, n)).amps
            fast = list(amps)
            apply_swap(fast, a, b)
            assert vec_close(ref, fast)


def random_circuit(n, length, rng):
    qc = QuantumCircuit(n)
    names = sorted(SINGLE_QUBIT_GATES)
    for _ in range(length):
        kind = rng.random()
        if n >= 2 and kind < 0.3:
            a, b = rng.sample(range(n), 2)
            qc.cnot(a, b)
        elif n >= 2 and kind < 0.4:
            a, b = rng.sample(range(n), 2)
            qc.swap(a, b)
        else:
            qc.add(rng.choice(names), rng.randrange(n))
    return qc


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_fast_equals_reference_on_random_circuits(n):
    rng = random.Random(2024 + n)
    for _ in range(10):
        qc = random_circuit(n, 25, rng)
        fast = qc.run("fast")
        ref = qc.run("reference")
        assert vec_close(fast.amps, ref.amps, tol=1e-9)
        assert fast.is_normalized()


# ---- QuantumCircuit API ------------------------------------------------------

def test_instructions_are_plain_data():
    qc = QuantumCircuit(2).h(0).cnot(0, 1)
    assert qc.instructions == [("h", (0,), ()), ("cnot", (0, 1), ())]
    assert len(qc) == 2


def test_run_is_repeatable_and_does_not_mutate_circuit():
    qc = QuantumCircuit(2).h(0).cnot(0, 1)
    first = qc.run().amps
    second = qc.run().amps
    assert first == second
    assert len(qc) == 2


def test_empty_circuit_gives_zero_state():
    assert repr(QuantumCircuit(3).run()) == f"|000{BRA}"


@pytest.mark.parametrize(
    "build",
    [
        lambda: QuantumCircuit(0),
        lambda: QuantumCircuit(2).h(2),
        lambda: QuantumCircuit(2).h(-1),
        lambda: QuantumCircuit(2).cnot(0, 0),
        lambda: QuantumCircuit(2).add("toffoli", 0, 1),
        lambda: QuantumCircuit(2).add("cnot", 0),
        lambda: QuantumCircuit(2).run("magic"),
    ],
)
def test_circuit_validation(build):
    with pytest.raises(ValueError):
        build()


def test_norm_preserved_after_every_instruction():
    qc = random_circuit(4, 30, random.Random(7))
    for k in range(len(qc) + 1):
        partial = QuantumCircuit(4)
        partial.instructions = qc.instructions[:k]
        assert partial.run().is_normalized()


# ---- the headline states ------------------------------------------------------

def test_bell_state():
    state = QuantumCircuit(2).h(0).cnot(0, 1).run()
    assert state.probabilities() == pytest.approx([0.5, 0, 0, 0.5])
    assert vec_close(state.amps, [R, 0, 0, R])
    assert repr(state) == f"(|00{BRA} + |11{BRA})/\u221a2"


def test_bell_state_with_roles_reversed_is_the_same():
    state = QuantumCircuit(2).h(1).cnot(1, 0).run()
    assert vec_close(state.amps, [R, 0, 0, R])


def test_other_bell_states():
    psi_plus = QuantumCircuit(2).h(0).cnot(0, 1).x(1).run()
    assert repr(psi_plus) == f"(|01{BRA} + |10{BRA})/\u221a2"
    phi_minus = QuantumCircuit(2).h(0).cnot(0, 1).z(0).run()
    assert repr(phi_minus) == f"(|00{BRA} - |11{BRA})/\u221a2"
    psi_minus = QuantumCircuit(2).h(0).cnot(0, 1).x(1).z(1).run()
    assert repr(psi_minus) == f"(|01{BRA} - |10{BRA})/\u221a2"


@pytest.mark.parametrize("n", [3, 4, 5])
def test_ghz_state(n):
    qc = QuantumCircuit(n).h(0)
    for q in range(n - 1):
        qc.cnot(q, q + 1)
    for method in ("fast", "reference"):
        state = qc.run(method)
        probs = state.probabilities()
        assert probs[0] == pytest.approx(0.5)
        assert probs[-1] == pytest.approx(0.5)
        assert sum(probs[1:-1]) == pytest.approx(0.0)
    assert repr(qc.run()) == f"(|{'0' * n}{BRA} + |{'1' * n}{BRA})/\u221a2"


def test_swap_then_h_example():
    # X on q0, swap q0<->q1 -> |10>; H on q1 -> (|00> - |10>)/sqrt(2)
    state = QuantumCircuit(2).x(0).swap(0, 1).h(1).run()
    assert repr(state) == f"(|00{BRA} - |10{BRA})/\u221a2"
