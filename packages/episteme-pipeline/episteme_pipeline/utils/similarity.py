"""Mathematical similarity utilities for dense representation vectors.

Provides numerically stable vector normalization and pairwise cosine similarity
matrix computation with zero-norm safeguards to prevent NaN propagation.
"""

from __future__ import annotations

import numpy as np


def l2_normalize(vectors: np.ndarray | list[list[float]] | list[float]) -> np.ndarray:
    """Compute L2-normalized vectors with safe division guarding against zero norms.

    Parameters
    ----------
    vectors : np.ndarray or list of list of float or list of float
        Input vector array of shape (D,) for a single vector or (N, D) for
        a batch of N vectors.

    Returns
    -------
    np.ndarray
        L2-normalized vector array with identical shape and float32 dtype.

    Notes
    -----
    Norms equal to zero are clamped to ``1e-10`` before division to prevent
    zero-division errors and ``NaN`` propagation.
    """
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim == 1:
        norm = np.linalg.norm(arr)
        if norm == 0.0:
            norm = 1e-10
        return arr / norm
    elif arr.ndim == 2:
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0.0] = 1e-10
        return arr / norms
    else:
        raise ValueError(f"Expected 1D or 2D array, got {arr.ndim}D array")


def cosine_similarity_matrix(
    a: np.ndarray | list[list[float]] | list[float],
    b: np.ndarray | list[list[float]] | list[float] | None = None,
) -> np.ndarray:
    """Compute pairwise cosine similarity matrix between vector sets.

    Parameters
    ----------
    a : np.ndarray or list of list of float or list of float
        First set of vectors of shape (N, D) or single vector (D,).
    b : np.ndarray or list of list of float or list of float or None, optional
        Second set of vectors of shape (M, D) or single vector (D,).
        If None, computes self-similarity matrix of shape (N, N).

    Returns
    -------
    np.ndarray
        Cosine similarity matrix of shape (N, M) (or (N, N) if b is None).
        If a is 1D and b is 1D, returns a scalar float. If a is 1D and b is 2D,
        returns shape (M,). If a is 2D and b is 1D, returns shape (N,).
    """
    norm_a = l2_normalize(a)
    if b is None:
        if norm_a.ndim == 1:
            return float(np.dot(norm_a, norm_a))
        return np.dot(norm_a, norm_a.T)

    norm_b = l2_normalize(b)
    if norm_a.ndim == 1 and norm_b.ndim == 1:
        return float(np.dot(norm_a, norm_b))
    elif norm_a.ndim == 1 and norm_b.ndim == 2:
        return np.dot(norm_b, norm_a)
    elif norm_a.ndim == 2 and norm_b.ndim == 1:
        return np.dot(norm_a, norm_b)
    else:
        return np.dot(norm_a, norm_b.T)


def csls_similarity_matrix(
    a: np.ndarray | list[list[float]] | list[float],
    b: np.ndarray | list[list[float]] | list[float] | None = None,
    k_nearest: int = 10,
) -> np.ndarray:
    """Compute Cross-Domain Similarity Local Scaling (CSLS) matrix (Conneau et al., 2018).

    Penalizes hub nodes and compensates for anisotropic embedding geometries via
    local neighborhood scaling:
    :math:`\\text{CSLS}(\\mathbf{u}, \\mathbf{v}) = 2 \\cos(\\mathbf{u}, \\mathbf{v}) - r_T(\\mathbf{u}) - r_T(\\mathbf{v})`
    where :math:`r_T(\\mathbf{u})` is the mean cosine similarity to its :math:`T` nearest neighbors.

    Parameters
    ----------
    a : np.ndarray or list of list of float or list of float
        First set of vectors of shape (N, D).
    b : np.ndarray or list of list of float or list of float or None, optional
        Second set of vectors of shape (M, D). If None, computes symmetric CSLS of shape (N, N).
    k_nearest : int, default 10
        Neighborhood size T for mean nearest-neighbor cosine similarity.

    Returns
    -------
    np.ndarray
        CSLS similarity matrix of shape (N, M) or (N, N).
    """
    sim = cosine_similarity_matrix(a, b)
    if not isinstance(sim, np.ndarray) or sim.ndim != 2:
        return np.asarray(sim, dtype=np.float32)

    n, m = sim.shape

    if b is None or (n == m and np.allclose(sim, sim.T)):
        if n <= 2:
            return np.asarray(sim, dtype=np.float32)
        t = min(max(1, k_nearest), n - 1)
        sim_off = sim.copy()
        np.fill_diagonal(sim_off, -np.inf)
        top_t = np.partition(sim_off, -t, axis=1)[:, -t:]
        r_a = np.mean(top_t, axis=1)
        csls = 2.0 * sim - r_a[:, None] - r_a[None, :]
        np.fill_diagonal(csls, 1.0)
        return np.asarray(csls, dtype=np.float32)
    else:
        if n <= 1 or m <= 1:
            return np.asarray(sim, dtype=np.float32)
        t_a = min(max(1, k_nearest), m)
        t_b = min(max(1, k_nearest), n)
        top_t_a = np.partition(sim, -t_a, axis=1)[:, -t_a:]
        r_a = np.mean(top_t_a, axis=1)
        top_t_b = np.partition(sim.T, -t_b, axis=1)[:, -t_b:]
        r_b = np.mean(top_t_b, axis=1)
        csls = 2.0 * sim - r_a[:, None] - r_b[None, :]
        return np.asarray(csls, dtype=np.float32)


def dynamic_k_effective(
    n: int,
    k_min: int = 2,
    k_max: int = 20,
    gamma: float = 2.0,
) -> int:
    """Compute sub-linear candidate degree bound :math:`K_{\\text{eff}}(N) = \\min(K_{\\max}, \\max(K_{\\min}, \\lceil \\gamma \\sqrt{N} \\rceil))`.

    Mitigates quadratic candidate explosion on small and medium input corpora.

    Parameters
    ----------
    n : int
        Number of entities or argument components in the candidate pool.
    k_min : int, default 2
        Minimum allowed candidate degree.
    k_max : int, default 20
        Maximum allowed candidate degree.
    gamma : float, default 2.0
        Sub-linear scaling factor.

    Returns
    -------
    int
        Bounded candidate degree limit.
    """
    import math

    if n <= 1:
        return 0
    k_val = math.ceil(gamma * math.sqrt(n))
    return min(k_max, max(k_min, k_val))


def z_score_normalize(
    similarity_matrix: np.ndarray,
    symmetric: bool = True,
) -> np.ndarray:
    """Standardize similarity matrix into zero-mean, unit-variance z-scores.

    Parameters
    ----------
    similarity_matrix : np.ndarray
        Pairwise similarity matrix of shape (N, N) or (N, M).
    symmetric : bool, default True
        If True and matrix is square, computes mean and standard deviation over
        upper-triangular non-diagonal entries to prevent self-similarity diagonal skew.

    Returns
    -------
    np.ndarray
        Standardized z-score matrix with identical shape and float32 dtype.
    """
    sim = np.asarray(similarity_matrix, dtype=np.float32)
    if sim.ndim != 2:
        return sim

    if symmetric and sim.shape[0] == sim.shape[1]:
        n = sim.shape[0]
        if n <= 1:
            return np.zeros_like(sim)
        triu_indices = np.triu_indices(n, k=1)
        values = sim[triu_indices]
        mean = float(np.mean(values))
        std = float(np.std(values))
        if std == 0.0:
            std = 1e-10
        z = (sim - mean) / std
        np.fill_diagonal(z, 0.0)
        return np.asarray(z, dtype=np.float32)
    else:
        mean = float(np.mean(sim))
        std = float(np.std(sim))
        if std == 0.0:
            std = 1e-10
        return np.asarray((sim - mean) / std, dtype=np.float32)

