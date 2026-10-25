"""Single-qubit gate matrices, written out by hand as nested lists of complex numbers."""

from __future__ import annotations

import cmath
import math

from .linalg import Matrix

_R = 1 / math.sqrt(2)

# Hadamard: |0> -> (|0>+|1>)/sqrt(2), |1> -> (|0>-|1>)/sqrt(2)
H: Matrix = [
    [complex(_R, 0), complex(_R, 0)],
    [complex(_R, 0), complex(-_R, 0)],
]

# Pauli-X (quantum NOT): swaps |0> and |1>
X: Matrix = [
    [0j, 1 + 0j],
    [1 + 0j, 0j],
]

# Pauli-Y: X and Z combined (Y = i X Z)
Y: Matrix = [
    [0j, -1j],
    [1j, 0j],
]

# Pauli-Z: leaves |0> alone, flips the sign of |1> (a "phase flip")
Z: Matrix = [
    [1 + 0j, 0j],
    [0j, -1 + 0j],
]

# S gate: quarter turn of phase on |1>. S*S = Z
S: Matrix = [
    [1 + 0j, 0j],
    [0j, 1j],
]

# T gate: eighth turn of phase on |1>. T*T = S
T: Matrix = [
    [1 + 0j, 0j],
    [0j, cmath.exp(1j * math.pi / 4)],
]

# ---- two-qubit gates (4x4, basis order |q1 q0> = 00, 01, 10, 11) --------------
# CNOT here has control = q1 (left bit) and target = q0 (right bit): it flips the
# target when the control is 1, so |10> <-> |11> and |00>, |01> are untouched.
# For any other control/target placement use operators.cnot_operator.
CNOT: Matrix = [
    [1 + 0j, 0j, 0j, 0j],
    [0j, 1 + 0j, 0j, 0j],
    [0j, 0j, 0j, 1 + 0j],
    [0j, 0j, 1 + 0j, 0j],
]

# SWAP exchanges the two qubits: |01> <-> |10>. Symmetric, so no control/target.
SWAP: Matrix = [
    [1 + 0j, 0j, 0j, 0j],
    [0j, 0j, 1 + 0j, 0j],
    [0j, 1 + 0j, 0j, 0j],
    [0j, 0j, 0j, 1 + 0j],
]
