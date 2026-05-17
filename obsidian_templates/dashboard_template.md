---
tags: [kairos/dashboard]
updated: "{{ updated_at }}"
---
# 📊 Portafolio de Clientes

> [!info] Última actualización: {{ updated_at_human }}

```dataview
TABLE
  client as Cliente,
  status as " ",
  animo as Ánimo,
  score as Progreso,
  alerts as Alertas
FROM "KAIROS/Dashboard/Portafolio"
SORT score ASC
```

{{ client_rows }}

## 🚨 Alertas Activas
![[KAIROS/Alertas/_inbox.md]]

---

> [!tip] Priorización
> Los clientes están ordenados por score ascendente (menor progreso primero).
