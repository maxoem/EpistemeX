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
