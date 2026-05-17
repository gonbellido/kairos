---
tags: [kairos/config]
---
# ⚙️ Configuración Activa — Instrucciones Calientes

> [!info] Este archivo es leído por KAIROS en cada interacción.
> Edita las secciones debajo para cambiar el comportamiento de los agentes en tiempo real.

## 🎭 Impronta Override (por cliente)

Define overrides de impronta por `client_id`. KAIROS los aplicará automáticamente.

```yaml
# Formato:
# client_id: { directividad: 0.7, emocionalidad: 0.4 }
# Ejemplo:
# ana_garcia: { directividad: 0.7, emocionalidad: 0.4 }
# juan_perez: { riesgo: 0.2, analiticidad: 0.9 }
```

## 📝 Instrucciones Generales para el Coach-Bot

Escribe aquí instrucciones que KAIROS debe seguir para TODAS las interacciones:

- ...

## 🧠 Metodología Activa

Define qué enfoque de coaching usar por defecto:

```yaml
metodologia: "ontologica"
# Opciones: ontologica, sistemica, cognitiva, PNL, integrativa
```

## 🚫 Anti-Patrones a Evitar

- ...

---

> [!warning] Los cambios toman efecto en la PRÓXIMA interacción con cada cliente.
