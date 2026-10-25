"""M4 tests: probabilities, measurement, collapse, sampling, seeded RNG."""

import math

import pytest

from qengine import QuantumCircuit, QuantumState
from qengine.measure import (
    bitstring,
    make_rng,
    measure_all,
    measure_qubit,
    qubit_probabilities,
    sample,
)

R = 1 / math.sqrt(2)
KET_END = "\u27e9"


def bell():
    return QuantumCircuit(2).h(0).cnot(0, 1).run()


def _hall(n):
    qc = QuantumCircuit(n)
    for q in range(n):
        qc.h(q)
    return qc.run()


def chi_squared(counts, probs, shots, n):
    total = 0.0
    for i, p in enumerate(probs):
        expected = shots * p
        observed = counts.get(bitstring(i, n), 0)
        if expected > 0:
            total += (observed - expected) ** 2 / expected
        else:
            assert observed == 0
    return total


# ---- helpers ------------------------------------------------------------------

def test_bitstring_is_little_endian_display():
    assert bitstring(5, 3) == "101"
    assert bitstring(1, 3) == "001"
    assert bitstring(0, 2) == "00"


def test_copy_is_independent():
    a = QuantumState(1)
    b = a.copy()
    b.amps[0] = 0j
    assert a.amps[0] == 1


# ---- per-qubit probabilities (no collapse) ---------------------------------------

def test_qubit_probabilities_of_zero_state():
    s = QuantumState(3)
    for q in range(3):
        assert qubit_probabilities(s, q) == pytest.approx((1.0, 0.0))


def test_qubit_probabilities_asymmetric():
    s = QuantumCircuit(3).x(0).run()  # |001>: q0=1, q1=0, q2=0
    assert qubit_probabilities(s, 0) == pytest.approx((0.0, 1.0))
    assert qubit_probabilities(s, 1) == pytest.approx((1.0, 0.0))
    assert qubit_probabilities(s, 2) == pytest.approx((1.0, 0.0))


def test_qubit_probabilities_bell_both_half():
    s = bell()
    assert qubit_probabilities(s, 0) == pytest.approx((0.5, 0.5))
    assert qubit_probabilities(s, 1) == pytest.approx((0.5, 0.5))


def test_qubit_probabilities_do_not_change_state():
    s = bell()
    before = list(s.amps)
    qubit_probabilities(s, 0)
    assert s.amps == before


def test_qubit_out_of_range():
    with pytest.raises(ValueError):
        qubit_probabilities(QuantumState(2), 2)
    with pytest.raises(ValueError):
        measure_qubit(QuantumState(2), -1)


# ---- measure_qubit + collapse -------------------------------------------------------

def test_measuring_definite_qubit_is_certain_and_leaves_state_alone():
    s = QuantumCircuit(2).x(0).run()  # |01>
    assert measure_qubit(s, 0, make_rng(1)) == 1
    assert measure_qubit(s, 1, make_rng(1)) == 0
    assert repr(s) == f"|01{KET_END}"


def test_measure_plus_state_collapses_to_basis_state():
    for seed in range(20):
        s = QuantumCircuit(1).h(0).run()
        outcome = measure_qubit(s, 0, make_rng(seed))
        assert outcome in (0, 1)
        assert repr(s) == f"|{outcome}{KET_END}"
        assert s.is_normalized()


def test_collapse_zeroes_inconsistent_amplitudes_and_renormalizes():
    for seed in range(10):
        s = _hall(3)  # 8 amplitudes, each 1/sqrt(8)
        outcome = measure_qubit(s, 1, make_rng(seed))
        assert s.is_normalized()
        for i, a in enumerate(s.amps):
            if ((i >> 1) & 1) == outcome:
                assert a == pytest.approx(0.5)  # 1/sqrt(8) / sqrt(1/2) = 1/2
            else:
                assert a == 0


def test_repeated_measurement_gives_same_answer():
    s = QuantumCircuit(1).h(0).run()
    rng = make_rng(5)
    first = measure_qubit(s, 0, rng)
    for _ in range(10):
        assert measure_qubit(s, 0, rng) == first


def test_measurement_statistics_of_plus_state():
    rng = make_rng(2024)
    ones = 0
    shots = 4000
    for _ in range(shots):
        s = QuantumCircuit(1).h(0).run()
        ones += measure_qubit(s, 0, rng)
    sigma = math.sqrt(shots * 0.25)
    assert abs(ones - shots / 2) < 5 * sigma


def test_biased_qubit_statistics():
    # Amplitudes sqrt(0.2), sqrt(0.8): P(1) = 0.8
    rng = make_rng(11)
    shots = 4000
    ones = 0
    for _ in range(shots):
        s = QuantumState(1, amplitudes=[math.sqrt(0.2), math.sqrt(0.8)])
        ones += measure_qubit(s, 0, rng)
    sigma = math.sqrt(shots * 0.8 * 0.2)
    assert abs(ones - 0.8 * shots) < 5 * sigma


# ---- entanglement through measurement ---------------------------------------------

@pytest.mark.parametrize("first,second", [(0, 1), (1, 0)])
def test_bell_measurements_are_perfectly_correlated(first, second):
    seen = set()
    for seed in range(60):
        s = bell()
        rng = make_rng(seed)
        a = measure_qubit(s, first, rng)
        # measuring one qubit already fixed the other
        assert qubit_probabilities(s, second) == pytest.approx((1.0, 0.0) if a == 0 else (0.0, 1.0))
        b = measure_qubit(s, second, rng)
        assert a == b
        assert repr(s) == f"|{a}{a}{KET_END}"
        seen.add(a)
    assert seen == {0, 1}  # both outcomes really do happen


def test_ghz_all_qubits_agree():
    qc = QuantumCircuit(4).h(0).cnot(0, 1).cnot(1, 2).cnot(2, 3)
    for seed in range(30):
        s = qc.run()
        rng = make_rng(seed)
        bits = [measure_qubit(s, q, rng) for q in range(4)]
        assert len(set(bits)) == 1


# ---- measure_all -----------------------------------------------------------------------

def test_measure_all_collapses_to_returned_index():
    for seed in range(20):
        s = _hall(3)
        idx = measure_all(s, make_rng(seed))
        assert 0 <= idx < 8
        assert s.amps[idx] == 1
        assert sum(1 for a in s.amps if a != 0) == 1
        assert s.is_normalized()


def test_measure_all_on_bell_only_00_or_11():
    outcomes = {measure_all(bell(), make_rng(seed)) for seed in range(40)}
    assert outcomes == {0b00, 0b11}


# ---- sample ----------------------------------------------------------------------------

def test_sample_does_not_collapse_state():
    s = bell()
    before = list(s.amps)
    sample(s, 500, make_rng(3))
    assert s.amps == before


def test_sample_counts_sum_to_shots_and_keys_are_bitstrings():
    counts = sample(_hall(3), 1000, make_rng(1))
    assert sum(counts.values()) == 1000
    assert all(len(k) == 3 and set(k) <= {"0", "1"} for k in counts)


def test_sample_bell_only_00_and_11():
    counts = sample(bell(), 1000, make_rng(7))
    assert set(counts) == {"00", "11"}
    assert abs(counts["00"] - 500) < 80  # ~5 sigma


def test_sample_is_reproducible_with_seed():
    a = sample(_hall(3), 500, make_rng(42))
    b = sample(_hall(3), 500, make_rng(42))
    assert a == b


def test_different_seeds_differ():
    a = sample(_hall(3), 500, make_rng(1))
    b = sample(_hall(3), 500, make_rng(2))
    assert a != b


def test_sample_chi_squared_uniform_3_qubits():
    shots = 10_000
    counts = sample(_hall(3), shots, make_rng(123))
    stat = chi_squared(counts, [1 / 8] * 8, shots, 3)
    assert stat < 24.32  # chi^2, 7 dof, p = 0.001


def test_sample_chi_squared_biased_distribution():
    probs = [0.1, 0.2, 0.3, 0.4]
    s = QuantumState(2, amplitudes=[math.sqrt(p) for p in probs])
    shots = 10_000
    counts = sample(s, shots, make_rng(99))
    stat = chi_squared(counts, probs, shots, 2)
    assert stat < 16.27  # chi^2, 3 dof, p = 0.001


def test_sample_validation():
    with pytest.raises(ValueError):
        sample(bell(), 0)
    with pytest.raises(ValueError):
        sample(bell(), -5)


# ---- QuantumCircuit.sample ---------------------------------------------------------------

def test_circuit_sample_bell():
    counts = QuantumCircuit(2).h(0).cnot(0, 1).sample(1000, seed=1)
    assert set(counts) == {"00", "11"}
    assert sum(counts.values()) == 1000
    assert abs(counts["00"] - 500) < 80


def test_circuit_sample_seeded_and_methods_agree():
    qc = QuantumCircuit(3).h(0).cnot(0, 1).cnot(1, 2)
    assert qc.sample(500, seed=8) == qc.sample(500, seed=8)
    assert qc.sample(500, seed=8, method="fast") == qc.sample(500, seed=8, method="reference")


def test_circuit_sample_deterministic_circuit():
    # X on q0 and q2 -> |101> every single shot
    assert QuantumCircuit(3).x(0).x(2).sample(200, seed=0) == {"101": 200}
