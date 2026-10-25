"""Bell state: two entangled qubits that always agree when measured."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qengine import QuantumCircuit, draw_circuit, format_histogram, format_state

qc = QuantumCircuit(2).h(0).cnot(0, 1)
state = qc.run()

print(draw_circuit(qc))
print(f"\nstate: {state!r}")
print(format_state(state))
print("\n1000 shots:")
print(format_histogram(qc.sample(1000, seed=1)))
