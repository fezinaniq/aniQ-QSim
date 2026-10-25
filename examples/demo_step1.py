"""Step 1 demo: apply H to |0> in the terminal and verify the result."""

import math

from qengine import H, QuantumState, X, is_unitary

TOL = 1e-9


def main() -> None:
    print("== Gate sanity ==")
    print(f"H unitary: {is_unitary(H)}")
    print(f"X unitary: {is_unitary(X)}")

    print("\n== H|0> ==")
    state = QuantumState(1)
    print(f"before : {state!r}   amps={state.amps}")
    state.apply(H)
    print(f"after  : {state!r}   amps={[round(a.real, 6) for a in state.amps]}")
    print(f"probs  : {state.probabilities()}")
    print(f"norm   : {state.norm():.12f}")

    expected = 1 / math.sqrt(2)
    assert all(abs(a - expected) < TOL for a in state.amps), "H|0> is wrong"
    assert abs(state.norm() - 1) < TOL, "state is not normalized"
    print("\nOK: H|0> = (|0> + |1>)/sqrt(2), norm = 1")

    print("\n== X|0>, then H ==")
    s2 = QuantumState(1).apply(X)
    print(f"X|0>   : {s2!r}")
    print(f"H X|0> : {s2.apply(H)!r}")


if __name__ == "__main__":
    main()
