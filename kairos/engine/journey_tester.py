"""Journey Tester — simulate client conversations, diagnose prompt issues, generate reports."""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete

from kairos.db.models import ClientJourneyModel, ClientSharedProfileModel

logger = logging.getLogger(__name__)
_utcnow = lambda: datetime.now(tz=timezone.utc)


@dataclass
class TestTurn:
    step: int
    agent_id: str
    agent_name: str
    phase_id: str
    phase_name: str
    prompt_sent: str
    user_message: str
    llm_response_raw: str
    llm_response_parsed: dict | None
    json_parse_error: str | None
    collected_fields: dict
    expected_fields: list
    missing_fields: list
    advancement: dict
    duration_ms: float
    error: str | None


@dataclass
class TestSession:
    id: str
    journey_id: str
    coach_id: str
    client_id: str
    status: str = "idle"
    turns: list = field(default_factory=list)
    current_phase_id: str = ""
    current_agent_id: str = ""
    created_at: str = ""


class JourneyTester:
    def __init__(self, session_factory, journey_engine):
        self._sf = session_factory
        self._je = journey_engine
        self._sessions: dict[str, TestSession] = {}

    async def start_test(self, journey_id: str, coach_id: str) -> TestSession:
        journey = await self._je.get_journey(journey_id)
        if not journey:
            raise ValueError("Journey not found")

        client_id = f"test_{uuid4().hex[:10]}"
        cj = await self._je.assign_client(client_id, coach_id, journey_id)
        if not cj:
            raise ValueError("Failed to assign journey")

        session = TestSession(
            id=uuid4().hex[:12],
            journey_id=journey_id,
            coach_id=coach_id,
            client_id=client_id,
            status="running",
            current_phase_id=cj.get("current_phase_id", ""),
            current_agent_id=cj.get("current_agent_id", ""),
            created_at=_utcnow().isoformat(),
        )
        self._sessions[session.id] = session
        return session

    async def send_message(self, session_id: str, message: str) -> TestTurn:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")

        cj = await self._je.get_client_journey(session.client_id)
        if not cj or not cj.get("journey"):
            raise ValueError("Client journey not found")

        journey = cj["journey"]
        agents = journey.get("agents", [])
        phases = journey.get("phases", [])
        agent_data = next(
            (a for a in agents if a["id"] == cj.get("current_agent_id")),
            agents[0] if agents else {},
        )
        phase_data = next(
            (p for p in phases if p["id"] == cj.get("current_phase_id")),
            phases[0] if phases else {},
        )

        t0 = time.time()
        error = None

        try:
            prompt = await self._je.compose_agent_prompt(session.client_id, message)
        except Exception as e:
            prompt = f"ERROR composing prompt: {e}"
            error = f"compose_prompt failed: {e}"

        llm_response = ""
        parse_error = None
        parsed = None

        if not error or prompt:
            try:
                from kairos.paths.fast_path import _call_llm

                collects_fields = agent_data.get("collects_fields", [])
                if isinstance(collects_fields, str):
                    collects_fields = json.loads(collects_fields)
                use_json = bool(collects_fields)
                llm_response = await _call_llm(prompt, message, use_json)
            except Exception as e:
                llm_response = f"LLM ERROR: {e}"
                error = f"LLM call failed: {e}"

        collected = {}
        expected = agent_data.get("collects_fields", []) if agent_data else []
        if isinstance(expected, str):
            expected = json.loads(expected)

        if not error:
            try:
                from kairos.paths.fast_path import _extract_data

                collected = _extract_data(llm_response, expected_fields=expected)
            except Exception:
                pass

        if not error:
            try:
                clean = llm_response.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                parsed = json.loads(clean)
            except (json.JSONDecodeError, ValueError) as e:
                parse_error = str(e)

        advancement = {"advanced": False, "error": None, "phase_completed": False, "message": llm_response}
        if not error:
            try:
                advancement = await self._je.validate_and_advance(
                    session.client_id, llm_response, agent_data
                )
            except Exception as e:
                advancement["error"] = f"validate_and_advance failed: {e}"

        duration_ms = (time.time() - t0) * 1000
        missing = [f for f in expected if f not in collected or not collected.get(f)]

        turn = TestTurn(
            step=len(session.turns) + 1,
            agent_id=agent_data.get("id", ""),
            agent_name=agent_data.get("name", "?"),
            phase_id=phase_data.get("id", ""),
            phase_name=phase_data.get("name", "?"),
            prompt_sent=prompt,
            user_message=message,
            llm_response_raw=llm_response,
            llm_response_parsed=parsed,
            json_parse_error=parse_error,
            collected_fields=collected,
            expected_fields=expected,
            missing_fields=missing,
            advancement=advancement,
            duration_ms=duration_ms,
            error=error,
        )
        session.turns.append(turn)

        cj2 = await self._je.get_client_journey(session.client_id)
        if cj2:
            session.current_phase_id = cj2.get("current_phase_id", "")
            session.current_agent_id = cj2.get("current_agent_id", "")
            if cj2.get("status") == "completed_journey":
                session.status = "completed"

        return turn

    async def skip_agent(self, session_id: str):
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")
        await self._je.advance_client(session.client_id)
        cj = await self._je.get_client_journey(session.client_id)
        if cj:
            session.current_phase_id = cj.get("current_phase_id", "")
            session.current_agent_id = cj.get("current_agent_id", "")
            if cj.get("status") == "completed_journey":
                session.status = "completed"

    async def reset_test(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session:
            try:
                async with self._sf() as s:
                    await s.execute(
                        delete(ClientJourneyModel).where(
                            ClientJourneyModel.client_id == session.client_id
                        )
                    )
                    await s.execute(
                        delete(ClientSharedProfileModel).where(
                            ClientSharedProfileModel.client_id == session.client_id
                        )
                    )
                    await s.commit()
            except Exception:
                pass

    def get_session(self, session_id: str) -> TestSession | None:
        return self._sessions.get(session_id)

    async def get_state(self, session_id: str) -> dict:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")
        journey = await self._je.get_journey(session.journey_id)
        if not journey:
            raise ValueError("Journey not found")

        agents = journey.get("agents", [])
        phases = journey.get("phases", [])

        agent_name = next(
            (a["name"] for a in agents if a["id"] == session.current_agent_id), "?"
        )
        phase_name = next(
            (p["name"] for p in phases if p["id"] == session.current_phase_id), "?"
        )

        return {
            "session_id": session.id,
            "status": session.status,
            "journey_name": journey.get("name", "?"),
            "phases": phases,
            "agents": agents,
            "current_phase_id": session.current_phase_id,
            "current_agent_id": session.current_agent_id,
            "current_phase_name": phase_name,
            "current_agent_name": agent_name,
            "turns_count": len(session.turns),
        }

    async def generate_report(self, session_id: str) -> dict:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")

        journey = await self._je.get_journey(session.journey_id)
        if not journey:
            raise ValueError("Journey not found")

        agent_turns: dict[str, list] = {}
        for t in session.turns:
            agent_turns.setdefault(t.agent_id, []).append(t)

        agent_results = []
        issues = []

        for agent in journey.get("agents", []):
            aid = agent["id"]
            turns = agent_turns.get(aid, [])

            collects_fields = agent.get("collects_fields", [])
            if isinstance(collects_fields, str):
                collects_fields = json.loads(collects_fields)

            all_collected = {}
            json_errors = 0
            for t in turns:
                all_collected.update(t.collected_fields)
                if t.json_parse_error:
                    json_errors += 1

            missing = [
                f for f in collects_fields if f not in all_collected or not all_collected.get(f)
            ]
            had_advancement = any(t.advancement.get("advanced") for t in turns)

            agent_issues = []

            if json_errors > 0:
                agent_issues.append(
                    {
                        "type": "json_parse_error",
                        "occurrences": json_errors,
                        "severity": "high",
                        "suggestion": (
                            "El LLM no devuelve JSON válido. Añade 'Responde ÚNICAMENTE en "
                            "formato JSON' al inicio del system_prompt y asegura que el formato "
                            "de respuesta sea explícito."
                        ),
                    }
                )

            if missing:
                agent_issues.append(
                    {
                        "type": "field_not_collected",
                        "fields": missing,
                        "severity": "high",
                        "suggestion": (
                            f"Campos no recolectados: {', '.join(missing)}. "
                            "El prompt no instruye claramente a pedir estos datos. "
                            "Añade instrucciones específicas para cada campo."
                        ),
                    }
                )

            if collects_fields and not had_advancement and not missing and turns:
                agent_issues.append(
                    {
                        "type": "no_advancement",
                        "severity": "critical",
                        "suggestion": (
                            "Todos los campos recolectados pero no hubo avance. "
                            "Verifica que el agent emita 'phase_completed: true' o "
                            "'suggested_tags' con un tag válido en tag_mappings."
                        ),
                    }
                )

            tag_map = agent.get("tag_mappings", {}) or {}
            if collects_fields and not tag_map:
                agent_issues.append(
                    {
                        "type": "missing_tag_mappings",
                        "severity": "medium",
                        "suggestion": (
                            "El agent no tiene tag_mappings definidos. Sin esto, "
                            "el avance depende solo de phase_completed, que es menos fiable."
                        ),
                    }
                )

            prompt = agent.get("system_prompt", "")
            if prompt and "json" not in prompt.lower() and collects_fields:
                agent_issues.append(
                    {
                        "type": "missing_json_instruction",
                        "severity": "medium",
                        "suggestion": (
                            "El system_prompt no menciona formato JSON. "
                            "El LLM podría no devolver datos estructurados."
                        ),
                    }
                )

            # Check placeholder issues
            import re

            placeholders = re.findall(r"\{\{(\w+)\}\}", prompt)
            unresolved = [
                p
                for p in placeholders
                if p
                not in (
                    "step_title",
                    "step_objective",
                    "agent_name",
                    "journey_name",
                    "coach_name",
                    "client_name",
                )
                and not p.startswith("collected.")
            ]
            if unresolved:
                agent_issues.append(
                    {
                        "type": "unknown_placeholders",
                        "fields": unresolved,
                        "severity": "low",
                        "suggestion": (
                            f"Placeholders no reconocidos: {', '.join(unresolved)}. "
                            "Usa solo {{step_title}}, {{step_objective}}, {{agent_name}}, "
                            "{{journey_name}}, {{coach_name}}, {{client_name}}, "
                            "o {{collected.campo}}."
                        ),
                    }
                )

            agent_results.append(
                {
                    "agent_id": aid,
                    "agent_name": agent["name"],
                    "phase_id": agent.get("phase_id", ""),
                    "phase_name": next(
                        (p["name"] for p in journey.get("phases", []) if p["id"] == agent.get("phase_id")),
                        "?",
                    ),
                    "turns": len(turns),
                    "fields_expected": collects_fields,
                    "fields_collected": list(all_collected.keys()),
                    "fields_missing": missing,
                    "json_parse_success": json_errors == 0 or len(turns) == 0,
                    "had_advancement": had_advancement,
                    "issues": agent_issues,
                }
            )
            issues.extend(agent_issues)

        total_agents = len(agent_results)
        agents_with_issues = sum(1 for a in agent_results if a["issues"])
        passed = total_agents - agents_with_issues

        critical = sum(1 for i in issues if i["severity"] == "critical")
        high = sum(1 for i in issues if i["severity"] == "high")
        medium = sum(1 for i in issues if i["severity"] == "medium")
        low = sum(1 for i in issues if i["severity"] == "low")

        score = round((passed / max(total_agents, 1)) * 100)

        return {
            "session_id": session_id,
            "journey_id": session.journey_id,
            "journey_name": journey.get("name", "?"),
            "journey_version": journey.get("version", 1),
            "status": session.status,
            "total_turns": len(session.turns),
            "phases_tested": len({t.phase_id for t in session.turns}),
            "agents_tested": len({t.agent_id for t in session.turns}),
            "agent_results": agent_results,
            "issues": issues,
            "summary": {
                "total_agents": total_agents,
                "agents_passed": passed,
                "agents_with_issues": agents_with_issues,
                "critical_issues": critical,
                "high_issues": high,
                "medium_issues": medium,
                "low_issues": low,
                "score": score,
            },
        }
