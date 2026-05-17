---
id: "{{ client_id }}"
coach: "{{ coach_id }}"
nombre: "{{ nombre }}"
tags: [kairos/cliente, {{ estado_emocional }}]
created: "{{ created_at }}"
updated: "{{ updated_at }}"
---
# 👤 {{ nombre }}

> [!warning] Estado Actual
> **Emocional:** {{ estado_emocional }} · **Claridad:** {{ claridad_pct }} · **Energía:** {{ energia_pct }} · **Resistencia:** {{ resistencia_pct }}

```dataview
TABLE
  "{{ estado_emocional }}" as Estado,
  {{ claridad }} as Claridad,
  {{ energia }} as Energía,
  {{ resistencia }} as Resistencia,
  {{ score_global }} as "Score Global"
FROM "KAIROS/Clientes/{{ nombre_safe }}"
```

## 📈 Progreso
- **Score Global:** {{ score_global_pct }}
- **Señales:** Claridad {{ senales.claridad_pct }} · Acción {{ senales.accion_pct }} · Apertura {{ senales.apertura_pct }} · Consistencia {{ senales.consistencia_pct }}

## 🎯 Objetivos
{{ objetivos_list }}

## 🧠 Patrones Detectados
{{ patrones_list }}

## 💡 Insights
{{ insights_list }}

## 📁 Expediente
- **Sesiones:** {{ sesiones }}
- **Mensajes:** {{ mensajes }}
- ` [[Bitácora]] ` · ` [[Alertas]] `

---

> [!info] Generado por KAIROS automáticamente.
> Edita esta nota para agregar observaciones del coach — KAIROS las leerá en la próxima síntesis.
