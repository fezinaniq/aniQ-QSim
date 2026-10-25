"""M2 demo: Kronecker products and single-qubit gates on multi-qubit states."""

from qengine import H, QuantumState, X, kron, single_qubit_operator
from qengine.linalg import identity


def show(m):
    for row in m:
        print("  [" + "  ".join(f"{x.real:5.2f}" for x in row) + " ]")


def main() -> None:
    print("== Kronecker product: I (x) X (X acting on qubit 0 of 2) ==")
    show(kron(identity(2), X))

    print("\n== X on qubit 0 vs qubit 1 (3 qubits, little-endian) ==")
    for t in range(3):
        s = QuantumState(3).apply(single_qubit_operator(X, t, 3))
        print(f"X on q{t}: {s!r}   (basis index {s.amps.index(1)})")

    print("\n== H on one qubit of two ==")
    for t in range(2):
        s = QuantumState(2).apply(single_qubit_operator(H, t, 2))
        print(f"H on q{t}: {s!r}")

    print("\n== H on every qubit of 3 -> uniform superposition ==")
    s = QuantumState(3)
    for t in range(3):
        s.apply(single_qubit_operator(H, t, 3))
    print(s)
    print("probabilities:", [round(p, 4) for p in s.probabilities()])


if __name__ == "__main__":
    main()
