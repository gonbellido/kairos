import json
import re
from kairos.core.state import StateClassification


class StateClassifier:
    def __init__(self, llm=None, confidence_threshold: float = 0.65, prompt_store=None):
        self._llm = llm
        self._threshold = confidence_threshold
        self._prompt_store = prompt_store

    async def classify(self, message: str, context: dict | None = None) -> StateClassification:
        text = message.lower()

        riesgo = self._detect_risk(text)
        emocion, emocion_conf = self._detect_emotion_with_confidence(text)
        urgencia = self._detect_urgency(text)
        intencion = self._detect_intention(text)
        tono = self._detect_tone(text)

        confidence = self._overall_confidence(emocion_conf, riesgo, urgencia)

        if confidence < self._threshold and self._llm:
            try:
                return await self._llm_classify(message)
            except Exception:
                pass  # fallback al resultado regex

        return StateClassification(
            riesgo=riesgo,
            emocion=emocion,
            urgencia=urgencia,
            intencion=intencion,
            tono=tono,
        )

    def _overall_confidence(self, emocion_conf: float, riesgo: float, urgencia: float) -> float:
        signals = 0
        if emocion_conf > 0.3:
            signals += 1
        if riesgo > 0.1:
            signals += 1
        if urgencia > 0.0:
            signals += 1
        return signals / 3.0

    async def _llm_classify(self, message: str) -> StateClassification:
        from langchain_core.messages import HumanMessage, SystemMessage

        classifier_prompt = (
            "Clasifica el mensaje para un sistema de coaching/asesoría. "
            "Responde SOLO con JSON, sin texto adicional:\n"
            "{\n"
            '  "riesgo": <float 0-1>,\n'
            '  "emocion": <"positive"|"negative"|"neutral"|"urgent">,\n'
            '  "urgencia": <float 0-1>,\n'
            '  "intencion": <"queja"|"compra"|"soporte"|"consulta"|"seguimiento"|"general">,\n'
            '  "tono": <"friendly"|"hostile"|"polite"|"neutral">\n'
            "}"
        )

        if self._prompt_store:
            try:
                stored = await self._prompt_store.get("classifier")
                if stored.strip():
                    classifier_prompt = stored
            except Exception:
                pass

        prompt = [SystemMessage(content=classifier_prompt),
                   HumanMessage(content=message)]
        response = await self._llm.ainvoke(prompt)
        text = response.content.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            raise ValueError("LLM no devolvió JSON válido")
        data = json.loads(match.group())
        return StateClassification(
            riesgo=float(data.get("riesgo", 0.0)),
            emocion=str(data.get("emocion", "neutral")),
            urgencia=float(data.get("urgencia", 0.0)),
            intencion=str(data.get("intencion", "general")),
            tono=str(data.get("tono", "neutral")),
        )

    def _detect_risk(self, text: str) -> float:
        high_risk = {"perdí", "crisis", "urgencia", "grave", "demanda", "emergencia", "abogado"}
        low_risk = {"consulta", "duda", "quiero saber", "información"}
        words = self._tokenize(text)
        hr = len(words & high_risk)
        lr = len(words & low_risk)
        return max(0.0, min(1.0, hr * 0.3 - lr * 0.1))

    def _detect_emotion_with_confidence(self, text: str) -> tuple[str, float]:
        positive = {"feliz", "contento", "gracias", "genial", "excelente", "bueno", "me alegra", "logré", "avancé"}
        negative = {
            "enfadado", "triste", "frustrado", "molesto", "harto", "decepcionado",
            "estancado", "perdido", "bloqueado", "atrapado", "no puedo", "imposible",
            "agotado", "desmotivado", "confundido", "angustiado", "preocupado",
        }
        urgent = {"urgente", "inmediato", "inmediata", "ya", "ahora", "corre", "emergencia"}
        words = self._tokenize(text)

        pos_hits = len(words & positive)
        neg_hits = len(words & negative)
        urg_hits = len(words & urgent)

        total = pos_hits + neg_hits + urg_hits
        if total == 0:
            return "neutral", 0.0

        if urg_hits > 0:
            return "urgent", min(1.0, urg_hits / 2)
        if neg_hits > pos_hits:
            return "negative", min(1.0, neg_hits / 3)
        if pos_hits > 0:
            return "positive", min(1.0, pos_hits / 3)
        return "neutral", 0.0

    def _detect_emotion(self, text: str) -> str:
        emocion, _ = self._detect_emotion_with_confidence(text)
        return emocion

    def _tokenize(self, text: str) -> set[str]:
        return set(re.sub(r"[^\w\sáéíóúñ]", " ", text.lower()).split())

    def _detect_urgency(self, text: str) -> float:
        urgent_words = {"urgente", "inmediato", "ya", "ahora", "lo antes posible", "corre", "hoy", "emergencia", "rápido"}
        found = sum(1 for w in urgent_words if w in text)
        return min(1.0, found * 0.25)

    def _detect_intention(self, text: str) -> str:
        patterns = {
            "queja": r"queja|reclamo|insatisfecho|mal servicio",
            "compra": r"comprar|adquirir|cotizar|precio|cuánto cuesta",
            "soporte": r"no funciona|error|problema técnico|ayuda|cómo se",
            "consulta": r"qué es|quién es|cómo funciona|información",
            "seguimiento": r"seguimiento|continuación|como hablamos|retomamos",
        }
        for intention, pattern in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return intention
        return "general"

    def _detect_tone(self, text: str) -> str:
        if re.search(r"(?i)^(hola|buenos días|buenas)", text):
            return "friendly"
        if re.search(r"(?i)(exijo|demando|deberían|es su obligación)", text):
            return "hostile"
        if re.search(r"(?i)(por favor|gracias|agradezco)", text):
            return "polite"
        return "neutral"
