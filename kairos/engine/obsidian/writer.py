from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState
from kairos.core.client import ClientProfile, ClientInsight, ClientPattern, Alert


class ObsidianWriter:
    def __init__(self, vault_path: str | Path):
        self._vault = Path(vault_path)
        self._base = self._vault / "KAIROS"
        self.ensure_structure()

    def ensure_structure(self) -> None:
        for folder in [
            "Clientes", "Alertas", "Metodología", "Dashboard",
        ]:
            (self._base / folder).mkdir(parents=True, exist_ok=True)

    # ── Client Profile Note ─────────────────────────────────────────

    def write_client_profile(self, profile: ClientProfile) -> Path:
        folder = self._base / "Clientes" / self._safe_name(profile.nombre)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self._safe_name(profile.nombre)}.md"

        content = self._client_template(profile)
        path.write_text(content, encoding="utf-8")
        return path

    def _client_template(self, p: ClientProfile) -> str:
        tags = " ".join(f"#{t}" for t in ["kairos/cliente", p.estado_actual.emocional])
        sc = p.estado_actual
        sg = p.progreso.senales
        return f"""---
id: {p.id}
coach_id: "{p.coach_id}"
nombre: "{p.nombre}"
tags: [{tags}]
created: {p.created_at.date()}
updated: {p.updated_at.date()}
emocion: "{sc.emocional}"
claridad: {sc.claridad}
energia: {sc.energia}
resistencia: {sc.resistencia}
score_global: {p.progreso.score_global}
senal_claridad: {sg.claridad}
senal_accion: {sg.accion}
senal_apertura: {sg.apertura}
senal_consistencia: {sg.consistencia}
sesiones: {p.historial.get('sesiones', 0)}
mensajes: {p.historial.get('mensajes', 0)}
---
# 👤 {p.nombre}

> [!warning] Estado Actual
> **Emocional:** {sc.emocional} · **Claridad:** {sc.claridad:.0%} · **Energía:** {sc.energia:.0%} · **Resistencia:** {sc.resistencia:.0%}

## 📈 Progreso
- **Score Global:** {p.progreso.score_global:.0%}
- **Señales:** Claridad {sg.claridad:.0%} · Acción {sg.accion:.0%} · Apertura {sg.apertura:.0%} · Consistencia {sg.consistencia:.0%}

## 🎯 Objetivos
{"".join(f"1. [[{o.titulo}]] — {o.descripcion}\n" for o in p.objetivos) if p.objetivos else "_Sin objetivos definidos._"}

## 🧠 Patrones Detectados
{"".join(f"- **{pat.patron}** (×{pat.frecuencia}) — último: {pat.ultima_deteccion.strftime('%d/%m/%y')}\n" for pat in p.patrones_detectados[-10:]) if p.patrones_detectados else "_Sin patrones todavía._"}

## 💡 Insights
{"".join(f"> {ins.contenido}\n>\n> *— {ins.fuente}, {ins.timestamp.strftime('%d/%m/%y')}*\n\n" for ins in p.insights[-5:]) if p.insights else "_Sin insights todavía._"}

## 📁 Expediente
- **Sesiones:** {p.historial.get('sesiones', 0)}
- **Mensajes:** {p.historial.get('mensajes', 0)}
- [[Bitácora]] · [[Alertas]]

---

> [!info] Generado por KAIROS automáticamente.
> Las variables en frontmatter están disponibles para consultas Dataview.
> ```dataview
> TABLE nombre, emocion, round(score_global * 100) as Progreso
> FROM #kairos/cliente
> SORT score_global ASC
> ```
"""

    # ── Dashboard ────────────────────────────────────────────────────

    def write_dashboard(self, clients: list[ClientProfile]) -> Path:
        path = self._base / "Dashboard" / "Portafolio.md"
        has_alerts = any(c.alertas_activas for c in clients)

        content = f"""---
tags: [kairos/dashboard]
updated: {_utcnow().strftime('%Y-%m-%d')}
---
# 📊 Portafolio de Clientes

> [!info] Última actualización: {_utcnow().strftime('%d/%m/%Y %H:%M')}

## 📋 Cartera de Clientes

```dataview
TABLE
  nombre as Cliente,
  emocion as Ánimo,
  round(claridad * 100) as Claridad,
  round(energia * 100) as Energía,
  round(resistencia * 100) as Resistencia,
  round(score_global * 100) as Progreso
FROM #kairos/cliente
SORT score_global ASC
```

## 🚨 Alertas Activas
{"![[Alertas/_inbox.md]]" if has_alerts else "_Sin alertas activas._"}

---

> [!tip] Priorización automática
> Los clientes con score_global más bajo aparecen primero en la tabla.
"""

        path.write_text(content, encoding="utf-8")
        return path

    # ── Alert / Inbox ────────────────────────────────────────────────

    def write_alert(self, alert: Alert) -> Path:
        folder = self._base / "Alertas"
        folder.mkdir(exist_ok=True)
        filename = f"{alert.tipo}_{alert.cliente_id}_{_utcnow().strftime('%Y%m%d_%H%M')}.md"
        path = folder / filename

        level_icon = {"low": "🟡", "medium": "🟠", "high": "🔴", "urgent": "🚨"}.get(alert.nivel, "🟡")

        content = f"""---
tags: [kairos/alerta, {alert.nivel}]
cliente: "{alert.cliente_id}"
tipo: "{alert.tipo}"
nivel: "{alert.nivel}"
accion: "{alert.accion}"
created: {_utcnow().isoformat()}
---

{level_icon} # Alerta: {alert.tipo.replace('_', ' ')}

> [!danger] {alert.mensaje}

**Acción recomendada:** `{alert.accion}`
"""
        path.write_text(content, encoding="utf-8")
        return path

    # ── Hot Config (Coach → KAIROS) ─────────────────────────────────

    def write_config_template(self) -> Path:
        path = self._base / "Config.md"
        if path.exists():
            return path
        content = """---
tags: [kairos/config]
---
# ⚙️ Configuración Activa — Instrucciones Calientes

> [!info] Este archivo es leído por KAIROS en cada interacción.
> Edita las líneas debajo para cambiar el comportamiento de los agentes en tiempo real.

## 🎭 Impronta Override (por cliente)
```yaml
# client_id: { impronta_overrides }
# Ejemplo:
# ana_garcia: { directividad: 0.7, emocionalidad: 0.4 }
```

## 📝 Instrucciones Generales
- Escribe aquí instrucciones que KAIROS debe seguir para todas las interacciones: ...
"""
        path.write_text(content, encoding="utf-8")
        return path

    # ── Config Parser (Obsidian → KAIROS) ────────────────────────────

    def parse_config(self) -> dict[str, Any]:
        path = self._base / "Config.md"
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8")

        overrides = {}
        in_yaml_block = False
        for line in text.split("\n"):
            stripped = line.strip()
            if "override" in line.lower():
                in_yaml_block = False  # wait for ```
                continue
            if stripped.startswith("```") and not in_yaml_block:
                in_yaml_block = True  # enter code fence
                continue
            if stripped.startswith("```") and in_yaml_block:
                in_yaml_block = False  # exit code fence
                continue
            if in_yaml_block:
                if stripped.startswith("#") or not stripped:
                    continue
                if ":" in stripped:
                    parts = stripped.split(":", 1)
                    key = parts[0].strip().strip('"').strip("'")
                    val = parts[1].strip()
                    if val.startswith("{") and val.endswith("}"):
                        import json as _json
                        try:
                            overrides[key] = _json.loads(val)
                        except _json.JSONDecodeError:
                            pass
        return overrides

    @staticmethod
    def _safe_name(name: str) -> str:
        return name.replace(" ", "_").replace("/", "_").replace(":", "_")
