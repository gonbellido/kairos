from kairos.core.memory import CaseMemory, RankedCase


class PatternGenerator:
    async def generate_insights(self, cases: list) -> list[dict]:
        if len(cases) < 3:
            return []

        def _outcome(c):
            if hasattr(c, 'case'):
                return getattr(c.case, 'outcome', None)
            return getattr(c, 'outcome', None)

        high_outcome = [c for c in cases if _outcome(c) and _outcome(c) > 0.5]
        low_outcome = [c for c in cases if _outcome(c) and _outcome(c) < 0.3]

        insights = []
        if high_outcome:
            avg = sum(_outcome(c) for c in high_outcome) / len(high_outcome)
            insights.append({
                "type": "success_pattern",
                "title": f"Intervenciones exitosas ({len(high_outcome)} casos)",
                "success_rate": round(avg, 2),
                "sample_size": len(high_outcome),
                "trigger_conditions": self._common_triggers(high_outcome),
            })
        if low_outcome:
            insights.append({
                "type": "risk_pattern",
                "title": f"Intervenciones de riesgo ({len(low_outcome)} casos)",
                "success_rate": round(sum(_outcome(c) for c in low_outcome) / len(low_outcome), 2),
                "sample_size": len(low_outcome),
            })
        return insights

    def _common_triggers(self, cases: list) -> list[str]:
        categories = {}
        for c in cases:
            cat = (c.case.metadata.category if hasattr(c, 'case') else c.metadata.category)
            categories[cat] = categories.get(cat, 0) + 1
        if not categories:
            return []
        top = max(categories, key=categories.get)
        return [f"Categoría recurrente: {top}"]
