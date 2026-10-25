"""QuantumState: a vector of 2**n complex amplitudes.

Qubit ordering (fixed for the whole project, little-endian):
    qubit 0 is the least significant bit of the basis index.
    Index 5 = 0b101 means q2=1, q1=0, q0=1, printed as |101> (|q2 q1 q0>).
"""

from __future__ import annotations

import math

from .linalg import TOL, Matrix, Vector, matvec

# Phase factors a ket term can carry in the compact "(|0> + |1>)/sqrt(k)" form:
# value -> (sign, "i" marker)
_PHASES = {1: ("+", ""), -1: ("-", ""), 1j: ("+", "i"), -1j: ("-", "i")}


class QuantumState:
    def __init__(self, n_qubits: int, amplitudes: Vector | None = None) -> None:
        if not isinstance(n_qubits, int) or n_qubits < 1:
            raise ValueError("n_qubits must be an integer >= 1")
        self.n_qubits = n_qubits
        size = 2**n_qubits
        if amplitudes is None:
            self.amps: Vector = [0j] * size
            self.amps[0] = 1 + 0j  # |00...0>
        else:
            if len(amplitudes) != size:
                raise ValueError(f"expected {size} amplitudes, got {len(amplitudes)}")
            self.amps = [complex(a) for a in amplitudes]

    # ---- inspection -------------------------------------------------------

    def norm(self) -> float:
        """Euclidean norm sqrt(sum |a|^2). A valid state has norm 1."""
        return math.sqrt(sum(abs(a) ** 2 for a in self.amps))

    def is_normalized(self, tol: float = TOL) -> bool:
        return abs(self.norm() - 1.0) < tol

    def probabilities(self) -> list[float]:
        """Born rule: P(i) = |amps[i]|^2."""
        return [abs(a) ** 2 for a in self.amps]

    def copy(self) -> QuantumState:
        """An independent copy (changing one never changes the other)."""
        return QuantumState(self.n_qubits, list(self.amps))

    # ---- evolution --------------------------------------------------------

    def apply(self, matrix: Matrix) -> QuantumState:
        """Replace the state with matrix @ state. The matrix must be 2**n x 2**n.

        In Step 1 this means a single-qubit gate on a 1-qubit state. From M2 on,
        the same method accepts full N-qubit operators built with Kronecker products.
        """
        if len(matrix) != len(self.amps):
            raise ValueError(
                f"operator is {len(matrix)}x{len(matrix)} but state has "
                f"{len(self.amps)} amplitudes ({self.n_qubits} qubits)"
            )
        self.amps = matvec(matrix, self.amps)
        return self

    # ---- display ----------------------------------------------------------

    def _label(self, index: int) -> str:
        return f"|{index:0{self.n_qubits}b}\u27e9"  # |q(n-1) ... q0>

    def ket(self, tol: float = TOL) -> str:
        """Readable ket, e.g. (|0> + |1>)/sqrt(2). Falls back to explicit coefficients."""
        terms = [(i, a) for i, a in enumerate(self.amps) if abs(a) > tol]
        if not terms:
            return "0"

        compact = self._compact_ket(terms, tol)
        if compact is not None:
            return compact

        parts: list[str] = []
        for pos, (i, a) in enumerate(terms):
            coeff = self._fmt_coeff(a, tol)
            negative = coeff.startswith("-")
            body = f"{coeff.lstrip('-')}{self._label(i)}"
            if pos == 0:
                parts.append(("-" if negative else "") + body)
            else:
                parts.append((" - " if negative else " + ") + body)
        return "".join(parts)

    def _compact_ket(self, terms: list[tuple[int, complex]], tol: float) -> str | None:
        m = abs(terms[0][1])
        if any(abs(abs(a) - m) > tol for _, a in terms):
            return None
        k = round(1 / (m * m))
        if abs(k * m * m - 1) > 1e-6:
            return None

        pieces: list[tuple[str, str]] = []
        for i, a in terms:
            unit = a / m
            key = next((p for p in _PHASES if abs(unit - p) < 1e-6), None)
            if key is None:
                return None
            sign, mark = _PHASES[key]
            pieces.append((sign, f"{mark}{self._label(i)}"))

        text = ("-" if pieces[0][0] == "-" else "") + pieces[0][1]
        for sign, term in pieces[1:]:
            text += f" {sign} {term}"
        if k == 1:
            return text
        root = math.isqrt(k)
        denom = str(root) if root * root == k else f"\u221a{k}"
        return f"({text})/{denom}"

    @staticmethod
    def _fmt_coeff(a: complex, tol: float) -> str:
        if abs(a.imag) < tol:
            return f"{a.real:.4f}"
        if abs(a.real) < tol:
            return f"{a.imag:.4f}i"
        return f"({a.real:.4f}{a.imag:+.4f}i)"

    def __repr__(self) -> str:
        return self.ket()
