"""Quality score computation from behavioral signals (QI-01).

This module computes a float 0-1 quality score for a knowledge item using
weighted behavioral signals. The formula is deterministic and uses only the
Python standard library (math module) — no external dependencies.

Weight breakdown (tunable via Settings in hivemind/config.py):
    40% usefulness    — ratio of helpful outcomes to total outcome votes
    25% popularity    — tanh-saturated retrieval count (saturates at ~200)
    20% freshness     — exponential decay from last access time
    15% contradiction — penalty for items flagged as contradicting others
    +10% bonus        — version_current bonus for items marked as current versions

The weights are configuration-time settings (environment variables via Settings).
Do NOT read weights from deployment_config at compute time — pass them as
parameters or read from Settings at call site.
"""

import math


def compute_quality_score(
    retrieval_count: int,
    helpful_count: int,
    not_helpful_count: int,
    contradiction_rate: float,
    days_since_last_access: float,
    is_version_current: bool,
    staleness_half_life_days: float = 90.0,
    weight_usefulness: float = 0.40,
    weight_popularity: float = 0.25,
    weight_freshness: float = 0.20,
    weight_contradiction: float = 0.15,
) -> float:
    """Compute a quality score for a knowledge item from behavioral signals.

    Parameters
    ----------
    retrieval_count : int
        Total number of times this item was returned in search results.
    helpful_count : int
        Number of times an agent reported this item solved their problem.
    not_helpful_count : int
        Number of times an agent reported this item was not helpful.
    contradiction_rate : float
        Fraction of this item's signals that are contradiction flags (0-1).
        Typically: contradiction_signals / total_signals.
    days_since_last_access : float
        Number of days since this item was last retrieved or voted on.
        Used to compute freshness decay.
    is_version_current : bool
        True if this item is the current (non-superseded) version of its
        knowledge. Adds a small bonus to reward up-to-date items.
    staleness_half_life_days : float
        Half-life for freshness decay in days (default 90.0). After this many
        days without access, freshness drops to 0.5. Tunable via
        Settings.quality_staleness_half_life_days.
    weight_usefulness : float
        Weight for the usefulness component (default 0.40).
    weight_popularity : float
        Weight for the popularity component (default 0.25).
    weight_freshness : float
        Weight for the freshness component (default 0.20).
    weight_contradiction : float
        Weight for the contradiction penalty (default 0.15).

    Returns
    -------
    float
        Quality score in [0.0, 1.0]. Higher is better.

    Notes
    -----
    Formula (research Pattern 3):

        usefulness = helpful / max(helpful + not_helpful, 1)
        popularity = tanh(retrieval_count / 50)      # saturates at ~200 retrievals
        freshness  = exp(-ln(2) * days_since / half_life)
        version_bonus = 0.1 if is_version_current else 0.0

        raw = (weight_usefulness  * usefulness
             + weight_popularity  * popularity
             + weight_freshness   * freshness
             - weight_contradiction * contradiction_rate
             + version_bonus)

        score = clamp(raw, 0.0, 1.0)

    The version_bonus (+0.10) slightly exceeds the maximum possible contribution
    from all weighted components when the item is brand-new (score would be
    0.5 neutral prior). This rewards items that are explicitly marked current.
    """
    # --- Usefulness: ratio of positive outcomes to total outcome votes
    total_outcomes = helpful_count + not_helpful_count
    usefulness = helpful_count / max(total_outcomes, 1)

    # --- Popularity: tanh-saturating retrieval count
    # tanh(1.0) ≈ 0.76 at 50 retrievals; saturates toward 1.0 around 200
    popularity = math.tanh(retrieval_count / 50.0)

    # --- Freshness: exponential decay with configurable half-life
    # freshness = exp(-ln(2) * t / half_life)
    # At t=0: freshness=1.0; at t=half_life: freshness=0.5
    freshness = math.exp(
        -math.log(2.0) * days_since_last_access / max(staleness_half_life_days, 1e-9)
    )

    # --- Version bonus: reward current (non-superseded) versions
    version_bonus = 0.1 if is_version_current else 0.0

    # --- Weighted combination
    raw = (
        weight_usefulness * usefulness
        + weight_popularity * popularity
        + weight_freshness * freshness
        - weight_contradiction * contradiction_rate
        + version_bonus
    )

    # --- Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, raw))
