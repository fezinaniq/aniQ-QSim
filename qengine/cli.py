"""Command-line interface: run circuits from the terminal, no Minecraft needed.

    python -m qengine run "h 0; cnot 0 1"
    python -m qengine run --file examples/bell.qc --shots 2000 --seed 1
    python -m qengine demo ghz -n 4
    python -m qengine list
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from .circuit import QuantumCircuit
from .draw import draw_circuit, format_histogram, format_state
from .measure import make_rng, sample
from .parser import CircuitParseError, circuit_to_text, parse_circuit


def bell_circuit(n: int = 2) -> QuantumCircuit:
    return QuantumCircuit(2).h(0).cnot(0, 1)


def ghz_circuit(n: int = 3) -> QuantumCircuit:
    qc = QuantumCircuit(n).h(0)
    for q in range(n - 1):
        qc.cnot(q, q + 1)
    return qc


def uniform_circuit(n: int = 3) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    for q in range(n):
        qc.h(q)
    return qc


def swap_circuit(n: int = 2) -> QuantumCircuit:
    return QuantumCircuit(2).x(0).swap(0, 1)


# name -> (builder, default qubits, description)
DEMOS: dict[str, tuple[Callable[[int], QuantumCircuit], int, str]] = {
    "bell": (bell_circuit, 2, "Bell state: H then CNOT, two entangled qubits"),
    "ghz": (ghz_circuit, 3, "GHZ state on n qubits (default 3): all-0 or all-1"),
    "uniform": (uniform_circuit, 3, "H on every qubit: equal superposition of all outcomes"),
    "swap": (swap_circuit, 2, "X on q0, then SWAP: the 1 moves to q1"),
}


def report(circuit: QuantumCircuit, args: argparse.Namespace) -> None:
    """Print the diagram, the final state, and (optionally) a sampled histogram."""
    ascii_only = args.ascii
    gates = len(circuit)
    print(f"Circuit: {circuit.n_qubits} qubits, {gates} gate{'' if gates == 1 else 's'}")
    print(draw_circuit(circuit, ascii_only))
    state = circuit.run(args.method)
    print(f"\nFinal state: {state!r}")
    print(format_state(state, ascii_only=ascii_only))
    if args.shots > 0:
        seed_note = f", seed {args.seed}" if args.seed is not None else ""
        print(f"\nSampling {args.shots} shots{seed_note}:")
        counts = sample(state, args.shots, make_rng(args.seed))
        print(format_histogram(counts, ascii_only=ascii_only))


def add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--shots", type=int, default=1000, help="measurement shots (0 = skip)")
    p.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible results")
    p.add_argument("--method", choices=["fast", "reference"], default="fast")
    p.add_argument("--ascii", action="store_true", help="plain ASCII output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qengine", description="From-scratch quantum simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a circuit given as text or a file")
    run.add_argument("circuit", nargs="?", help='e.g. "h 0; cnot 0 1"')
    run.add_argument("--file", "-f", help="read the circuit from a text file")
    run.add_argument("-n", "--qubits", type=int, default=None, help="number of qubits")
    add_common(run)

    demo = sub.add_parser("demo", help="run a built-in demo circuit")
    demo.add_argument("name", choices=sorted(DEMOS))
    demo.add_argument("-n", "--qubits", type=int, default=None)
    add_common(demo)

    sub.add_parser("list", help="list built-in demos")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Make Unicode output safe when stdout is redirected on Windows.
    if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)

    if args.command == "list":
        for name in sorted(DEMOS):
            print(f"  {name:<8} {DEMOS[name][2]}")
        return 0

    try:
        if args.command == "demo":
            builder, default_n, _ = DEMOS[args.name]
            circuit = builder(args.qubits or default_n)
            print(f"Demo '{args.name}' as text:\n{circuit_to_text(circuit)}\n")
        else:
            if args.file:
                with open(args.file, encoding="utf-8") as fh:
                    text = fh.read()
            elif args.circuit:
                text = args.circuit
            else:
                print("error: give a circuit string or --file", file=sys.stderr)
                return 2
            circuit = parse_circuit(text, args.qubits)
        report(circuit, args)
    except (CircuitParseError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
