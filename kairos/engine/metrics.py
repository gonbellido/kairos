import time
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class PipelineMetrics:
    """C2: Métricas del pipeline LangGraph."""

    def __init__(self, max_samples: int = 1000):
        self._node_latencies: dict[str, list[float]] = defaultdict(list)
        self._max_samples = max_samples

        # Hit rate por nivel de memoria
        self._hit_counts: dict[str, int] = defaultdict(int)
        self._total_retrievals = 0

        # Distribución de composite_score
        self._composite_scores: list[float] = []

        # Conteo de requests
        self._total_requests = 0

        # Provider activo
        self._embedding_provider = "unknown"

    def set_embedding_provider(self, provider: str):
        self._embedding_provider = provider

    def record_node_latency(self, node_name: str, latency_ms: float):
        self._node_latencies[node_name].append(latency_ms)
        if len(self._node_latencies[node_name]) > self._max_samples:
            self._node_latencies[node_name] = self._node_latencies[node_name][-self._max_samples:]

    def record_hit(self, level: str, count: int = 1):
        self._hit_counts[level] += count
        self._total_retrievals += 1

    def record_composite_score(self, score: float):
        self._composite_scores.append(score)
        if len(self._composite_scores) > self._max_samples:
            self._composite_scores = self._composite_scores[-self._max_samples:]

    def record_request(self):
        self._total_requests += 1

    def snapshot(self) -> dict[str, Any]:
        node_stats = {}
        for name, lats in self._node_latencies.items():
            if lats:
                lats_sorted = sorted(lats)
                p50_idx = int(len(lats) * 0.5)
                p95_idx = int(len(lats) * 0.95)
                p99_idx = int(len(lats) * 0.99)
                node_stats[name] = {
                    "count": len(lats),
                    "avg_ms": round(sum(lats) / len(lats), 2),
                    "p50_ms": round(lats_sorted[min(p50_idx, len(lats) - 1)], 2),
                    "p95_ms": round(lats_sorted[min(p95_idx, len(lats) - 1)], 2),
                    "p99_ms": round(lats_sorted[min(p99_idx, len(lats) - 1)], 2),
                }

        total_hits = sum(self._hit_counts.values())
        hit_rates = {}
        if total_hits > 0:
            for level, count in self._hit_counts.items():
                hit_rates[f"hit_rate_{level}"] = round(count / total_hits, 3)

        scores = self._composite_scores
        score_stats = {}
        if scores:
            scores_sorted = sorted(scores)
            score_stats = {
                "composite_score_avg": round(sum(scores) / len(scores), 3),
                "composite_score_min": round(scores_sorted[0], 3),
                "composite_score_max": round(scores_sorted[-1], 3),
                "composite_score_p50": round(scores_sorted[len(scores) // 2], 3),
            }

        return {
            "total_requests": self._total_requests,
            "embedding_provider": self._embedding_provider,
            "nodes": node_stats,
            "memory": {
                "total_retrievals": self._total_retrievals,
                **hit_rates,
            },
            "scoring": score_stats,
        }

    def log_summary(self):
        s = self.snapshot()
        logger.info(
            "Metrics: %d requests | embedding=%s | scores avg=%.3f",
            s["total_requests"],
            s["embedding_provider"],
            s.get("scoring", {}).get("composite_score_avg", 0),
        )
        for node, stats in sorted(s.get("nodes", {}).items()):
            logger.info(
                "  node %s: %d calls, avg=%.1fms, p50=%.1fms, p99=%.1fms",
                node, stats["count"], stats["avg_ms"], stats["p50_ms"], stats["p99_ms"],
            )
        mem = s.get("memory", {})
        for k, v in sorted(mem.items()):
            if k.startswith("hit_rate_"):
                logger.info("  %s: %.2f%%", k, v * 100)


_metrics: PipelineMetrics | None = None


def get_metrics() -> PipelineMetrics:
    global _metrics
    if _metrics is None:
        _metrics = PipelineMetrics()
    return _metrics


def reset_metrics():
    global _metrics
    _metrics = PipelineMetrics()
