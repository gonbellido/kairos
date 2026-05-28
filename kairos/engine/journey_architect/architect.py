import json
import logging
from typing import Optional, List, Dict, Any
from kairos.engine.journey_engine import JourneyEngine
from kairos.engine.journey_architect.methodology_store import CoachMethodologyStore
from kairos.engine.journey_architect.knowledge import JOURNEY_SCHEMA_DOC, JOURNEY_ARCHITECT_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class JourneyArchitect:
    def __init__(self, llm, journey_engine: JourneyEngine, methodology_store: CoachMethodologyStore):
        self.llm = llm
        self.journey_engine = journey_engine
        self.methodology_store = methodology_store

    async def build_from_prompt(
        self,
        coach_id: str,
        prompt: str,
        existing_journey_id: Optional[str] = None
    ) -> Dict[str, Any]:
        methodology = await self.methodology_store.get_methodology(coach_id)

        full_system_prompt = f"{JOURNEY_ARCHITECT_SYSTEM_PROMPT}\n\n### JOURNEY_SCHEMA_DOC\n{JOURNEY_SCHEMA_DOC}"

        user_context = f"METODOLOGÍA DEL COACH:\n{methodology}\n\nPROMPT DEL USUARIO:\n{prompt}"
        if existing_journey_id:
            existing = await self.journey_engine.get_journey(existing_journey_id)
            if existing:
                user_context += f"\n\nJOURNEY EXISTENTE A MODIFICAR:\n{json.dumps(existing, indent=2)}"

        messages = [
            SystemMessage(content=full_system_prompt),
            HumanMessage(content=user_context)
        ]

        attempt = 0
        max_attempts = 3
        last_error = None

        while attempt < max_attempts:
            try:
                response = await self.llm.ainvoke(messages)
                content = response.content

                # Extract JSON if wrapped in markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                spec = json.loads(content)

                validation = await self.validate_journey_spec(spec.get("journey", {}))
                if validation["valid"]:
                    return spec

                logger.warning("Validation errors (attempt %d): %s", attempt + 1, validation["errors"])
                messages.append(HumanMessage(content=f"La especificación generada tiene errores de validación:\n{json.dumps(validation['errors'], indent=2)}\nPor favor, corrígela y devuelve el JSON completo de nuevo."))
                attempt += 1
                last_error = validation["errors"]
            except json.JSONDecodeError as e:
                logger.error("JSON parse error (attempt %d): %s", attempt + 1, e)
                logger.debug("Raw LLM response: %s", content if 'content' in locals() else 'N/A')
                messages.append(HumanMessage(content=f"Hubo un error de formato JSON: {str(e)}. Asegúrate de devolver un JSON válido según el esquema."))
                attempt += 1
                last_error = str(e)
            except Exception as e:
                logger.error("LLM invocation error (attempt %d): %s", attempt + 1, e)
                messages.append(HumanMessage(content=f"Hubo un error procesando tu respuesta anterior: {str(e)}. Asegúrate de devolver un JSON válido según el esquema."))
                attempt += 1
                last_error = str(e)

        return {
            "journey": {},
            "gaps_detected": [],
            "warnings": [f"Máximo de intentos de corrección alcanzado. Errores pendientes: {last_error}"]
        }

    async def validate_journey_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        if not spec:
            return {"valid": False, "errors": ["Especisificación vacía"]}

        required_journey = ["name", "phases"]
        for field in required_journey:
            if field not in spec:
                errors.append(f"Journey: falta campo requerido '{field}'")

        phases = spec.get("phases", [])
        if not phases:
            errors.append("Journey: debe tener al menos una fase")

        valid_phase_orders = {p.get("order_index") for p in phases if p.get("order_index") is not None}

        for i, phase in enumerate(phases):
            p_name = phase.get("name", f"Fase {i+1}")
            if "name" not in phase:
                errors.append(f"Fase {i+1}: falta 'name'")
            if "order_index" not in phase:
                errors.append(f"Fase {p_name}: falta 'order_index'")

            agents = phase.get("agents", [])
            if not agents:
                errors.append(f"Fase {p_name}: debe tener al menos un agente")

            for j, agent in enumerate(agents):
                a_name = agent.get("name", f"Agente {j+1}")
                if "system_prompt" not in agent:
                    errors.append(f"Agente {a_name} en {p_name}: falta 'system_prompt'")

                # Check tag_mappings consistency
                tag_mappings = agent.get("tag_mappings", {})
                for tag, target in tag_mappings.items():
                    if target != 99 and target not in valid_phase_orders:
                        errors.append(f"Agente {a_name} en {p_name}: tag '{tag}' apunta a orden {target} inexistente")

                # Check collects_fields subset of output_schema keys
                collects = agent.get("collects_fields", [])
                output_schema = agent.get("output_schema", {})
                req_fields = output_schema.get("structured", {}).get("required_fields", {})
                for field in collects:
                    if field not in req_fields:
                        errors.append(f"Agente {a_name} en {p_name}: field '{field}' en collects_fields no está en required_fields del output_schema")

        return {"valid": len(errors) == 0, "errors": errors}

    async def create_journey_from_spec(self, coach_id: str, spec: Dict[str, Any]) -> str:
        validation = await self.validate_journey_spec(spec)
        if not validation["valid"]:
            raise ValueError(f"Invalid journey spec: {validation['errors']}")

        journey = await self.journey_engine.create_journey(
            coach_id=coach_id,
            name=spec["name"],
            description=spec.get("description", ""),
            objective=spec.get("objective", ""),
            profile_type=spec.get("profile_type", "custom"),
            tag_mappings=spec.get("tag_mappings", {})
        )
        journey_id = journey["id"]

        for phase_spec in sorted(spec["phases"], key=lambda x: x["order_index"]):
            phase = await self.journey_engine.add_phase(
                journey_id=journey_id,
                name=phase_spec["name"],
                objective=phase_spec.get("objective", ""),
                order_index=phase_spec["order_index"]
            )
            phase_id = phase["id"]

            for agent_spec in phase_spec.get("agents", []):
                tag_map = agent_spec.get("tag_mappings", {})
                await self.journey_engine.add_agent(
                    journey_id=journey_id,
                    phase_id=phase_id,
                    name=agent_spec["name"],
                    role=agent_spec.get("role", ""),
                    goal=agent_spec.get("goal", ""),
                    system_prompt=agent_spec.get("system_prompt", ""),
                    instructions=agent_spec.get("instructions", ""),
                    collects_fields=agent_spec.get("collects_fields", []),
                    output_schema=agent_spec.get("output_schema", {}),
                    tag_mappings=tag_map,
                    allowed_tags=list(tag_map.keys()),
                )

        return journey_id

    async def explain_journey(self, journey_id: str) -> str:
        journey_data = await self.journey_engine.get_journey(journey_id)
        if not journey_data:
            return "Journey no encontrado."

        prompt = f"Explica este Journey de coaching en lenguaje natural, describiendo sus fases y el rol de sus agentes:\n{json.dumps(journey_data, indent=2)}"
        messages = [
            SystemMessage(content="Eres un experto en coaching. Explica la estructura del proceso de forma clara y motivadora para el coach."),
            HumanMessage(content=prompt)
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    async def suggest_improvements(self, journey_id: str, coach_id: str) -> List[str]:
        journey_data = await self.journey_engine.get_journey(journey_id)
        methodology = await self.methodology_store.get_methodology(coach_id)

        prompt = f"Basado en la metodología del coach y el journey actual, sugiere 3-5 mejoras concretas:\n\nMETODOLOGÍA:\n{methodology}\n\nJOURNEY:\n{json.dumps(journey_data, indent=2)}"
        messages = [
            SystemMessage(content="Eres un senior coach architect. Sugiere mejoras técnicas o metodológicas al journey. Devuelve una lista de strings."),
            HumanMessage(content=prompt)
        ]
        response = await self.llm.ainvoke(messages)
        suggestions = []
        for line in response.content.split("\n"):
            line = line.strip()
            if line.startswith("-") or (line and line[0].isdigit() and "." in line):
                suggestions.append(line.lstrip("- 0123456789."))

        return suggestions[:5]
