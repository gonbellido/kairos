"""F2: Objective evaluator — decides whether a phase/agent objective is met.

Modes:
- deterministic: all of the agent's ``collects_fields`` are present and non-empty.
- llm: an injected async judge assesses the agent goal against the transcript.
- hybrid: deterministic first; fall back to the llm judge only when ambiguous.

Decoupled from any concrete LLM client: pass an async callable
``llm_judge(prompt: str) -> str`` (returning JSON) to enable llm/hybrid modes.
The result is meant to be stored in ``client_journeys.objective_state`` and read
by the coordinator (F3) to drive transitions.
"""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
_utcnow = lambda: datetime.now(tz=timezone.utc)

_EMPTY = (None, "", [], {})


def _as_list(value) -> list:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return []
    return value if isinstance(value, list) else []


def _missing_fields(collects_fields: list, collected: dict) -> list:
    collected = collected or {}
    return [f for f in collects_fields if f not in collected or collected.get(f) in _EMPTY]


class ObjectiveEvaluator:
    def __init__(self, llm_judge=None):
        # llm_judge: optional async callable (prompt: str) -> str returning JSON
        self._llm_judge = llm_judge

    def _infer_mode(self, agent: dict) -> str:
        cfg = agent.get("objective_eval") or {}
        mode = cfg.get("mode") if isinstance(cfg, dict) else None
        if mode in ("deterministic", "llm", "hybrid"):
            return mode
        return "deterministic" if _as_list(agent.get("collects_fields")) else "llm"

    async def evaluate(self, agent: dict, collected: dict, transcript: str = "") -> dict:
        mode = self._infer_mode(agent)
        collects = _as_list(agent.get("collects_fields"))

        if collects:
            missing = _missing_fields(collects, collected)
            det = {"met": not missing, "confidence": 1.0, "missing": missing}
        else:
            det = {"met": False, "confidence": 0.0, "missing": []}

        if mode == "deterministic":
            return self._stamp({**det, "mode": "deterministic"})

        if mode == "hybrid" and collects and det["met"]:
            return self._stamp({**det, "mode": "hybrid"})

        if self._llm_judge is None:
            return self._stamp({**det, "mode": "deterministic_fallback"})

        llm = await self._llm_evaluate(agent, collected, transcript)
        if llm is None:
            return self._stamp({**det, "mode": "deterministic_fallback"})
        return self._stamp({**llm, "mode": mode})

    async def _llm_evaluate(self, agent: dict, collected: dict, transcript: str):
        goal = agent.get("goal") or agent.get("role") or agent.get("name") or ""
        prompt = (
            "Eres un evaluador objetivo. Decide si el OBJETIVO del agente se cumplió "
            "según la conversación y los datos recolectados.\n\n"
            f"OBJETIVO: {goal}\n\n"
            f"DATOS RECOLECTADOS: {json.dumps(collected or {}, ensure_ascii=False)[:1500]}\n\n"
            f"CONVERSACIÓN RECIENTE:\n{(transcript or '')[:2000]}\n\n"
            'Responde SOLO con JSON: {"met": bool, "confidence": 0.0-1.0, "missing": ["..."]}'
        )
        try:
            raw = await self._llm_judge(prompt)
            clean = (raw or "").strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(clean)
            missing = data.get("missing", [])
            return {
                "met": bool(data.get("met", False)),
                "confidence": float(data.get("confidence", 0.0)),
                "missing": missing if isinstance(missing, list) else [],
            }
        except Exception as e:
            logger.debug("objective llm judge failed: %s", e)
            return None

    def _stamp(self, d: dict) -> dict:
        d["ts"] = _utcnow().isoformat()
        return d
