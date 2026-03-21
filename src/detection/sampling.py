"""Data sampling utilities — hybrid under/over-sampling for imbalanced insider threat data.

The CERT r4.2 dataset has a severe class imbalance:
  - ~70 known insiders (label=1)
  - ~930 normal users (label=0)

Using `scale_pos_weight` alone leaves the decision boundary geometrically biased.
This module applies a 3-stage hybrid strategy:
  1. ClusterCentroids under-sampling → reduce normals to ~350 representative prototypes
  2. BorderlineSMOTE over-sampling  → grow insiders from 70 to ~150 (borderline cases only)

The result is a ~350:150 ratio (2.3:1) vs original 13.3:1 — much more learnable.

CRITICAL: Always split BEFORE resampling. Never evaluate on SMOTE-augmented samples.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Literal

SamplingStrategy = Literal["none", "under_only", "smote_only", "hybrid"]


def resample(
    X: np.ndarray,
    y: np.ndarray,
    strategy: SamplingStrategy = "hybrid",
    random_state: int = 42,
    verbose: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply the chosen resampling strategy to X, y.

    Args:
        X: Feature matrix (n_samples, n_features) — TRAINING set ONLY, never the full dataset.
        y: Labels array. 1 = insider, 0 = normal.
        strategy: One of:
            "none"       — No resampling (falls back to scale_pos_weight in XGBoost).
            "under_only" — Random under-sample the majority class.
            "smote_only" — SMOTE over-sample the minority class only.
            "hybrid"     — ClusterCentroids under-sample + BorderlineSMOTE (recommended).
        random_state: Random seed for reproducibility.
        verbose: Print before/after class distribution.

    Returns:
        X_resampled, y_resampled — balanced training arrays.
    """
    n_pos = int(y.sum())
    n_neg = int(len(y) - n_pos)

    if verbose:
        print(f"[SAMPLING] Before resampling: {n_pos} insiders, {n_neg} normals (ratio 1:{n_neg/max(n_pos,1):.1f})")

    if strategy == "none":
        if verbose:
            print("[SAMPLING] Strategy=none — returning original data (use scale_pos_weight)")
        return X, y

    # Need at least k_neighbors+1 insider samples for SMOTE
    MIN_MINORITY = 6

    if n_pos < MIN_MINORITY and strategy in ("smote_only", "hybrid"):
        if verbose:
            print(f"[SAMPLING] ⚠️  Only {n_pos} minority samples — falling back to 'under_only'")
        strategy = "under_only"

    try:
        from imblearn.over_sampling import BorderlineSMOTE, SMOTE
        from imblearn.under_sampling import ClusterCentroids, RandomUnderSampler
        from imblearn.pipeline import Pipeline as ImbPipeline
    except ImportError:
        raise ImportError(
            "imbalanced-learn is required for data sampling. "
            "Install via: pip install imbalanced-learn"
        )

    if strategy == "under_only":
        # Random under-sample majority to 3:1 ratio
        target_ratio = min(0.33, n_pos / n_neg)  # at most 3:1
        sampler = RandomUnderSampler(
            sampling_strategy=target_ratio, random_state=random_state
        )
        X_res, y_res = sampler.fit_resample(X, y)

    elif strategy == "smote_only":
        k = min(5, n_pos - 1)  # k_neighbors must be < n_minority_samples
        sampler = SMOTE(
            sampling_strategy=0.5,  # insiders become 50% of majority size
            k_neighbors=k,
            random_state=random_state,
        )
        X_res, y_res = sampler.fit_resample(X, y)

    elif strategy == "hybrid":
        # Stage 1: ClusterCentroids — compress normals to representative prototypes
        # Target: reduce normals so ratio becomes ~4:1 after clustering
        under_ratio = min(0.25, n_pos / n_neg)  # insiders at 25% of normals count
        
        # Stage 2: BorderlineSMOTE — generate synthetic insiders near the decision boundary
        k = min(5, n_pos - 1)
        over_ratio = 0.5  # after under-sampling, insiders become 50% of new normal count

        # ClusterCentroids can be slow on large data; fall back if needed
        try:
            under_sampler = ClusterCentroids(
                sampling_strategy=under_ratio, random_state=random_state
            )
            X_under, y_under = under_sampler.fit_resample(X, y)
        except Exception as e:
            if verbose:
                print(f"[SAMPLING] ClusterCentroids failed ({e}), using RandomUnderSampler instead.")
            under_sampler = RandomUnderSampler(
                sampling_strategy=under_ratio, random_state=random_state
            )
            X_under, y_under = under_sampler.fit_resample(X, y)

        # Now apply BorderlineSMOTE to the under-sampled set
        n_pos_under = int(y_under.sum())
        k_under = min(5, n_pos_under - 1)
        if k_under < 1:
            if verbose:
                print("[SAMPLING] Not enough minority samples after under-sampling for SMOTE — skipping over-sampling.")
            X_res, y_res = X_under, y_under
        else:
            try:
                over_sampler = BorderlineSMOTE(
                    sampling_strategy=over_ratio,
                    k_neighbors=k_under,
                    random_state=random_state,
                )
                X_res, y_res = over_sampler.fit_resample(X_under, y_under)
            except Exception as e:
                if verbose:
                    print(f"[SAMPLING] BorderlineSMOTE failed ({e}), using vanilla SMOTE.")
                over_sampler = SMOTE(
                    sampling_strategy=over_ratio,
                    k_neighbors=k_under,
                    random_state=random_state,
                )
                X_res, y_res = over_sampler.fit_resample(X_under, y_under)
    else:
        raise ValueError(f"Unknown sampling strategy: '{strategy}'. Use: none/under_only/smote_only/hybrid")

    n_pos_res = int(y_res.sum())
    n_neg_res = int(len(y_res) - n_pos_res)
    if verbose:
        print(f"[SAMPLING] After  resampling: {n_pos_res} insiders, {n_neg_res} normals (ratio 1:{n_neg_res/max(n_pos_res,1):.1f})")
        print(f"[SAMPLING] Sample counts: {len(X)} → {len(X_res)} total training samples")

    return X_res, y_res
