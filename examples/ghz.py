"""GHZ state: n qubits that are all 0 or all 1, never mixed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qengine import QuantumCircuit, draw_circuit, format_histogram

N = 5
qc = QuantumCircuit(N).h(0)
for q in range(N - 1):
    qc.cnot(q, q + 1)

print(draw_circuit(qc))
print(f"\nstate: {qc.run()!r}")
print("\n1000 shots:")
print(format_histogram(qc.sample(1000, seed=3)))
