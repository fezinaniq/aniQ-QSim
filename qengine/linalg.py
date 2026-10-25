"""Hand-written linear algebra on plain Python lists of complex numbers.

No NumPy, no quantum libraries. A Matrix is a list of rows, a Vector is a list.
"""

from __future__ import annotations

Vector = list[complex]
Matrix = list[list[complex]]

TOL = 1e-9  # default tolerance for every "approximately equal" check


def identity(n: int) -> Matrix:
    """n x n identity matrix."""
    return [[1 + 0j if i == j else 0j for j in range(n)] for i in range(n)]


def matvec(M: Matrix, v: Vector) -> Vector:
    """Matrix-vector product M @ v using plain nested loops.

    result[i] = sum_j M[i][j] * v[j]
    """
    cols = len(v)
    for r, row in enumerate(M):
        if len(row) != cols:
            raise ValueError(
                f"shape mismatch: row {r} has {len(row)} entries but vector has {cols}"
            )
    out: Vector = []
    for row in M:
        acc = 0j
        for j in range(cols):
            acc += row[j] * v[j]
        out.append(acc)
    return out


def matmul(A: Matrix, B: Matrix) -> Matrix:
    """Matrix-matrix product A @ B using plain nested loops."""
    inner = len(B)
    if any(len(row) != inner for row in A):
        raise ValueError("shape mismatch: columns of A must equal rows of B")
    cols = len(B[0])
    out: Matrix = []
    for row in A:
        new_row = []
        for j in range(cols):
            acc = 0j
            for k in range(inner):
                acc += row[k] * B[k][j]
            new_row.append(acc)
        out.append(new_row)
    return out


def dagger(M: Matrix) -> Matrix:
    """Conjugate transpose (M-dagger)."""
    rows, cols = len(M), len(M[0])
    return [[M[i][j].conjugate() for i in range(rows)] for j in range(cols)]


def mat_close(A: Matrix, B: Matrix, tol: float = TOL) -> bool:
    """True if A and B have the same shape and all entries differ by < tol."""
    if len(A) != len(B) or any(len(ra) != len(rb) for ra, rb in zip(A, B)):
        return False
    return all(abs(a - b) < tol for ra, rb in zip(A, B) for a, b in zip(ra, rb))


def vec_close(a: Vector, b: Vector, tol: float = TOL) -> bool:
    """True if two vectors have the same length and all entries differ by < tol."""
    return len(a) == len(b) and all(abs(x - y) < tol for x, y in zip(a, b))


def is_unitary(M: Matrix, tol: float = TOL) -> bool:
    """True if M is square and M-dagger @ M == I within tol."""
    n = len(M)
    if any(len(row) != n for row in M):
        return False
    return mat_close(matmul(dagger(M), M), identity(n), tol)


def kron(A: Matrix, B: Matrix) -> Matrix:
    """Kronecker (tensor) product A (x) B.

    If A is (ra x ca) and B is (rb x cb), the result is (ra*rb x ca*cb) and
        result[i*rb + k][j*cb + l] = A[i][j] * B[k][l]
    i.e. every entry of A is replaced by that entry times the whole matrix B.
    """
    ra, ca = len(A), len(A[0])
    rb, cb = len(B), len(B[0])
    out: Matrix = [[0j] * (ca * cb) for _ in range(ra * rb)]
    for i in range(ra):
        for j in range(ca):
            a = A[i][j]
            for k in range(rb):
                for l_ in range(cb):
                    out[i * rb + k][j * cb + l_] = a * B[k][l_]
    return out


def mat_add(A: Matrix, B: Matrix) -> Matrix:
    """Element-wise sum of two matrices of the same shape."""
    if len(A) != len(B) or any(len(ra) != len(rb) for ra, rb in zip(A, B)):
        raise ValueError("shape mismatch in mat_add")
    return [[a + b for a, b in zip(ra, rb)] for ra, rb in zip(A, B)]
