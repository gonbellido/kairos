"""Fase I: Journey Engine — compose prompts, track progress, route transitions."""

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kairos.db.models import (
    ClientJourneyModel,
    ClientSharedProfileModel,
    JourneyAgentModel,
    JourneyEventModel,
    JourneyModel,
    JourneyPhaseModel,
    JourneyTransitionModel,
)

_utcnow = lambda: datetime.now(tz=timezone.utc)
logger = logging.getLogger(__name__)


# ── Template variables always available in agent prompts (used by the journeys API) ──

COACH_VARIABLES = {
    "directividad": "Nivel de directividad (0.0-1.0)",
    "emocionalidad": "Nivel de empatía (0.0-1.0)",
    "ritmo": "Velocidad del proceso (0.0-1.0)",
    "coach_persona": "Descripción de personalidad del coach",
}

JOURNEY_VARIABLES = {
    "journey_name": "Nombre del journey",
    "phase_name": "Nombre de esta fase",
    "phase_order": "Número de fase actual",
    "total_phases": "Total de fases",
    "progress_pct": "Porcentaje de avance (0-100)",
    "pending_fields": "Campos aún no recolectados",
}


def _humanize_delta(delta) -> str:
    """Return human-readable time delta in Spanish."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 3600:
        mins = total_seconds // 60
        return f"{mins} minuto{'s' if mins != 1 else ''}"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours} hora{'s' if hours != 1 else ''}"
    elif total_seconds < 7 * 86400:
        days = total_seconds // 86400
        return f"{days} día{'s' if days != 1 else ''}"
    elif total_seconds < 30 * 86400:
        weeks = total_seconds // (7 * 86400)
        return f"{weeks} semana{'s' if weeks != 1 else ''}"
    else:
        months = total_seconds // (30 * 86400)
        return f"{months} mes{'es' if months != 1 else ''}"

# Default journey templates (seeded on first run)
DEFAULT_JOURNEYS = {
    "coaching": {
        "name": "Coaching Personal",
        "description": "Proceso de acompañamiento para desarrollo personal y profesional",
        "objective": "Alcanzar claridad, definir objetivos y ejecutar un plan de acción",
        "profile_type": "coaching",
        "output_schema": '{"message":"str","structured":{"phase_completed":bool,"required_fields":{}},"next_step_tag":"str|null","escalation_flag":bool}',
        "phases": [
            {"name": "Diagnóstico", "objective": "Entender situación actual, objetivo principal y bloqueos",
             "agents": [{"name": "Explorador", "role": "Diagnóstico inicial", "goal": "Identificar situación, motivación y primer bloqueo",
                         "system_prompt": "Eres un coach ontológico en fase de Diagnóstico. Tu objetivo es entender la situación actual del cliente, su motivación y su principal bloqueo.\n\nDebes obtener: nombre, contexto actual, qué quiere trabajar y qué le frena.\n\nResponde SIEMPRE en formato JSON:\n{\"message\": \"tu respuesta empática al cliente\", \"structured\": {\"phase_completed\": false, \"required_fields\": {\"client_name\": \"\", \"context\": \"\", \"goal\": \"\", \"blocker\": \"\"}}, \"next_step_tag\": null, \"escalation_flag\": false}\n\nCuando tengas TODOS los campos con valores reales, marca phase_completed: true y next_step_tag: \"to_clarity\".\nSi el cliente muestra crisis o confusión extrema, marca escalation_flag: true.",
                         "instructions": "Pregunta una cosa a la vez. No llenes campos que el cliente no ha dicho. Sé cálido."}]},
            {"name": "Claridad", "objective": "Transformar el deseo en un objetivo concreto y medible",
             "agents": [{"name": "Clarificador", "role": "Enfoque y precisión", "goal": "Convertir ideas difusas en objetivo SMART",
                         "system_prompt": "Eres un coach ontológico en fase de Claridad. El cliente ya compartió su situación. Ahora debes ayudarle a definir un objetivo concreto y medible.\n\nUsa los datos previos de la ficha del cliente para no repetir preguntas.\n\nResponde SIEMPRE en formato JSON:\n{\"message\": \"tu respuesta\", \"structured\": {\"phase_completed\": false, \"required_fields\": {\"smart_goal\": \"\", \"success_criteria\": \"\", \"timeline\": \"\"}}, \"next_step_tag\": null, \"escalation_flag\": false}\n\nCuando el objetivo esté claramente definido, marca phase_completed: true y next_step_tag: \"to_plan\".",
                         "instructions": "No repitas preguntas ya respondidas. Usa la ficha común como memoria. Sé concreto."}]},
            {"name": "Plan de Acción", "objective": "Definir pasos concretos, responsables y plazos",
             "agents": [{"name": "Planificador", "role": "Estructura y compromiso", "goal": "Crear plan de acción con tareas específicas",
                         "system_prompt": "Eres un coach en fase de Plan de Acción. El cliente tiene un objetivo claro. Ahora deben definir pasos concretos.\n\nResponde SIEMPRE en formato JSON:\n{\"message\": \"tu respuesta\", \"structured\": {\"phase_completed\": false, \"required_fields\": {\"tasks\": [{\"title\":\"\",\"deadline\":\"\"}]}}, \"next_step_tag\": null, \"escalation_flag\": false}\n\nCuando hayan definido al menos 2 tareas con plazos, marca phase_completed: true y next_step_tag: \"to_followup\".",
                         "instructions": "Tareas simples, viables en 24-48h. Pide compromiso verbal."}]},
            {"name": "Seguimiento", "objective": "Revisar avance, desbloquear obstáculos y ajustar",
             "agents": [{"name": "Accountability", "role": "Soporte y revisión", "goal": "Verificar ejecución y resolver bloqueos",
                         "system_prompt": "Eres un coach en fase de Seguimiento. Revisa el avance del cliente en sus tareas. Pregunta qué completó, qué no, y por qué.\n\nResponde SIEMPRE en formato JSON:\n{\"message\": \"tu respuesta\", \"structured\": {\"phase_completed\": false, \"required_fields\": {\"completed_tasks\": [], \"blockers_resolved\": []}}, \"next_step_tag\": null, \"escalation_flag\": false}\n\nSi el cliente completó todas las tareas sin bloqueos, marca phase_completed: true y next_step_tag: \"to_close\". Si hay bloqueos serios, escalation_flag: true.",
                         "instructions": "Celebra logros. Pregunta por lo que no se hizo sin juzgar."}]},
            {"name": "Cierre", "objective": "Consolidar aprendizajes y definir próximos pasos",
             "agents": [{"name": "Integrador", "role": "Síntesis y proyección", "goal": "Resumir avances y planificar siguiente etapa",
                         "system_prompt": "Eres un coach en fase de Cierre. Resume los avances del cliente, celebra logros y ayuda a definir próximos pasos.\n\nResponde SIEMPRE en formato JSON:\n{\"message\": \"tu respuesta\", \"structured\": {\"phase_completed\": false, \"required_fields\": {\"learnings\": \"\", \"next_steps\": \"\"}}, \"next_step_tag\": null, \"escalation_flag\": false}\n\nCuando el cliente tenga claros sus aprendizajes y próximos pasos, marca phase_completed: true y next_step_tag: \"journey_complete\".",
                         "instructions": "Sintetiza lo aprendido. Empodera. Ofrece continuidad."}]},
        ],
    },
    "comercial": {
        "name": "Desarrollo Comercial",
        "description": "Proceso de acompañamiento para equipos de ventas y negociación",
        "objective": "Mejorar habilidades comerciales, manejo de objeciones y cierre de ventas",
        "profile_type": "comercial",
        "output_schema": '{"message":"str","structured":{"phase_completed":bool,"required_fields":{}},"next_step_tag":"str|null","escalation_flag":bool}',
        "phases": [
            {"name": "Evaluación", "objective": "Diagnosticar fortalezas y áreas de mejora comercial",
             "agents": [{"name": "Evaluador Comercial", "role": "Diagnóstico de habilidades", "goal": "Identificar nivel actual y gaps comerciales",
                         "system_prompt": "Eres un coach comercial en fase de Evaluación. Diagnostica las habilidades de venta del cliente: prospección, presentación, manejo de objeciones, cierre.\n\nResponde SIEMPRE en formato JSON:\n{\"message\":\"tu respuesta\",\"structured\":{\"phase_completed\":false,\"required_fields\":{\"strengths\":[],\"gaps\":[],\"current_pipeline\":\"\"}},\"next_step_tag\":null,\"escalation_flag\":false}\n\nCuando tengas el diagnóstico completo, marca phase_completed:true y next_step_tag:\"to_technique\".",
                         "instructions": "Pregunta por casos reales. Sé directo y orientado a resultados."}]},
            {"name": "Técnica", "objective": "Desarrollar metodología de ventas y manejo de objeciones",
             "agents": [{"name": "Técnico de Ventas", "role": "Metodología y práctica", "goal": "Entrenar técnicas de venta consultiva",
                         "system_prompt": "Eres un coach comercial en fase de Técnica. Entrena al cliente en metodología de ventas: SPIN, Sandler, Challenger. Enfócate en sus gaps específicos.\n\nResponde SIEMPRE en formato JSON:\n{\"message\":\"tu respuesta\",\"structured\":{\"phase_completed\":false,\"required_fields\":{\"techniques_practiced\":[],\"objection_responses\":[]}},\"next_step_tag\":null,\"escalation_flag\":false}\n\nCuando haya practicado al menos 2 técnicas, marca phase_completed:true y next_step_tag:\"to_practice\".",
                         "instructions": "Role-playing. Da ejemplos concretos de su industria."}]},
            {"name": "Práctica", "objective": "Aplicar en casos reales con feedback estructurado",
             "agents": [{"name": "Simulador", "role": "Role-playing y feedback", "goal": "Practicar escenarios reales con retroalimentación",
                         "system_prompt": "Eres un coach comercial en fase de Práctica. Simula escenarios reales de venta con el cliente y da feedback.\n\nResponde SIEMPRE en formato JSON:\n{\"message\":\"tu respuesta\",\"structured\":{\"phase_completed\":false,\"required_fields\":{\"scenarios_completed\":0,\"feedback_summary\":\"\"}},\"next_step_tag\":null,\"escalation_flag\":false}\n\nCuando haya completado 2 escenarios con feedback, marca phase_completed:true y next_step_tag:\"to_results\".",
                         "instructions": "Sé honesto en el feedback. Celebra mejoras."}]},
            {"name": "Resultados", "objective": "Medir mejora, celebrar logros y planificar continuidad",
             "agents": [{"name": "Analista de Resultados", "role": "Métricas y cierre", "goal": "Evaluar progreso y definir metas futuras",
                         "system_prompt": "Eres un coach comercial en fase de Resultados. Evalúa el progreso del cliente, mide mejoras y define próximos objetivos.\n\nResponde SIEMPRE en formato JSON:\n{\"message\":\"tu respuesta\",\"structured\":{\"phase_completed\":false,\"required_fields\":{\"improvement_pct\":0,\"next_targets\":[]}},\"next_step_tag\":null,\"escalation_flag\":false}\n\nCuando hayas evaluado el progreso, marca phase_completed:true y next_step_tag:\"journey_complete\".",
                         "instructions": "Usa datos. Celebra logros. Motiva continuidad."}]},
        ],
    },
    "financiero": {
        "name": "Planificación Financiera",
        "description": "Proceso de acompañamiento para educación y planificación financiera personal",
        "objective": "Organizar finanzas, definir objetivos de ahorro/inversión y crear un plan",
        "profile_type": "financiero",
        "output_schema": '{"message":"str","structured":{"phase_completed":bool,"required_fields":{}},"next_step_tag":"str|null","escalation_flag":bool}',
        "phases": [
            {"name": "Radiografía", "objective": "Mapear situación financiera actual (ingresos, gastos, deudas)",
             "agents": [{"name": "Mapeador Financiero", "role": "Diagnóstico financiero", "goal": "Obtener panorama completo de salud financiera",
                         "system_prompt": "Eres un coach financiero en fase de Radiografía. Mapea ingresos, gastos, deudas y activos del cliente.\n\nResponde SIEMPRE en formato JSON:\n{\"message\":\"tu respuesta\",\"structured\":{\"phase_completed\":false,\"required_fields\":{\"monthly_income\":0,\"monthly_expenses\":0,\"debts\":[],\"savings\":0}},\"next_step_tag\":null,\"escalation_flag\":false}\n\nCuando tengas el panorama completo, marca phase_completed:true y next_step_tag:\"to_objectives\".\nSi detectas deuda crítica, escalation_flag:true.",
                         "instructions": "Sin juicios. Datos objetivos. Confidencialidad total."}]},
            {"name": "Objetivos", "objective": "Definir metas financieras concretas con plazos",
             "agents": [{"name": "Planificador de Metas", "role": "Definición de objetivos", "goal": "Establecer metas SMART de ahorro, inversión o reducción de deuda",
                         "system_prompt": "Eres un coach financiero en fase de Objetivos. Ayuda al cliente a definir metas financieras SMART.\n\nResponde SIEMPRE en formato JSON:\n{\"message\":\"tu respuesta\",\"structured\":{\"phase_completed\":false,\"required_fields\":{\"goals\":[{\"title\":\"\",\"target_amount\":0,\"deadline\":\"\"}]}},\"next_step_tag\":null,\"escalation_flag\":false}\n\nCuando tenga al menos 1 meta concreta, marca phase_completed:true y next_step_tag:\"to_strategy\".",
                         "instructions": "Metas realistas. Prioriza según urgencia."}]},
            {"name": "Estrategia", "objective": "Crear plan de acción con pasos concretos",
             "agents": [{"name": "Estratega Financiero", "role": "Diseño de plan", "goal": "Construir presupuesto, plan de ahorro y estrategia de inversión",
                         "system_prompt": "Eres un coach financiero en fase de Estrategia. Diseña un plan concreto: presupuesto mensual, plan de ahorro, estrategia de inversión.\n\nResponde SIEMPRE en formato JSON:\n{\"message\":\"tu respuesta\",\"structured\":{\"phase_completed\":false,\"required_fields\":{\"budget_plan\":{},\"savings_plan\":\"\",\"investment_strategy\":\"\"}},\"next_step_tag\":null,\"escalation_flag\":false}\n\nCuando el plan esté definido, marca phase_completed:true y next_step_tag:\"to_followup\".",
                         "instructions": "Plan simple y accionable. Nada de productos complejos."}]},
            {"name": "Seguimiento", "objective": "Revisar ejecución mensual y ajustar",
             "agents": [{"name": "Tracker Financiero", "role": "Monitoreo y ajuste", "goal": "Verificar cumplimiento y adaptar según cambios",
                         "system_prompt": "Eres un coach financiero en fase de Seguimiento. Revisa el cumplimiento del plan y ajusta según cambios.\n\nResponde SIEMPRE en formato JSON:\n{\"message\":\"tu respuesta\",\"structured\":{\"phase_completed\":false,\"required_fields\":{\"budget_compliance_pct\":0,\"adjustments\":[]}},\"next_step_tag\":null,\"escalation_flag\":false}\n\nSi el plan se cumplió, marca phase_completed:true y next_step_tag:\"journey_complete\". Si hay desvíos serios, escalation_flag:true.",
                         "instructions": "Sin culpa. Ajusta, no abandones."}]},
        ],
    },
    "bioneuro_full": {
        "name": "Bioneuromoción — Protocolo Completo 15 Pasos",
        "description": "Protocolo terapéutico completo: desde identificación del síntoma hasta transformación de mandatos",
        "objective": "Guiar al cliente en 15 pasos para descubrir y transformar el biocódigo emocional",
        "profile_type": "bioneuro",
        "output_schema": '{"message":"str","structured":{},"suggested_tags":[],"confidence":0.0,"escalation_flag":false}',
        "tag_mappings": {},
        "phases": [
            {"name":"1. Apertura e Historia Clínica","objective":"Recibir al consultante, habilitar historia clínica inicial","agents":[{"name":"Recepcionista","role":"Agente Inicial","goal":"Obtener nombre, apellido, fecha nacimiento, sexo, lateralidad, nacionalidad, provincia","system_prompt":"Eres el Agente Inicial de Bioneuromoción. Recibe al Consultante creando un entorno agradable. Una pregunta a la vez.\\n\\nPreguntas en orden:\\n1. '¿Podrías confirmarme tu nombre y apellido?'\\n2. '¿Cuál es tu fecha de nacimiento?'\\n3. '¿Cuál es tu sexo?'\\n4. '¿Eres diestro o zurdo?'\\n5. '¿De qué nacionalidad y provincia sos?'\\n\\nCuando tengas TODAS las respuestas, incluye en collected_data los campos: nombre, apellido, fecha_nacimiento, sexo, lateralidad, nacionalidad, provincia. Marca phase_completed:true y añade suggested_tags: [\\\"to_step_2\\\"].\\n\\nResponde SIEMPRE en JSON con: {\\\"message\\\": \\\"tu respuesta\\\", \\\"collected_data\\\": {\\\"campo\\\": \\\"valor\\\"}}","instructions":"Una pregunta a la vez. Lenguaje cálido.","allowed_tags":["to_step_2"],"collects_fields":["nombre","apellido","fecha_nacimiento","sexo","lateralidad","nacionalidad","provincia"]}]},
            {"name":"2. Clasificación MC (MCb vs MCn)","objective":"Identificar Motivo de Consulta como biológico o no biológico","agents":[{"name":"Clasificador MC","role":"Especialista MC","goal":"Clasificar MCb o MCn, preguntar desde cuándo","system_prompt":"Eres especialista en Motivos de Consulta. Pregunta:\\n1. ¿Cuál es el motivo principal por el que consultás?\\n2. ¿Desde cuándo lo tenés?\\nSi es físico/diagnóstico → MCb. Si es situacional/emocional → MCn.\\nResponde JSON: message, structured(MC,MC_detail,since), suggested_tags, confidence, escalation_flag","instructions":"Si MCb genérico pedir especificar.","allowed_tags":["to_step_3","to_step_5"]}]},
            {"name":"3. Buscar Códigos Biológicos (CB)","objective":"Traducir MCb a CB. Si MCn, saltar a paso 5","agents":[{"name":"Buscador CB","role":"Especialista CB","goal":"Encontrar CB del MCb usando memoria de casos","system_prompt":"Encuentra el CB del MCb usando memory_hits. Si no encuentras, pide más detalle. No inventes CB.\\nResponde JSON: message, structured(MC,MC_detail,CB), evidence, suggested_tags, confidence, escalation_flag","instructions":"Buscar en memoria primero. Si no hay match, preguntar detalles.","allowed_tags":["to_step_4","to_step_6"]}]},
            {"name":"4. Hachazo (MCb)","objective":"Ayudar al cliente a identificar Hachazo ligado al CB","agents":[{"name":"Detector Hachazo","role":"Especialista Hachazo","goal":"Guiar al cliente para identificar Hachazo ligado al CB","system_prompt":"Explica al cliente su CB y guíalo para identificar un Hachazo ligado a ese CB. Da ejemplos si no entiende.\\nResponde JSON: message, structured(hachazo_event,hachazo_context), suggested_tags, confidence, escalation_flag","instructions":"Si no entiende, dar ejemplos concretos.","allowed_tags":["to_step_6"]}]},
            {"name":"5. Hachazo (MCn)","objective":"Identificar Hachazo relacionado con situaciones no-biológicas","agents":[{"name":"Detector Hachazo MCn","role":"Especialista Hachazo situacional","goal":"Guiar al cliente para identificar Hachazo del MCn","system_prompt":"Para MCn, guía al cliente a recordar un evento agudo, inesperado, doloroso, vivido en soledad relacionado con su MCn.\\n'Contame una vez que te pasó... ¿cómo fue ese momento?'\\nResponde JSON: message, structured(hachazo_event,hachazo_context), suggested_tags, confidence, escalation_flag","instructions":"Guiar al cliente a revivir el momento.","allowed_tags":["to_step_6"]}]},
            {"name":"6. SEPe","objective":"Guiar al cliente a escribir Sentimientos, Emociones, Pensamientos del Hachazo","agents":[{"name":"Guía SEPe","role":"Terapeuta","goal":"Obtener 10-15 SEPe del momento del Hachazo","system_prompt":"Guía al cliente a regresar al momento exacto del Hachazo y escribir entre 10 y 15 Sentimientos, Emociones y Pensamientos.\\n'Volvé a ese instante. Escribí los pensamientos literales, sensaciones físicas y emociones. Poné pausa al llegar.'\\nResponde JSON: message, structured(SEPe,SEPe_tags), suggested_tags, confidence, escalation_flag","instructions":"Motivar suavemente. No presionar.","allowed_tags":["to_step_7"]}]},
            {"name":"7. Identificar Miedos (M1,M2,M3)","objective":"Transformar SEPe en miedos con tres preguntas secuenciales","agents":[{"name":"Extractor Miedos","role":"Especialista miedos","goal":"Obtener M1, M2, M3 con repreguntas","system_prompt":"Transforma SEPe en miedos:\\n1. Ante [SEPe], ¿miedo a qué? → M1\\n2. ¿Y si pasa M1... miedo a qué? → M2\\n3. ¿Y si pasa M2... miedo a qué? → M3\\nSi dice 'no tuve miedo', ofrece: temor, preocupación.\\nResponde JSON: message, structured(miedo_1,miedo_2,miedo_3), suggested_tags, confidence, escalation_flag","instructions":"Tres preguntas. No aceptar 'nada' sin explorar.","allowed_tags":["to_step_8"]}]},
            {"name":"8. Consecuencias del Miedo","objective":"Pedir elegir entre frágil/débil/vulnerable","agents":[{"name":"Selector Consecuencias","role":"Evaluador","goal":"El cliente elige frágil, débil o vulnerable","system_prompt":"Pide al cliente imaginar el peor momento y elegir: ¿frágil, débil o vulnerable?\\nResponde JSON: message, structured(choice), suggested_tags, confidence, escalation_flag","instructions":"Guardar la elección exacta.","allowed_tags":["to_step_9"]}]},
            {"name":"9. Tragedias (T1,T2,T3)","objective":"Obtener tres tragedias con repreguntas","agents":[{"name":"Extractor Tragedias","role":"Explorador","goal":"Obtener T1, T2, T3 con repreguntas","system_prompt":"Partiendo de [choice]:\\n1. Si [choice], ¿qué es lo peor que podría pasar? → T1\\n2. Y si T1, ¿qué tragedia peor? → T2\\n3. Y si T2, ¿la peor de todas? → T3\\nNo aceptar 'nada'. Insistir suavemente.\\nResponde JSON: message, structured(tragedia_1,tragedia_2,tragedia_3), suggested_tags, confidence, escalation_flag","instructions":"Insistir suavemente si bloquea.","allowed_tags":["to_step_10"]}]},
            {"name":"10. Autoatribuciones","objective":"Ofrecer 5 opciones de desvalorización, elegir 2","agents":[{"name":"Selector Atribuciones","role":"Identificador creencias","goal":"Cliente elige 2 de 5 opciones","system_prompt":"Ofrece 5 opciones sin interpretar:\\n1. NO VALGO\\n2. NO SIRVO\\n3. NO MEREZCO NADA\\n4. NO PERTENEZCO\\n5. NO EXISTO\\nEl cliente elige 2 y las memoriza en orden.\\nResponde JSON: message, structured(self_attributions), suggested_tags, confidence, escalation_flag","instructions":"No interpretar. Solo presentar y registrar.","allowed_tags":["to_step_11"]}]},
            {"name":"11. Perfil A/B","objective":"Inventar personas con ~15 atributos cada una","agents":[{"name":"Constructor Perfiles","role":"Diseñador identidades","goal":"Obtener 15 atributos para Perfil A y Perfil B","system_prompt":"Pide al cliente imaginar dos personas:\\nPerfil A: 'Si yo fuera [atribuciones], ¿cómo tendría que ser alguien para sentir [tragedia_3]? Dame 15 atributos.'\\nPerfil B: 'Si NO fuera [atribuciones], ¿cómo sería? Dame otros 15.'\\nNumera y separa cada atributo.\\nResponde JSON: message, structured(perfiles_A,perfiles_B), suggested_tags, confidence, escalation_flag","instructions":"Separar y numerar cada atributo.","allowed_tags":["to_step_12"]}]},
            {"name":"12. CreMa (Creencias y Mandatos)","objective":"Confeccionar Creencia y Mandato para cada perfil","agents":[{"name":"Compilador CreMa","role":"Sintetizador","goal":"Generar Creencia An+Mandato An, Creencia Bn+Mandato Bn en 1ª persona","system_prompt":"Para cada atributo, genera en 1ª persona:\\n'Si yo fuera [atributo]... entonces NO PUEDO SER [atributo]'\\nNO mostrar al cliente todavía. Guardar para paso 13.\\nResponde JSON: message, structured(CreMa), suggested_tags, confidence, escalation_flag","instructions":"Generar pero no mostrar todavía.","allowed_tags":["to_step_13"]}]},
            {"name":"13. Mostrar CreMa","objective":"Mostrar listado combinado al cliente, explicar origen","agents":[{"name":"Presentador CreMa","role":"Comunicador","goal":"Mostrar CreMa con tono suave, explicar origen","system_prompt":"Muestra al cliente el listado combinado de Creencias y Mandatos. Explica su origen con tono suave (panza de mamá). No juzgues.\\nResponde JSON: message, structured(presented_crema,acknowledged), suggested_tags, confidence, escalation_flag","instructions":"Tono suave. Explicar sin juzgar.","allowed_tags":["to_step_14"]}]},
            {"name":"14. Herramientas para Sanar","objective":"Dar ejercicios prácticos para desafiar cada mandato","agents":[{"name":"Facilitador","role":"Coach transformación","goal":"Explicar ejercicios breves para desafiar mandatos","system_prompt":"Para cada CreMa, da un ejercicio práctico, simple y viable en 24-48h.\\nEj: si 'no puedo ser visible' → 'poner una foto en redes sociales'.\\nResponde JSON: message, structured(exercises,explainers), suggested_tags, confidence, escalation_flag","instructions":"Ejercicios simples. Viables. Motivador.","allowed_tags":["to_step_15"]}]},
            {"name":"15. Cierre y Próximos Pasos","objective":"Resumir, ofrecer continuidad, cerrar con empoderamiento","agents":[{"name":"Cerrador","role":"Sintetizador final","goal":"Resumir 14 pasos, ofrecer seguimiento, cierre cálido","system_prompt":"Resume brevemente lo trabajado en 14 etapas. Felicita al cliente. Ofrece seguimiento personalizado, talleres o material adicional. Termina con empoderamiento.\\nResponde JSON: message, structured(summary,offer), suggested_tags, confidence, escalation_flag","instructions":"Resumir sin abrumar. Cierre cálido y empoderante.","allowed_tags":["journey_complete"]}]}
        ],
    },
    "bioneuro": {
        "name": "Bioneuromoción — 12 Pasos Profundos",
        "description": "Protocolo terapéutico guiado para descubrir el biocódigo emocional detrás de un síntoma físico",
        "objective": "Guiar al cliente a través de 12 pasos para identificar y transformar el mandato emocional asociado a su síntoma",
        "profile_type": "bioneuro",
        "phases": [
            {"name": "1. Apertura y Encuadre", "objective": "Saludar, pedir datos básicos y confirmar propósito de la consulta",
             "agents": [{"name": "Recepcionista", "role": "Apertura empática", "goal": "Obtener nombre, edad, género y encuadrar la sesión",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 1 de 12: Apertura y Encuadre. Saluda al cliente con calidez, pide su nombre, edad y género. Confirma que entiende el propósito de la consulta. No avances a preguntas clínicas todavía. Sé amable y profesional.",
                         "instructions": "output_format: json. fields_expected: client_name, age, gender."}]},
            {"name": "2. Identificación del Síntoma", "objective": "Describir el síntoma físico y su cronología",
             "agents": [{"name": "Explorador de Síntomas", "role": "Historia clínica inicial", "goal": "Obtener descripción detallada del síntoma y timeline",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 2 de 12: Identificación del Síntoma. Pide al cliente que describa el síntoma físico que lo trae hoy y desde cuándo. Guíalo a expresar el momento inicial y cualquier episodio relevante posterior. Sé empático pero metódico.",
                         "instructions": "output_format: json. fields_expected: symptom_description, timeline."}]},
            {"name": "3. Búsqueda del Hachazo", "objective": "Encontrar el evento traumático agudo, inesperado y vivido en soledad",
             "agents": [{"name": "Detector de Hachazo", "role": "Rastreo de trauma inicial", "goal": "Identificar el hachazo: evento agudo, inesperado, doloroso, vivido en soledad",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 3 de 12: Búsqueda del Hachazo. Invita al cliente a recordar un evento puntual ANTES del inicio del síntoma. Este evento debe haber sido AGUDO, INESPERADO, DOLOROSO y VIVIDO EN SOLEDAD. Ayúdalo a encontrar ese instante preciso y a describirlo brevemente. No interpretes, solo guía.",
                         "instructions": "output_format: json. fields_expected: hachazo_event."}]},
            {"name": "4. Inmersión Sensorial", "objective": "Revivir el hachazo capturando sensaciones: imágenes, sonidos, olores",
             "agents": [{"name": "Guía Sensorial", "role": "Inmersión guiada", "goal": "Obtener al menos 10 sensaciones del momento del hachazo",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 4 de 12: Inmersión Sensorial. Pídele al cliente que se sumerja en ese momento del hachazo y capture lo que percibe: imágenes, sonidos, olores, sensaciones corporales. Pide una lista de al menos 10 sensaciones. NO interpretes, solo registra. Sé un espejo neutro.",
                         "instructions": "output_format: json. fields_expected: sensations_list (min 10 items)."}]},
            {"name": "5. La Pregunta por el Miedo", "objective": "Identificar el miedo primario con la frase clave del protocolo",
             "agents": [{"name": "Extractor de Miedo", "role": "Identificación del miedo raíz", "goal": "Obtener el miedo primario usando la frase del protocolo",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 5 de 12: La pregunta por el miedo. Formula EXACTAMENTE esta frase: 'En ese momento del hachazo, cuando escuchaste [lo que dijo la persona], fijate bien... ¿miedo a qué?'. Registra la primera emoción de miedo identificada por el cliente. No interpretes ni reformules. Usa las palabras literales del protocolo.",
                         "instructions": "output_format: json. fields_expected: fear_primary."}]},
            {"name": "6. Ahondar en el Miedo", "objective": "Cadena de miedos: ¿Y si nadie/todo el mundo...?",
             "agents": [{"name": "Cadena de Miedos", "role": "Profundización progresiva", "goal": "Obtener miedo secundario, terciario, vulnerabilidad central y amenaza máxima",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 6 de 12: Ahondar en el miedo. Realiza la cadena de miedos: a) ¿Y si nadie/todo el mundo [miedo_primario]...? → obtén miedo_secundario. b) ¿Y si nadie/todo el mundo [miedo_secundario]...? → obtén miedo_terciario. Luego pregunta: '¿Cuál es tu vulnerabilidad central?' y '¿Cuál sería la amenaza máxima?'. Registra todo sin juzgar.",
                         "instructions": "output_format: json. fields_expected: fear_chain, core_vulnerability, threat_max."}]},
            {"name": "7. Opciones de Desvalorización", "objective": "Presentar las 5 frases y pedir que elija 2",
             "agents": [{"name": "Selector de Desvalorización", "role": "Presentación de opciones", "goal": "El cliente elige 2 de las 5 frases de desvalorización",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 7 de 12: Opciones de Desvalorización. Ofrece EXACTAMENTE estas 5 frases y pide que elija 2: 1. NO VALGO, 2. NO SIRVO, 3. NO MEREZCO NADA, 4. NO PERTENEZCO, 5. NO EXISTO. No comentes ni interpretes las opciones. Solo preséntalas y registra las 2 elegidas.",
                         "instructions": "output_format: json. fields_expected: devaluation_options (2 items)."}]},
            {"name": "8. Elección Crítica", "objective": "Confirmar las 2 opciones elegidas",
             "agents": [{"name": "Confirmador", "role": "Validación de elección", "goal": "Confirmar y registrar las 2 desvalorizaciones elegidas",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 8 de 12: Elección Crítica. Confirma cuáles fueron las dos opciones elegidas por el cliente. Repíteselas textualmente. No razones, no analices, solo confirma y registra.",
                         "instructions": "output_format: json. fields_expected: chosen_devaluations (2 items)."}]},
            {"name": "9. Perfil 'Si Yo Fuera'", "objective": "Construir el perfil de la persona que sufriría esa amenaza",
             "agents": [{"name": "Constructor de Identidad", "role": "Proyección de atributos", "goal": "El cliente lista 15+ atributos de la persona que sufriría esa amenaza",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 9 de 12: Perfil Si Yo Fuera. Pídele al cliente: 'Si vos tuvieras que sufrir [amenaza_máxima], imaginá una persona que tenga que pasar por eso. ¿Cómo tendría que ser? Dame al menos 15 atributos de esa persona.' Anota todos los atributos. No filtres ni juzgues.",
                         "instructions": "output_format: json. fields_expected: identity_attributes (min 15 items)."}]},
            {"name": "10. Creencias y Mandatos", "objective": "Combinar atributos + desvalorizaciones en mandatos",
             "agents": [{"name": "Compilador de Mandatos", "role": "Síntesis de creencias", "goal": "Generar mandatos: Si soy [atributo] → [desvalorización]. Mandato: NO PUEDO SER...",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 10 de 12: Creencias y Mandatos. Toma los atributos y las desvalorizaciones. Para cada atributo, construye: 'Si soy [ATRIBUTO], entonces [DESVALORIZACIÓN 1] y [DESVALORIZACIÓN 2]. Por lo tanto, el mandato es: NO PUEDO SER [ATRIBUTO]...' Presenta los mandatos generados de forma clara y contundente.",
                         "instructions": "output_format: json. fields_expected: mandates_generated (list of mandate strings)."}]},
            {"name": "11. Tareas de Desafío", "objective": "Proponer acción concreta contraria al mandato para 24-48h",
             "agents": [{"name": "Diseñador de Tareas", "role": "Acción terapéutica", "goal": "El cliente se compromete a una tarea simple, viable y contraria al mandato",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 11 de 12: Tareas de Desafío. Propón UNA acción concreta que sea CONTRARIA al mandato descubierto. Debe ser SIMPLE, VIABLE y realizable en 24-48 horas. Pide compromiso verbal del cliente para realizarla. Ejemplo: si el mandato es 'no puedo ser visible', la tarea es 'poner una foto tuya en redes sociales'. Sé específico y firme pero alentador.",
                         "instructions": "output_format: json. fields_expected: assigned_task."}]},
            {"name": "12. Cierre y Próximos Pasos", "objective": "Resumir lo trabajado y ofrecer continuidad",
             "agents": [{"name": "Cerrador de Sesión", "role": "Síntesis y cierre", "goal": "Resumir avances, felicitar, ofrecer próxima sesión",
                         "system_prompt": "Eres un coach de Bioneuromoción en el paso 12 de 12: Cierre. Resume brevemente lo trabajado hoy. Felicita al cliente por su valentía. Recuérdale su tarea de desafío. Ofrece programar una sesión personalizada de seguimiento. Termina con un mensaje de empoderamiento y cierre cálido.",
                         "instructions": "output_format: json. fields_expected: []."}]},
        ],
    },
}


class JourneyEngine:
    """Core journey business logic — prompt composition, routing, progress."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    # ── CRUD ──

    async def create_journey(self, coach_id: str, name: str, **kwargs) -> dict:
        jid = uuid4().hex[:12]
        async with self._sf() as s:
            j = JourneyModel(id=jid, coach_id=coach_id, name=name, **kwargs)
            s.add(j)
            await s.commit()
            return self._journey_to_dict(j)

    async def list_journeys(self, coach_id: str, full: bool = False) -> list[dict]:
        async with self._sf() as s:
            result = await s.execute(
                select(JourneyModel).where(JourneyModel.coach_id == coach_id).order_by(JourneyModel.created_at.desc())
            )
            journeys = [self._journey_to_dict(j) for j in result.scalars().all()]
            if full:
                for j in journeys:
                    j["phases"] = await self._get_phases(s, j["id"])
                    j["agents"] = await self._get_agents(s, j["id"])
            return journeys

    async def get_journey(self, journey_id: str) -> dict | None:
        async with self._sf() as s:
            j = await s.get(JourneyModel, journey_id)
            if not j:
                return None
            phases = await self._get_phases(s, journey_id)
            agents = await self._get_agents(s, journey_id)
            d = self._journey_to_dict(j)
            d["phases"] = phases
            d["agents"] = agents
            return d

    async def update_journey(self, journey_id: str, **fields) -> dict | None:
        async with self._sf() as s:
            j = await s.get(JourneyModel, journey_id)
            if not j:
                return None
            bump = False
            for k, v in fields.items():
                if k != "version" and hasattr(j, k) and v is not None:
                    setattr(j, k, v)
                    bump = True
            if bump:
                j.version = (getattr(j, "version", 1) or 1) + 1
            await s.commit()
            return self._journey_to_dict(j)

    async def add_phase(self, journey_id: str, name: str, **kwargs) -> dict:
        pid = uuid4().hex[:12]
        async with self._sf() as s:
            p = JourneyPhaseModel(id=pid, journey_id=journey_id, name=name, **kwargs)
            s.add(p)
            await s.commit()
            return self._phase_to_dict(p)

    async def update_phase(self, phase_id: str, **fields) -> dict | None:
        async with self._sf() as s:
            p = await s.get(JourneyPhaseModel, phase_id)
            if not p:
                return None
            for k, v in fields.items():
                if hasattr(p, k) and v is not None:
                    setattr(p, k, v)
            await s.commit()
            return self._phase_to_dict(p)

    async def add_agent(self, journey_id: str, phase_id: str, name: str, **kwargs) -> dict:
        aid = uuid4().hex[:12]
        async with self._sf() as s:
            a = JourneyAgentModel(id=aid, journey_id=journey_id, phase_id=phase_id, name=name, **kwargs)
            s.add(a)
            await s.commit()
            return self._agent_to_dict(a)

    async def update_agent(self, agent_id: str, **fields) -> dict | None:
        async with self._sf() as s:
            a = await s.get(JourneyAgentModel, agent_id)
            if not a:
                return None
            for k, v in fields.items():
                if hasattr(a, k) and v is not None:
                    setattr(a, k, v)
            await s.commit()
            return self._agent_to_dict(a)

    async def update_journey_tags(self, journey_id: str, tag_mappings: dict) -> dict | None:
        async with self._sf() as s:
            j = await s.get(JourneyModel, journey_id)
            if not j:
                return None
            j.tag_mappings = tag_mappings
            await s.commit()
            return self._journey_to_dict(j)

    async def delete_journey(self, journey_id: str) -> bool:
        async with self._sf() as s:
            j = await s.get(JourneyModel, journey_id)
            if not j:
                return False
            await s.execute(delete(JourneyAgentModel).where(JourneyAgentModel.journey_id == journey_id))
            await s.execute(delete(JourneyPhaseModel).where(JourneyPhaseModel.journey_id == journey_id))
            await s.delete(j)
            await s.commit()
            return True

    async def clone_journey(self, journey_id: str) -> dict | None:
        original = await self.get_journey(journey_id)
        if not original:
            return None
        new_id = uuid4().hex[:12]
        phase_id_map = {}
        async with self._sf() as s:
            orig_model = await s.get(JourneyModel, journey_id)
            if not orig_model:
                return None
            new_j = JourneyModel(
                id=new_id, coach_id=orig_model.coach_id,
                name=f"Copia de {orig_model.name}",
                description=orig_model.description, objective=orig_model.objective,
                profile_type=orig_model.profile_type, status="draft", version=1,
                tag_mappings=orig_model.tag_mappings,
            )
            s.add(new_j)
            for phase in original.get("phases", []):
                new_pid = uuid4().hex[:12]
                phase_id_map[phase["id"]] = new_pid
                new_p = JourneyPhaseModel(
                    id=new_pid, journey_id=new_id,
                    name=phase["name"], objective=phase.get("objective", ""),
                    order_index=phase["order_index"],
                )
                s.add(new_p)
            for agent in original.get("agents", []):
                new_a = JourneyAgentModel(
                    id=uuid4().hex[:12], journey_id=new_id,
                    phase_id=phase_id_map.get(agent["phase_id"], ""),
                    name=agent["name"], role=agent.get("role", ""),
                    goal=agent.get("goal", ""),
                    system_prompt=agent.get("system_prompt", ""),
                    instructions=agent.get("instructions", ""),
                    collects_fields=agent.get("collects_fields", []),
                    output_schema=agent.get("output_schema", {}),
                    tag_mappings=agent.get("tag_mappings", {}),
                    order_index=agent.get("order_index", 0),
                    is_active=agent.get("is_active", True),
                )
                s.add(new_a)
            await s.commit()
        return await self.get_journey(new_id)

    async def reorder_phase(self, phase_id: str, direction: str = "up") -> bool:
        async with self._sf() as s:
            p = await s.get(JourneyPhaseModel, phase_id)
            if not p:
                return False
            result = await s.execute(
                select(JourneyPhaseModel).where(JourneyPhaseModel.journey_id == p.journey_id).order_by(JourneyPhaseModel.order_index)
            )
            phases = result.scalars().all()
            idx = next((i for i, ph in enumerate(phases) if ph.id == phase_id), -1)
            if idx < 0:
                return False
            if direction == "up" and idx > 0:
                phases[idx].order_index, phases[idx-1].order_index = phases[idx-1].order_index, phases[idx].order_index
                await s.commit()
                return True
            if direction == "down" and idx < len(phases) - 1:
                phases[idx].order_index, phases[idx+1].order_index = phases[idx+1].order_index, phases[idx].order_index
                await s.commit()
                return True
            return False

    # ── Client assignment ──

    async def assign_client(self, client_id: str, coach_id: str, journey_id: str) -> dict | None:
        journey = await self.get_journey(journey_id)
        if not journey:
            return None

        # Check if client already has this journey
        existing = await self.get_client_journey(client_id)
        if existing and existing.get("journey") and existing.get("journey", {}).get("id") == journey_id:
            return existing

        phases = journey.get("phases", [])
        first_phase = phases[0] if phases else None
        first_agent = None
        if first_phase:
            agents = [a for a in journey.get("agents", []) if a["phase_id"] == first_phase["id"]]
            first_agent = agents[0] if agents else None

        # Pre-populate collected_data from existing shared profile (cross-journey data sharing)
        existing_profile_data = {}
        async with self._sf() as s:
            sp_result = await s.execute(
                select(ClientSharedProfileModel).where(ClientSharedProfileModel.client_id == client_id)
            )
            sp_existing = sp_result.scalars().first()
            if sp_existing and sp_existing.profile_data:
                existing_profile_data = dict(sp_existing.profile_data)

        cid = uuid4().hex[:12]
        async with self._sf() as s:
            cj = ClientJourneyModel(
                id=cid, client_id=client_id, coach_id=coach_id, journey_id=journey_id,
                current_phase_id=first_phase["id"] if first_phase else None,
                current_agent_id=first_agent["id"] if first_agent else None,
                status="in_progress", started_at=_utcnow(), last_interaction_at=_utcnow(),
                collected_data=existing_profile_data,
            )
            s.add(cj)

            # Auto-create shared profile (or update if exists)
            existing_sp = await s.execute(
                select(ClientSharedProfileModel).where(ClientSharedProfileModel.client_id == client_id)
            )
            sp = existing_sp.scalars().first()
            if sp:
                sp.journey_id = journey_id
                sp.goals_data = {"main": journey.get("objective", "")}
            else:
                sp = ClientSharedProfileModel(
                    id=uuid4().hex[:12], client_id=client_id, coach_id=coach_id, journey_id=journey_id,
                    profile_data={}, goals_data={"main": journey.get("objective", "")},
                )
                s.add(sp)

            # Log event
            ev = JourneyEventModel(id=uuid4().hex[:12], client_id=client_id, coach_id=coach_id,
                                   journey_id=journey_id, event_type="journey_started",
                                   payload_data={"status": "in_progress"})
            s.add(ev)
            await s.commit()
            return self._client_journey_to_dict(cj)

    async def _log_journey_event(self, client_id: str, coach_id: str, journey_id: str,
                                  event_type: str, payload_data: dict = None):
        """Log a journey event to PostgreSQL."""
        try:
            async with self._sf() as s:
                ev = JourneyEventModel(
                    id=uuid4().hex[:12], client_id=client_id, coach_id=coach_id,
                    journey_id=journey_id, event_type=event_type,
                    payload_data=payload_data or {}
                )
                s.add(ev)
                await s.commit()
        except Exception as e:
            logger.warning("Failed to log journey event: %s", e)

    async def get_client_journey(self, client_id: str) -> dict | None:
        async with self._sf() as s:
            result = await s.execute(
                select(ClientJourneyModel).where(ClientJourneyModel.client_id == client_id)
                    .order_by(ClientJourneyModel.created_at.desc())
            )
            cj = result.scalars().first()
            if not cj:
                return None
            d = self._client_journey_to_dict(cj)
            journey = await self.get_journey(cj.journey_id)
            d["journey"] = journey
            sp = await self.get_shared_profile(s, client_id)
            d["shared_profile"] = sp
            return d

    async def get_shared_profile(self, session_or_sf, client_id: str) -> dict | None:
        is_sf = hasattr(session_or_sf, '__call__')
        if is_sf:
            async with session_or_sf() as s:
                return await self._get_shared_profile(s, client_id)
        return await self._get_shared_profile(session_or_sf, client_id)

    async def _get_shared_profile(self, s, client_id: str) -> dict | None:
        result = await s.execute(
            select(ClientSharedProfileModel).where(ClientSharedProfileModel.client_id == client_id)
        )
        sp = result.scalars().first()
        return self._shared_profile_to_dict(sp) if sp else None

    async def update_shared_profile(self, client_id: str, **fields) -> dict | None:
        async with self._sf() as s:
            result = await s.execute(
                select(ClientSharedProfileModel).where(ClientSharedProfileModel.client_id == client_id)
            )
            sp = result.scalars().first()
            if not sp:
                return None
            for k, v in fields.items():
                if hasattr(sp, k) and v is not None:
                    setattr(sp, k, v)
            sp.updated_at = _utcnow()
            await s.commit()
            return self._shared_profile_to_dict(sp)

    async def advance_client(self, client_id: str) -> dict | None:
        """Move to next agent/phase based on order_index."""
        cj_data = await self.get_client_journey(client_id)
        if not cj_data:
            return None

        journey = cj_data.get("journey", {})
        phases = sorted(journey.get("phases", []), key=lambda p: p["order_index"])
        agents = sorted(journey.get("agents", []), key=lambda a: a["order_index"])

        current_phase_id = cj_data.get("current_phase_id")
        current_agent_id = cj_data.get("current_agent_id")
        new_phase_id = current_phase_id
        new_agent_id = current_agent_id
        new_status = cj_data.get("status", "in_progress")

        if current_agent_id and current_phase_id:
            # Find next agent in same phase
            phase_agents = [a for a in agents if a["phase_id"] == current_phase_id]
            cur_idx = next((i for i, a in enumerate(phase_agents) if a["id"] == current_agent_id), -1)
            if cur_idx >= 0 and cur_idx + 1 < len(phase_agents):
                new_agent_id = phase_agents[cur_idx + 1]["id"]
            else:
                # Move to next phase
                phase_idx = next((i for i, p in enumerate(phases) if p["id"] == current_phase_id), -1)
                if phase_idx >= 0 and phase_idx + 1 < len(phases):
                    next_phase = phases[phase_idx + 1]
                    new_phase_id = next_phase["id"]
                    next_agents = [a for a in agents if a["phase_id"] == next_phase["id"]]
                    new_agent_id = next_agents[0]["id"] if next_agents else current_agent_id
                else:
                    new_status = "completed_journey"

        # Calculate progress
        if new_status == "completed_journey":
            progress = 100
        else:
            completed = sum(1 for p in phases if p["order_index"] < next(
                (p["order_index"] for p in phases if p["id"] == new_phase_id), 0
            ))
            progress = int(completed / len(phases) * 100) if phases else 0

        async with self._sf() as s:
            result = await s.execute(
                select(ClientJourneyModel).where(ClientJourneyModel.client_id == client_id)
            )
            cj = result.scalars().first()
            if cj:
                cj.current_phase_id = new_phase_id
                cj.current_agent_id = new_agent_id
                cj.status = new_status
                cj.progress_pct = progress
                cj.last_interaction_at = _utcnow()
                if new_agent_id != current_agent_id or new_status == "completed_journey":
                    cj.turn_count = 0
                if new_status == "completed_journey":
                    cj.completed_at = _utcnow()

                # Promote collected_data → shared_profile.profile_data for cross-journey persistence
                collected = cj.collected_data or {}
                if isinstance(collected, str):
                    try:
                        collected = json.loads(collected)
                    except json.JSONDecodeError:
                        collected = {}
                if collected:
                    sp_result = await s.execute(
                        select(ClientSharedProfileModel)
                        .where(ClientSharedProfileModel.client_id == client_id)
                    )
                    sp = sp_result.scalars().first()
                    if sp:
                        merged = dict(sp.profile_data or {})
                        merged.update({k: v for k, v in collected.items() if v and not k.startswith("_")})
                        sp.profile_data = merged
                        sp.updated_at = _utcnow()

                ev = JourneyEventModel(id=uuid4().hex[:12], client_id=client_id,
                                       coach_id=cj.coach_id, journey_id=cj.journey_id,
                                       phase_id=new_phase_id, agent_id=new_agent_id,
                                       event_type="phase_advanced",
                                       payload_data={"from_phase": current_phase_id, "to_phase": new_phase_id})
                s.add(ev)
                await s.commit()
                return self._client_journey_to_dict(cj)
        return None


    # ── Prompt composition ──

    async def compose_agent_prompt(self, client_id: str, message: str,
                                    coach_name: str = "", language: str = "es",
                                    memory_hits: list = None, coach_imprint: dict = None,
                                    case_store=None) -> str:
        """K6: Compose prompt using agent's system_prompt + collected data + state."""
        cj_data = await self.get_client_journey(client_id)
        if not cj_data or not cj_data.get("journey"):
            return ""

        journey = cj_data["journey"]
        current_phase_id = cj_data.get("current_phase_id")
        current_agent_id = cj_data.get("current_agent_id")

        agents = journey.get("agents", [])
        agent_data = next((a for a in agents if a["id"] == current_agent_id), agents[0] if agents else {})
        phases = journey.get("phases", [])
        phase_data = next((p for p in phases if p["id"] == current_phase_id), phases[0] if phases else {})

        system_prompt = agent_data.get("system_prompt", "")
        if not system_prompt.strip():
            return ""

        prompt = system_prompt

        # K7: New session detection — inject resume block if gap > 6h
        last_raw = cj_data.get("last_interaction_at")
        if last_raw:
            try:
                last_dt = datetime.fromisoformat(last_raw) if isinstance(last_raw, str) else last_raw
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                delta = _utcnow() - last_dt
                if delta.total_seconds() > 6 * 3600:
                    tiempo_str = _humanize_delta(delta)
                    prompt = (
                        f"## RETOMADA DE SESIÓN\n"
                        f"El cliente retoma la conversación después de {tiempo_str}. "
                        f"ANTES de continuar con tu objetivo habitual, debes:\n"
                        f"1. Saludar cálidamente y reconocer que es un nuevo encuentro.\n"
                        f"2. Hacer un breve recap de lo que ya trabajaron juntos "
                        f"(usa los datos recolectados que aparecen más abajo).\n"
                        f"3. Preguntar cómo está el cliente y si quiere continuar desde donde lo dejaron.\n"
                        f"Solo después de ese saludo y confirmación, retoma tu objetivo normal de fase.\n\n"
                    ) + prompt
            except Exception:
                pass

        # K6: Template placeholders
        prompt = prompt.replace("{{step_title}}", phase_data.get("name", ""))
        prompt = prompt.replace("{{step_objective}}", phase_data.get("objective", ""))
        prompt = prompt.replace("{{agent_name}}", agent_data.get("name", ""))
        prompt = prompt.replace("{{journey_name}}", journey.get("name", ""))
        prompt = prompt.replace("{{coach_name}}", coach_name)

        # K5: Imprint-to-Text — inject coach behavioral rules
        if coach_imprint:
            from kairos.core.impronta import Impronta
            from kairos.engine.imprint_mapper import ImprintMapper
            try:
                impronta = Impronta(**{k: float(v) for k, v in coach_imprint.items() if isinstance(v, (int, float))})
                rules = ImprintMapper().map(impronta)
                if rules:
                    prompt += "\n\n## Estilo de coaching\n" + "\n".join(f"- {r}" for r in rules)
            except Exception:
                pass

        # Resolve {{client_name}} from collected_data or shared profile
        resolved_client_name = ""
        collected_data_placeholder = cj_data.get("collected_data", {}) or {}
        if isinstance(collected_data_placeholder, str):
            try:
                collected_data_placeholder = json.loads(collected_data_placeholder)
            except (json.JSONDecodeError, ValueError):
                collected_data_placeholder = {}
        for key in ("nombre", "client_name", "name", "cliente"):
            if collected_data_placeholder.get(key):
                resolved_client_name = collected_data_placeholder[key]
                break
        sp = await self.get_shared_profile(self._sf, client_id)
        if not resolved_client_name and sp:
            resolved_client_name = sp.get("profile_data", {}).get("nombre", "") or sp.get("profile_data", {}).get("name", "")
        prompt = prompt.replace("{{client_name}}", resolved_client_name)

        # Resolve {{collected.*}} placeholders (e.g. {{collected.email}})
        import re
        collected_refs = re.findall(r"\{\{collected\.([^}]+)\}\}", prompt)
        for ref in collected_refs:
            val = collected_data_placeholder.get(ref, "")
            if not val and sp:
                val = sp.get("profile_data", {}).get(ref, "")
            prompt = prompt.replace("{{collected." + ref + "}}", str(val) if val else "")

        # Collected data from client_journeys.collected_data (source of truth)
        collected_data = cj_data.get("collected_data", {}) or {}
        if isinstance(collected_data, str):
            try:
                collected_data = json.loads(collected_data)
            except (json.JSONDecodeError, ValueError):
                collected_data = {}
        clean_collected = {k: v for k, v in collected_data.items() if v and not k.startswith("_")}
        if clean_collected:
            prompt += "\n\n## Datos recolectados del cliente\n"
            prompt += "\n".join(f"- {k}: {v}" for k, v in clean_collected.items())

        # Journey state
        prompt += f"""

## Estado
- Journey: {journey.get('name', '')}
- Fase actual: {phase_data.get('name', '?')} — {phase_data.get('objective', '')}
- Progreso: {cj_data.get('progress_pct', 0)}%
"""

        # RAG: inject relevant coach KB + session history hits
        if memory_hits:
            kb_hits = [h for h in memory_hits if h.get("source") == "coach_kb" and h.get("content")]
            session_hits = [h for h in memory_hits if h.get("source") == "session_history" and h.get("content")]
            if kb_hits:
                prompt += "\n## Material relevante del coach\n"
                prompt += "\n---\n".join(h["content"][:600] for h in kb_hits[:3])
            if session_hits:
                prompt += "\n\n## Historial de sesiones anteriores del cliente\n"
                prompt += "\n---\n".join(h["content"][:400] for h in session_hits[:2])

        # K4: CaseStore RAG — inject relevant cases from N2 memory
        rag_top_k = agent_data.get("rag_top_k", 0) or 0
        if rag_top_k > 0 and case_store and hasattr(case_store, "search_relevant"):
            try:
                cases = await case_store.search_relevant(
                    query_text=message,
                    profile_id=journey.get("profile_type", "coaching"),
                    client_id=client_id,
                    top_k=rag_top_k,
                )
                valid_cases = [c for c in cases if c.get("_score", 0) > 0.5 and c.get("content")]
                if valid_cases:
                    prompt += "\n\n## Casos relevantes de memoria\n"
                    for c in valid_cases[:rag_top_k]:
                        content = c.get("content", "")
                        outcome = c.get("outcome", "")
                        case_text = content[:400]
                        if outcome:
                            case_text += f"\nResultado: {outcome[:200]}"
                        prompt += f"\n---\n{case_text}"
            except Exception:
                pass

        prompt += f"""
## Mensaje del cliente
{message}
"""
        return prompt

    async def validate_and_advance(self, client_id: str, llm_response: str, agent_data: dict = None) -> dict:
        """K3+K2: Parse JSON response, save structured data, apply tag transitions."""
        result = {"advanced": False, "error": None, "phase_completed": False, "message": llm_response, "action": "stay", "suggested_tags": []}

        # Count this turn against the current agent (reset to 0 on transition)
        try:
            async with self._sf() as s:
                await s.execute(
                    update(ClientJourneyModel)
                    .where(ClientJourneyModel.client_id == client_id)
                    .values(turn_count=func.coalesce(ClientJourneyModel.turn_count, 0) + 1)
                )
                await s.commit()
        except Exception as e:
            logger.debug("turn_count increment skipped: %s", e)

        # Parse JSON
        data = None
        try:
            clean = llm_response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(clean)
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass

        if data and isinstance(data, dict):
            result["message"] = data.get("message", llm_response)
            structured = data.get("structured", {}) or {}

            # Bug fix: read next_step_tag (string) used by coaching/comercial/financiero prompts
            # in addition to suggested_tags (array) used by bioneuro prompts
            suggested_tags = data.get("suggested_tags", []) or []
            next_step_tag = data.get("next_step_tag")
            if next_step_tag and isinstance(next_step_tag, str) and next_step_tag not in suggested_tags:
                suggested_tags.append(next_step_tag)
            if suggested_tags:
                result["suggested_tags"] = suggested_tags

            # Core: Extract ALL collected data regardless of JSON format
            # Supports: {"collected_data": {...}}, {"structured": {"collected_data": {...}}},
            #           {"structured": {"required_fields": {...}}}, {"structured": {"field": "value"}}
            all_fields = {}

            # 1. Top-level collected_data (bioneuro format)
            top_collected = data.get("collected_data", {})
            if isinstance(top_collected, dict):
                all_fields.update((k, v) for k, v in top_collected.items() if v and not k.startswith("_"))

            if isinstance(structured, dict):
                # 2. structured.collected_data
                struct_collected = structured.get("collected_data", {})
                if isinstance(struct_collected, dict):
                    all_fields.update((k, v) for k, v in struct_collected.items() if v and not k.startswith("_"))

                # 3. structured.required_fields (coaching/comercial/financiero format) — was being skipped before
                req_fields = structured.get("required_fields", {})
                if isinstance(req_fields, dict):
                    all_fields.update((k, v) for k, v in req_fields.items() if v and not k.startswith("_"))

                # 4. Other scalar fields in structured (legacy)
                for key in structured:
                    if key not in ("collected_data", "phase_completed", "required_fields") and not key.startswith("_"):
                        val = structured[key]
                        if isinstance(val, (str, int, float, bool)) and val:
                            all_fields[key] = val

            logger.debug(
                "journey validate: client=%s agent=%s json_parsed=True fields=%s phase_completed=%s tags=%s",
                client_id, (agent_data or {}).get("name", "?"),
                list(all_fields.keys()), structured.get("phase_completed") if isinstance(structured, dict) else False,
                suggested_tags,
            )

            # Save to shared profile
            if all_fields:
                async with self._sf() as s:
                    sp_result = await s.execute(
                        select(ClientSharedProfileModel).where(ClientSharedProfileModel.client_id == client_id)
                    )
                    sp = sp_result.scalars().first()
                    if sp:
                        merged = dict(sp.profile_data or {})
                        merged.update(all_fields)
                        sp.profile_data = merged
                        sp.updated_at = _utcnow()
                    await s.commit()

            if isinstance(structured, dict) and structured.get("phase_completed"):
                result["phase_completed"] = True
        else:
            logger.warning(
                "journey validate: client=%s agent=%s JSON parse FAILED — no advancement. preview=%.300s",
                client_id, (agent_data or {}).get("name", "?"), llm_response,
            )

        # K2: Tag transitions
        if result.get("suggested_tags") and agent_data:
            allowed = agent_data.get("allowed_tags", [])
            journey_data = await self.get_client_journey(client_id)
            if journey_data:
                journey = journey_data.get("journey", {}) or {}
                phases = journey.get("phases", [])
                # Merge agent-level and journey-level tag_mappings
                agent_tag_map = agent_data.get("tag_mappings", {}) or {}
                journey_tag_map = journey.get("tag_mappings", {}) or {}
                tag_map = {**journey_tag_map, **agent_tag_map}
                for tag in result["suggested_tags"]:
                    if tag in allowed:
                        target = tag_map.get(tag)
                        if target is not None and target != 99:
                            # Resolve target (order_index → phase_id, or keep if already phase_id)
                            target_phase_id = target if isinstance(target, str) else None
                            if target_phase_id is None:
                                target_phase = next(
                                    (p for p in phases if p.get("order_index") == target),
                                    None
                                )
                                target_phase_id = target_phase["id"] if target_phase else None
                            if target_phase_id:
                                await self._jump_to_step(client_id, target_phase_id)
                                result["advanced"] = True
                        elif target == 99:
                            # journey_complete
                            async with self._sf() as s:
                                cj = (await s.execute(
                                    select(ClientJourneyModel).where(ClientJourneyModel.client_id == client_id)
                                )).scalars().first()
                                if cj:
                                    cj.status = "completed_journey"
                                    cj.progress_pct = 100
                                    cj.completed_at = _utcnow()
                                    await s.commit()
                            result["advanced"] = True
                        await self._log_journey_event(client_id, journey_data.get("coach_id", ""),
                            journey_data.get("journey_id", ""), "phase_advanced",
                            {"agent": agent_data.get("name", "?"), "tag": tag,
                             "target": target, "target_type": "tag_jump" if target != 99 else "complete"})
                        break

        if result.get("phase_completed") and not result["advanced"]:
            await self.advance_client(client_id)
            result["advanced"] = True

        # F2: evaluate the acting agent's objective (deterministic) and persist it.
        # Extracted variables are reused by the coordinator (F3) below.
        collected = {}
        turn_count = 0
        obj_state = {}
        journey_id = ""
        current_phase_id = ""
        coach_id = ""
        if agent_data:
            try:
                from kairos.engine.objective_evaluator import ObjectiveEvaluator
                async with self._sf() as s:
                    cj = (await s.execute(
                        select(ClientJourneyModel).where(ClientJourneyModel.client_id == client_id)
                    )).scalars().first()
                    if cj:
                        raw = cj.collected_data or {}
                        if isinstance(raw, str):
                            try:
                                raw = json.loads(raw)
                            except (json.JSONDecodeError, ValueError):
                                raw = {}
                        collected = raw
                        turn_count = cj.turn_count or 0
                        journey_id = cj.journey_id or ""
                        current_phase_id = cj.current_phase_id or ""
                        coach_id = cj.coach_id or ""

                        # Merge shared_profile data — validate_and_advance writes
                        # collected fields there, not in client_journeys.collected_data.
                        sp_result = await s.execute(
                            select(ClientSharedProfileModel).where(
                                ClientSharedProfileModel.client_id == client_id
                            )
                        )
                        sp = sp_result.scalars().first()
                        if sp and sp.profile_data:
                            sp_data = sp.profile_data
                            if isinstance(sp_data, str):
                                try:
                                    sp_data = json.loads(sp_data)
                                except (json.JSONDecodeError, ValueError):
                                    sp_data = {}
                            collected = {**sp_data, **collected}

                        objective = await ObjectiveEvaluator().evaluate(agent_data, collected)
                        obj_state = dict(cj.objective_state or {})
                        obj_state[agent_data.get("id", "?")] = objective
                        cj.objective_state = obj_state
                        await s.commit()
                        result["objective"] = objective
            except Exception as e:
                logger.debug("objective evaluation skipped: %s", e)

        # F3: guard-based transitions via the coordinator (runs when tags did not advance)
        if not result.get("advanced") and agent_data and journey_id and current_phase_id:
            try:
                from kairos.engine.journey_coordinator import JourneyCoordinator
                ctx = {
                    "collected": collected,
                    "turn_count": turn_count,
                    "objective_state": obj_state,
                }
                coord = JourneyCoordinator(self._sf)
                transition = await coord.resolve_transition(
                    journey_id, current_phase_id, ctx
                )
                if transition:
                    target = transition["to_phase_id"]
                    if target == "__complete__":
                        async with self._sf() as s:
                            cj2 = (await s.execute(
                                select(ClientJourneyModel).where(
                                    ClientJourneyModel.client_id == client_id
                                )
                            )).scalars().first()
                            if cj2:
                                cj2.status = "completed_journey"
                                cj2.progress_pct = 100
                                cj2.completed_at = _utcnow()
                                await s.commit()
                        result["advanced"] = True
                    elif target.startswith("journey:"):
                        new_journey_id = target[len("journey:"):]
                        await self.assign_client(client_id, coach_id, new_journey_id)
                        async with self._sf() as s:
                            cj2 = (await s.execute(
                                select(ClientJourneyModel).where(
                                    ClientJourneyModel.client_id == client_id
                                )
                            )).scalars().first()
                            if cj2:
                                cj2.status = "derived"
                                cj2.progress_pct = 100
                                cj2.completed_at = _utcnow()
                                await s.commit()
                        result["advanced"] = True
                    elif target:
                        await self._jump_to_step(client_id, target)
                        result["advanced"] = True
            except Exception as e:
                logger.debug("coordinator transition skipped: %s", e)

        # F4: fallback — route to rescue agent if max_turns exceeded without advancement
        if not result.get("advanced") and agent_data:
            max_turns = agent_data.get("max_turns", 0) or 0
            client_turn = turn_count or 0
            if max_turns > 0 and client_turn >= max_turns:
                fallback_id = agent_data.get("fallback_agent_id", "") or ""
                if fallback_id:
                    try:
                        await self._jump_to_agent(client_id, fallback_id)
                        result["advanced"] = True
                        result["fallback_applied"] = True
                    except Exception as e:
                        logger.debug("fallback jump failed: %s", e)

        return result

    async def _jump_to_step(self, client_id: str, target_phase_id: str):
        """K2: Jump to specific phase bypassing sequential order."""
        cj_data = await self.get_client_journey(client_id)
        if not cj_data:
            return
        journey = cj_data.get("journey", {})
        agents = journey.get("agents", [])
        target_agents = [a for a in agents if a["phase_id"] == target_phase_id]
        first_agent = target_agents[0] if target_agents else None

        async with self._sf() as s:
            result = await s.execute(
                select(ClientJourneyModel).where(ClientJourneyModel.client_id == client_id)
            )
            cj = result.scalars().first()
            if cj:
                cj.current_phase_id = target_phase_id
                cj.current_agent_id = first_agent["id"] if first_agent else cj.current_agent_id
                cj.turn_count = 0
                cj.last_interaction_at = _utcnow()
                ev = JourneyEventModel(id=uuid4().hex[:12], client_id=client_id,
                                       coach_id=cj.coach_id, journey_id=cj.journey_id,
                                       phase_id=target_phase_id, agent_id=first_agent["id"] if first_agent else "",
                                       event_type="tag_jump",
                                       payload_data={"to_phase": target_phase_id})
                s.add(ev)
                await s.commit()

    async def _jump_to_agent(self, client_id: str, target_agent_id: str):
        """F4: Jump to a specific agent (not just the first of the phase)."""
        cj_data = await self.get_client_journey(client_id)
        if not cj_data:
            return
        journey = cj_data.get("journey", {})
        agents = journey.get("agents", [])
        target = next((a for a in agents if a["id"] == target_agent_id), None)
        if not target:
            return
        async with self._sf() as s:
            result = await s.execute(
                select(ClientJourneyModel).where(ClientJourneyModel.client_id == client_id)
            )
            cj = result.scalars().first()
            if cj:
                cj.current_phase_id = target["phase_id"]
                cj.current_agent_id = target_agent_id
                cj.turn_count = 0
                cj.last_interaction_at = _utcnow()
                ev = JourneyEventModel(
                    id=uuid4().hex[:12], client_id=client_id,
                    coach_id=cj.coach_id, journey_id=cj.journey_id,
                    phase_id=target["phase_id"], agent_id=target_agent_id,
                    event_type="fallback_jump",
                    payload_data={"to_agent": target_agent_id},
                )
                s.add(ev)
                await s.commit()

    # ── Transition CRUD (F6 UI) ──

    async def get_transitions(self, journey_id: str) -> list[dict]:
        async with self._sf() as s:
            result = await s.execute(
                select(JourneyTransitionModel)
                .where(JourneyTransitionModel.journey_id == journey_id)
                .order_by(JourneyTransitionModel.priority.desc())
            )
            return [{c.name: getattr(t, c.name) for c in t.__table__.columns}
                    for t in result.scalars().all()]

    async def add_transition(self, journey_id: str, from_phase_id: str,
                             to_phase_id: str, condition: dict,
                             priority: int = 0) -> dict:
        tid = uuid4().hex[:12]
        async with self._sf() as s:
            t = JourneyTransitionModel(
                id=tid, journey_id=journey_id, from_phase_id=from_phase_id,
                to_phase_id=to_phase_id, condition=condition,
                priority=priority, is_active=True,
            )
            s.add(t)
            await s.commit()
            return {c.name: getattr(t, c.name) for c in t.__table__.columns}

    async def update_transition(self, transition_id: str, **fields) -> dict | None:
        async with self._sf() as s:
            t = await s.get(JourneyTransitionModel, transition_id)
            if not t:
                return None
            for k, v in fields.items():
                if hasattr(t, k) and v is not None:
                    setattr(t, k, v)
            t.updated_at = _utcnow()
            await s.commit()
            return {c.name: getattr(t, c.name) for c in t.__table__.columns}

    async def delete_transition(self, transition_id: str) -> bool:
        async with self._sf() as s:
            t = await s.get(JourneyTransitionModel, transition_id)
            if not t:
                return False
            await s.delete(t)
            await s.commit()
            return True

    async def save_collected(self, client_id: str, collected: dict) -> None:
        """Save collected data to both client_journeys and shared_profiles atomically.

        Vital fields (nombre, apellido, etc.) are normalized from aliases and
        written to a canonical `vital_fields` sub-key in shared_profiles.profile_data.
        """
        if not collected:
            return

        from kairos.engine.vital_fields import extract_vital_fields, normalize_collected
        normalized = normalize_collected(collected)
        vital = extract_vital_fields(normalized)

        async with self._sf() as s:
            from sqlalchemy import update
            # 1. Update client_journeys.collected_data (keep normalized version)
            await s.execute(
                update(ClientJourneyModel)
                .where(ClientJourneyModel.client_id == client_id)
                .values(collected_data=normalized)
            )
            # 2. Merge into shared_profiles.profile_data + stamp vital_fields
            sp_result = await s.execute(
                select(ClientSharedProfileModel)
                .where(ClientSharedProfileModel.client_id == client_id)
            )
            sp = sp_result.scalars().first()
            if sp:
                merged = dict(sp.profile_data or {})
                merged.update({k: v for k, v in normalized.items() if v and not k.startswith("_")})
                if vital:
                    existing_vital = dict(merged.get("vital_fields", {}) or {})
                    existing_vital.update(vital)
                    merged["vital_fields"] = existing_vital
                sp.profile_data = merged
                sp.updated_at = _utcnow()
            await s.commit()

    def _format_shared_profile(self, sp: dict) -> str:
        if not sp:
            return "Sin información previa."
        parts = []
        profile = sp.get("profile_data", {})
        if profile:
            parts.append(f"Perfil: {profile}")
        goals = sp.get("goals_data", {})
        if goals:
            parts.append(f"Objetivos: {goals}")
        summary = sp.get("conversation_summary", "")
        if summary:
            parts.append(f"Resumen: {summary}")
        return "\n".join(parts) if parts else "Sin información previa."

    # ── Seed defaults ──

    async def seed_defaults(self):
        """Seed default journey templates if none exist."""
        async with self._sf() as s:
            count = await s.execute(select(JourneyModel).limit(1))
            if count.scalars().first():
                return

        coach_id = "default"
        for profile_type, data in DEFAULT_JOURNEYS.items():
            jid = uuid4().hex[:12]
            async with self._sf() as s:
                j = JourneyModel(id=jid, coach_id=coach_id, name=data["name"],
                                 description=data["description"], objective=data["objective"],
                                 profile_type=profile_type, status="active")
                s.add(j)
                await s.commit()

            for pi, phase_data in enumerate(data["phases"]):
                pid = uuid4().hex[:12]
                async with self._sf() as s:
                    p = JourneyPhaseModel(id=pid, journey_id=jid, name=phase_data["name"],
                                          objective=phase_data["objective"], order_index=pi)
                    s.add(p)
                    await s.commit()

                for ai, agent_data in enumerate(phase_data["agents"]):
                    aid = uuid4().hex[:12]
                    async with self._sf() as s:
                        # Extract output_schema from journey level if agent doesn't have one
                        agent_output_schema = agent_data.get("output_schema") or data.get("output_schema", "")
                        a = JourneyAgentModel(id=aid, journey_id=jid, phase_id=pid,
                                              name=agent_data["name"], role=agent_data["role"],
                                              goal=agent_data["goal"], order_index=ai,
                                              system_prompt=agent_data.get("system_prompt", ""),
                                              instructions=agent_data.get("instructions", ""),
                                              allowed_tags=agent_data.get("allowed_tags", []),
                                              output_schema=agent_output_schema,
                                              collects_fields=agent_data.get("collects_fields", []))
                        s.add(a)
                        await s.commit()
            logger.info("Seeded journey: %s (%d phases)", data["name"], len(data["phases"]))

    # ── Serialization helpers ──

    def _journey_to_dict(self, j: JourneyModel) -> dict:
        return {"id": j.id, "coach_id": j.coach_id, "name": j.name, "description": j.description,
                "objective": j.objective, "profile_type": j.profile_type, "language": j.language,
                "status": j.status, "version": getattr(j, "version", 1),
                "channel": getattr(j, "channel", "text") or "text",
                "tag_mappings": getattr(j, "tag_mappings", {}) or {},
                "created_at": j.created_at.isoformat() if j.created_at else ""}

    def _phase_to_dict(self, p: JourneyPhaseModel) -> dict:
        return {"id": p.id, "journey_id": p.journey_id, "name": p.name, "description": p.description,
                "objective": p.objective, "order_index": p.order_index,
                "completion_criteria": p.completion_criteria, "visible_to_client": p.visible_to_client}

    def _agent_to_dict(self, a: JourneyAgentModel) -> dict:
        return {"id": a.id, "journey_id": a.journey_id, "phase_id": a.phase_id, "name": a.name,
                "role": a.role, "goal": a.goal, "system_prompt": a.system_prompt,
                "instructions": a.instructions, "order_index": a.order_index, "is_active": a.is_active,
                "allowed_tags": getattr(a, "allowed_tags", []) or [],
                "output_schema": getattr(a, "output_schema", {}) or {},
                "collects_fields": getattr(a, "collects_fields", []) or [],
                "tag_mappings": getattr(a, "tag_mappings", {}) or {},
                "max_turns": getattr(a, "max_turns", 0) or 0,
                "fallback_agent_id": getattr(a, "fallback_agent_id", "") or "",
                "version": getattr(a, "version", 1)}

    def _client_journey_to_dict(self, cj: ClientJourneyModel) -> dict:
        collected = getattr(cj, "collected_data", {}) or {}
        if isinstance(collected, str):
            try:
                collected = json.loads(collected)
            except json.JSONDecodeError:
                collected = {}
        return {"id": cj.id, "client_id": cj.client_id, "coach_id": cj.coach_id,
                "journey_id": cj.journey_id, "current_phase_id": cj.current_phase_id,
                "current_agent_id": cj.current_agent_id, "status": cj.status,
                "progress_pct": cj.progress_pct, "extra": cj.extra,
                "collected_data": collected,
                "current_phase_order": getattr(cj, "current_phase_order", 1),
                "turn_count": getattr(cj, "turn_count", 0) or 0,
                "objective_state": getattr(cj, "objective_state", {}) or {},
                "started_at": cj.started_at.isoformat() if cj.started_at else "",
                "last_interaction_at": cj.last_interaction_at.isoformat() if cj.last_interaction_at else ""}

    async def _get_phases(self, s, journey_id: str) -> list[dict]:
        result = await s.execute(
            select(JourneyPhaseModel).where(JourneyPhaseModel.journey_id == journey_id).order_by(JourneyPhaseModel.order_index)
        )
        return [self._phase_to_dict(p) for p in result.scalars().all()]

    async def _get_agents(self, s, journey_id: str) -> list[dict]:
        result = await s.execute(
            select(JourneyAgentModel).where(JourneyAgentModel.journey_id == journey_id).order_by(JourneyAgentModel.order_index)
        )
        return [self._agent_to_dict(a) for a in result.scalars().all()]

    def _shared_profile_to_dict(self, sp: ClientSharedProfileModel) -> dict:
        return {"id": sp.id, "client_id": sp.client_id, "journey_id": sp.journey_id,
                "profile_data": sp.profile_data, "goals_data": sp.goals_data,
                "insights_data": sp.insights_data or [], "blockers_data": sp.blockers_data or [],
                "tasks_data": sp.tasks_data or [], "checkpoints_data": sp.checkpoints_data or [],
                "conversation_summary": sp.conversation_summary or "",
                "risk_flags_data": sp.risk_flags_data or []}


# ── K3: JSON Schema Validation ──

def validate_agent_output(schema: dict, output: dict) -> dict:
    errors = []
    if not schema:
        return {"valid": True, "errors": []}
    required = schema.get("structured", {}).get("required_fields", {})
    if required:
        structured = output.get("structured", {})
        for field, expected_type in required.items():
            if field not in structured:
                errors.append(f"Campo requerido '{field}' ausente")
                continue
            val = structured[field]
            type_map = {"string": str, "number": (int, float), "boolean": bool, "list": list, "dict": dict}
            expected = type_map.get(expected_type)
            if expected and not isinstance(val, expected):
                errors.append(f"Campo '{field}': esperado {expected_type}, recibido {type(val).__name__}")
    output_schema = schema.get("output_schema", {})
    if output_schema:
        for field in output_schema:
            if field not in output:
                errors.append(f"Campo '{field}' del output_schema ausente en respuesta")
    return {"valid": len(errors) == 0, "errors": errors}
