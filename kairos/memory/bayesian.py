"""D5: Bayesian scoring with Thompson sampling for optimal case selection."""

import math
from typing import Any

SCALE = 10.0  # precision scale for Beta parameters


class BayesianScorer:
    """Thompson sampling scorer for ranking cases based on reward history."""

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self._prior_a = prior_alpha
        self._prior_b = prior_beta

    def sample(self, case_id: str, history: dict[str, Any]) -> float:
        """Sample a score from Beta(alpha + successes, beta + failures).

        history: dict with keys 'successes' (int) and 'total_uses' (int)
        """
        successes = history.get("successes", 0)
        total = history.get("total_uses", 0)
        failures = max(0, total - successes)

        # Scale to precision SCALE
        alpha = self._prior_a + successes * SCALE
        beta = self._prior_b + failures * SCALE

        # Simple approximate sampling via mode + jitter
        # For production use, replace with proper Beta sampling (numpy, scipy, or random.betavariate)
        mode = (alpha - 1) / (alpha + beta - 2) if alpha > 1 and beta > 1 else 0.5
        # Add small random jitter proportional to variance
        import random
        variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
        jitter = random.gauss(0, math.sqrt(max(variance, 0.001)))
        return max(0.0, min(1.0, mode + jitter))

    def update_posterior(self, case_id: str, history: dict[str, Any], reward: float) -> dict[str, Any]:
        """Increment success count based on reward threshold."""
        history = history.copy()
        history["total_uses"] = history.get("total_uses", 0) + 1
        if reward > 0.6:
            history["successes"] = history.get("successes", 0) + 1
        return history


# Singleton
_bayesian_scorer = BayesianScorer()


def get_bayesian_scorer() -> BayesianScorer:
    return _bayesian_scorer
