from jinja2 import Environment, BaseLoader

from kairos.core.profile import Profile
from kairos.core.memory import RankedCase, PatternMemory
from kairos.core.impronta import Impronta
from kairos.core.state import StateClassification


class PromptEngine:
    def __init__(self):
        self._env = Environment(loader=BaseLoader(), autoescape=False)

    async def build(
        self,
        profile: Profile,
        impronta: Impronta,
        impronta_rules: list[str] | None = None,
        state_classification: StateClassification | None = None,
        cases: list[RankedCase] | None = None,
        patterns: list[PatternMemory] | None = None,
        insights: list[dict] | None = None,
        knowledge_docs: list[dict] | None = None,
        message: str = "",
        context: dict | None = None,
    ) -> str:
        system = self._render_system(profile, impronta)
        rules_block = self._format_rules(impronta_rules or [])
        state_info = self._format_state(state_classification)
        cases_block = self._format_cases(cases or [])
        patterns_block = self._format_patterns(patterns or [])
        insights_block = self._format_insights(insights or [])
        knowledge_block = self._format_knowledge(knowledge_docs or [])
        user_block = self._format_user(message, context or {})

        blocks = [system]
        if rules_block: blocks.append(rules_block)
        if state_info: blocks.append(state_info)
        if cases_block: blocks.append(cases_block)
        if patterns_block: blocks.append(patterns_block)
        if insights_block: blocks.append(insights_block)
        if knowledge_block: blocks.append(knowledge_block)
        blocks.append(user_block)
        return "\n\n".join(blocks)

    def _render_system(self, profile: Profile, impronta: Impronta) -> str:
        return self._env.from_string(profile.system_prompt_template).render(
            profile_name=profile.name,
            description=profile.description,
            **impronta.model_dump(),
        )

    def _format_state(self, state: StateClassification | None) -> str:
        if not state:
            return ""
        return (
            "## State Classification\n"
            f"- Risk: {state.get('riesgo', 'N/A')}\n"
            f"- Emotion: {state.get('emocion', 'N/A')}\n"
            f"- Urgency: {state.get('urgencia', 'N/A')}\n"
            f"- Intention: {state.get('intencion', 'N/A')}\n"
            f"- Tone: {state.get('tono', 'N/A')}\n"
        )

    def _format_cases(self, cases: list[RankedCase]) -> str:
        if not cases:
            return ""
        lines = ["## Relevant Past Cases (weighted by experience)"]
        for i, c in enumerate(cases[:5], 1):
            lines.append(
                f"\n[Case {i} - Score: {c.composite_score:.2f}]"
                f"\nContext: {c.case.context[:200]}"
                f"\nIntervention: {c.case.intervention[:400]}"
                f"\nOutcome: {c.case.outcome or 'unknown'}"
                f"\n---"
            )
        return "\n".join(lines)

    def _format_patterns(self, patterns: list[PatternMemory]) -> str:
        if not patterns:
            return ""
        lines = ["## Identified Patterns"]
        for p in patterns[:3]:
            lines.append(f"- {p.title} (signal: {p.statistical_signal:.2f}, freq: {p.frequency})")
        return "\n".join(lines)

    def _format_knowledge(self, docs: list[dict]) -> str:
        if not docs:
            return ""
        lines = ["## Relevant Knowledge"]
        for d in docs[:3]:
            lines.append(f"- {d['content'][:300]}")
        return "\n".join(lines)

    def _format_rules(self, rules: list[str]) -> str:
        if not rules:
            return ""
        return "## Behavioral Guidelines (from Impronta)\n" + "\n".join(f"- {r}" for r in rules)

    def _format_insights(self, insights: list[dict]) -> str:
        if not insights:
            return ""
        lines = ["## Detected Patterns & Insights"]
        for ins in insights[:3]:
            lines.append(f"- {ins.get('title', '')} (success rate: {ins.get('success_rate', 'N/A')}, n={ins.get('sample_size', 0)})")
        return "\n".join(lines)

    def _format_user(self, message: str, context: dict) -> str:
        parts = [f"## User Message\n\n{message}"]
        ctx = {k: v for k, v in context.items() if k not in ("impronta_overrides", "memory_filters")}
        if ctx:
            parts.insert(0, "## Context\n" + "\n".join(f"{k}: {v}" for k, v in ctx.items()))
        return "\n\n".join(parts)
