"""M4 demo: measurement, collapse, entanglement, and sampling histograms."""

from qengine import QuantumCircuit, make_rng, measure_all, measure_qubit, qubit_probabilities


def histogram(counts: dict[str, int], shots: int, width: int = 40) -> None:
    for key, c in counts.items():
        bar = "#" * round(width * c / shots)
        print(f"  |{key}>  {c:>5}  {bar}")


def main() -> None:
    print("== 1. Measuring H|0>: a coin flip that then sticks ==")
    for seed in range(4):
        state = QuantumCircuit(1).h(0).run()
        before = repr(state)
        outcome = measure_qubit(state, 0, make_rng(seed))
        print(f"  seed {seed}: {before}  --measure-->  got {outcome}, state is now {state!r}")

    print("\n== 2. Bell state: measure q0, and q1 is already decided ==")
    for seed in range(5):
        state = QuantumCircuit(2).h(0).cnot(0, 1).run()
        rng = make_rng(seed)
        a = measure_qubit(state, 0, rng)
        _, p1 = qubit_probabilities(state, 1)
        b = measure_qubit(state, 1, rng)
        print(f"  seed {seed}: q0 -> {a}   P(q1=1) is now {p1:.0f}   q1 -> {b}   state {state!r}")

    print("\n== 3. Sampling 1000 shots of a Bell state (state is not collapsed) ==")
    bell = QuantumCircuit(2).h(0).cnot(0, 1)
    histogram(bell.sample(1000, seed=1), 1000)

    print("\n== 4. H on all 3 qubits: 10,000 shots vs theory (12.5% each) ==")
    qc = QuantumCircuit(3)
    for q in range(3):
        qc.h(q)
    counts = qc.sample(10_000, seed=2024)
    histogram(counts, 10_000 // 2)
    print("  theory per outcome: 1250")

    print("\n== 5. Same seed, same answer (reproducible) ==")
    print(" ", bell.sample(10, seed=7))
    print(" ", bell.sample(10, seed=7))

    print("\n== 6. measure_all on a GHZ state ==")
    ghz = QuantumCircuit(3).h(0).cnot(0, 1).cnot(1, 2)
    for seed in range(4):
        state = ghz.run()
        idx = measure_all(state, make_rng(seed))
        print(f"  seed {seed}: got {idx:03b}")


if __name__ == "__main__":
    main()
