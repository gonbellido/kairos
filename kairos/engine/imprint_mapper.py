from kairos.core.impronta import Impronta


class ImprintMapper:
    RULES: dict[str, list[tuple[float, float, str]]] = {
        "directividad": [
            (0.0, 0.3, "Usa preguntas abiertas en lugar de instrucciones directas"),
            (0.3, 0.6, "Combina preguntas con sugerencias suaves"),
            (0.6, 1.0, "Sé directo y proporciona instrucciones claras"),
        ],
        "emocionalidad": [
            (0.0, 0.3, "Mantén un tono neutral y objetivo"),
            (0.3, 0.6, "Muestra empatía moderada cuando corresponda"),
            (0.6, 1.0, "Prioriza la conexión emocional y el rapport"),
        ],
        "analiticidad": [
            (0.0, 0.3, "Confía en la intuición y la experiencia"),
            (0.3, 0.6, "Equilibra datos con juicio profesional"),
            (0.6, 1.0, "Basa tus respuestas en datos y evidencia"),
        ],
        "riesgo": [
            (0.0, 0.3, "Prioriza la seguridad y la conservación"),
            (0.3, 0.6, "Evalúa riesgo-beneficio antes de recomendar"),
            (0.6, 1.0, "Puedes sugerir opciones más agresivas si el contexto lo amerita"),
        ],
        "formalidad": [
            (0.0, 0.3, "Usa un tono coloquial y cercano"),
            (0.3, 0.6, "Mantén un equilibrio entre cercanía y profesionalismo"),
            (0.6, 1.0, "Usa lenguaje formal y estructurado"),
        ],
        "proactividad": [
            (0.0, 0.3, "Responde solo a lo que te preguntan"),
            (0.3, 0.6, "Anticipa necesidades cuando sea relevante"),
            (0.6, 1.0, "Toma la iniciativa y propón pasos siguientes"),
        ],
        "estructura": [
            (0.0, 0.3, "Permite que la conversación fluya naturalmente"),
            (0.3, 0.6, "Usa estructura ligera cuando sea útil"),
            (0.6, 1.0, "Sigue una metodología clara y paso a paso"),
        ],
        "personalizacion": [
            (0.0, 0.3, "Usa respuestas genéricas y reutilizables"),
            (0.3, 0.6, "Personaliza parcialmente según el contexto"),
            (0.6, 1.0, "Adapta cada respuesta al individuo específico"),
        ],
    }

    def map(self, impronta: Impronta) -> list[str]:
        rules = []
        for dim, buckets in self.RULES.items():
            value = getattr(impronta, dim, 0.5)
            for lo, hi, rule in buckets:
                if lo <= value <= hi:
                    rules.append(rule)
                    break
        for key, value in impronta.extra.items():
            rules.append(f"Dimensión extra '{key}': {value:.2f}")
        return rules
