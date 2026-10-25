"""M3 demo: Bell and GHZ states, and the fast path vs the reference path."""

import time

from qengine import QuantumCircuit


def ladder(n: int) -> QuantumCircuit:
    qc = QuantumCircuit(n).h(0)
    for q in range(n - 1):
        qc.cnot(q, q + 1)
    return qc


def main() -> None:
    print("== Bell state: H on q0, CNOT(q0 -> q1) ==")
    bell = QuantumCircuit(2).h(0).cnot(0, 1)
    state = bell.run()
    print(f"state         : {state!r}")
    for i, p in enumerate(state.probabilities()):
        print(f"  P(|{i:02b}>) = {p:.3f}")
    print("-> only 00 and 11 can happen: the two qubits always agree (entanglement)")

    print("\n== GHZ state (4 qubits) ==")
    print(ladder(4).run())

    print("\n== Fast path vs reference path (circuit = H + CNOT ladder) ==")
    print(f"{'qubits':>6} {'reference (s)':>14} {'fast (s)':>10} {'same result':>12}")
    for n in range(2, 9):
        qc = ladder(n)
        t0 = time.perf_counter()
        ref = qc.run("reference")
        t_ref = time.perf_counter() - t0
        t0 = time.perf_counter()
        fast = qc.run("fast")
        t_fast = time.perf_counter() - t0
        same = all(abs(a - b) < 1e-9 for a, b in zip(ref.amps, fast.amps))
        print(f"{n:>6} {t_ref:>14.4f} {t_fast:>10.5f} {same!s:>12}")

    print("\n== Fast path alone on bigger circuits ==")
    for n in (12, 14, 16):
        t0 = time.perf_counter()
        state = ladder(n).run("fast")
        dt = time.perf_counter() - t0
        p = state.probabilities()
        print(f"{n} qubits: {dt:.3f}s   P(all 0)={p[0]:.3f}  P(all 1)={p[-1]:.3f}")


if __name__ == "__main__":
    main()
