---
tags: [kairos/alerta, {{ nivel }}]
cliente: "{{ cliente_id }}"
tipo: "{{ tipo }}"
nivel: "{{ nivel }}"
accion: "{{ accion }}"
created: "{{ created_at }}"
---

{{ icon }} # Alerta: {{ tipo_human }}

> [!danger] {{ mensaje }}

**Acción recomendada:** ` {{ accion }} `

**Cliente:** ` [[{{ cliente_nombre }}]] `

---

*Generado por KAIROS — {{ created_at_human }}*
