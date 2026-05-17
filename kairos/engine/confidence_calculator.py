from kairos.core.memory import RankedCase


class ConfidenceCalculator:
    @staticmethod
    def calculate(
        ranked_cases: list[RankedCase],
        evaluation_score: float,
        impronta_adherence: float,
        case_count: int,
    ) -> tuple[float, dict]:
        score_avg = 0.0
        if ranked_cases:
            score_avg = sum(c.composite_score for c in ranked_cases) / len(ranked_cases)

        consistency = min(1.0, case_count / 10.0)
        coverage = score_avg

        confidence = (
            0.3 * evaluation_score +
            0.3 * impronta_adherence +
            0.2 * consistency +
            0.2 * coverage
        )
        details = {
            "score_avg": round(score_avg, 3),
            "consistency": round(consistency, 3),
            "coverage": round(coverage, 3),
            "raw_evaluation": round(evaluation_score, 3),
            "impronta_adherence": round(impronta_adherence, 3),
        }
        return round(max(0.0, min(1.0, confidence)), 3), details
