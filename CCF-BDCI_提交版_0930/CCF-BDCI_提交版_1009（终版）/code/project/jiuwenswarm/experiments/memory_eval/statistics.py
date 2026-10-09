"""Paired inference over memory episodes; repeated generations stay clustered."""

from __future__ import annotations

import numpy as np


def cluster_interval(values, *, strata=None, resamples=10000, seed=20261007):
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("Cluster values must be finite and nonempty")
    if strata is None:
        strata = ["all"] * len(values)
    if len(strata) != len(values):
        raise ValueError("Each memory cluster needs a stratum")
    rng = np.random.default_rng(seed)
    total = np.zeros(resamples)
    for label in sorted(set(strata)):
        subset = values[[i for i, stratum in enumerate(strata) if stratum == label]]
        draws = rng.integers(0, len(subset), size=(resamples, len(subset)))
        total += subset[draws].sum(axis=1)
    sample_means = total / len(values)
    low, high = np.quantile(sample_means, [0.025, 0.975])
    return {"estimate": float(values.mean()), "low": float(low), "high": float(high),
            "clusters": len(values), "confidence": 0.95, "resamples": resamples,
            "seed": seed, "method": "stratified paired memory-cluster bootstrap"}


def paired_permutation(differences, *, resamples=10000, seed=20261007):
    diffs = np.asarray(differences, dtype=float)
    if not len(diffs) or not np.isfinite(diffs).all():
        raise ValueError("Paired cluster differences must be finite and nonempty")
    observed = abs(diffs.sum())
    if observed == 0:
        return 1.0
    nonzero = diffs[diffs != 0]
    rng = np.random.default_rng(seed)
    signs = rng.integers(0, 2, size=(resamples, len(nonzero))) * 2 - 1
    count = int(np.count_nonzero(abs(signs @ nonzero) >= observed - 1e-12))
    return (count + 1) / (resamples + 1)


def holm_adjust(pvalues: dict[str, float]) -> dict[str, float]:
    adjusted = {}
    running = 0.0
    ordered = sorted(pvalues, key=pvalues.get)
    for rank, key in enumerate(ordered):
        running = max(running, min(1.0, pvalues[key] * (len(ordered) - rank)))
        adjusted[key] = running
    return adjusted
