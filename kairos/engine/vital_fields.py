"""Vital fields registry — universal fields any journey can collect.

These fields automatically map to canonical client profile positions
when collected by any journey agent.
"""

# field_key → display metadata
VITAL_FIELDS: dict[str, dict] = {
    "nombre":           {"label": "Nombre",             "section": "identity",      "profile_key": "first_name"},
    "apellido":         {"label": "Apellidos",           "section": "identity",      "profile_key": "surname"},
    "fecha_nacimiento": {"label": "Fecha de nacimiento", "section": "identity",      "profile_key": "fecha_nacimiento"},
    "sexo":             {"label": "Sexo",                "section": "identity",      "profile_key": "sexo"},
    "lateralidad":      {"label": "Lateralidad",         "section": "identity",      "profile_key": "lateralidad"},
    "nacionalidad":     {"label": "Nacionalidad",        "section": "identity",      "profile_key": "nacionalidad"},
    "provincia":        {"label": "Provincia / Estado",  "section": "location",      "profile_key": "provincia"},
    "email":            {"label": "Email",               "section": "contact",       "profile_key": "email"},
    "telefono":         {"label": "Teléfono",            "section": "contact",       "profile_key": "phone"},
    "profesion":        {"label": "Profesión",           "section": "professional",  "profile_key": "job_title"},
    "empresa":          {"label": "Empresa",             "section": "professional",  "profile_key": "company"},
    "objetivo_principal": {"label": "Objetivo principal","section": "coaching",      "profile_key": "objetivo_principal"},
    "contexto":         {"label": "Contexto actual",     "section": "coaching",      "profile_key": "contexto"},
    "motivo_consulta":  {"label": "Motivo de consulta",  "section": "coaching",      "profile_key": "motivo_consulta"},
    "bloqueo_principal":{"label": "Bloqueo principal",   "section": "coaching",      "profile_key": "bloqueo_principal"},
}

# Aliases the LLM might use → canonical vital field key
FIELD_ALIASES: dict[str, str] = {
    "nombre_completo": "nombre",
    "name": "nombre",
    "first_name": "nombre",
    "full_name": "nombre",
    "last_name": "apellido",
    "surname": "apellido",
    "apellidos": "apellido",
    "birthday": "fecha_nacimiento",
    "birth_date": "fecha_nacimiento",
    "dob": "fecha_nacimiento",
    "gender": "sexo",
    "genero": "sexo",
    "handedness": "lateralidad",
    "nationality": "nacionalidad",
    "province": "provincia",
    "state": "provincia",
    "ciudad": "provincia",
    "city": "provincia",
    "phone": "telefono",
    "phone_number": "telefono",
    "celular": "telefono",
    "job_title": "profesion",
    "profession": "profesion",
    "occupation": "profesion",
    "company": "empresa",
    "organization": "empresa",
    "goal": "objetivo_principal",
    "main_goal": "objetivo_principal",
    "objetivo": "objetivo_principal",
    "context": "contexto",
    "mc": "motivo_consulta",
    "mcb": "motivo_consulta",
    "mcn": "motivo_consulta",
    "blocker": "bloqueo_principal",
    "bloqueo": "bloqueo_principal",
    "main_blocker": "bloqueo_principal",
}

SECTION_LABELS = {
    "identity": "Identidad",
    "location": "Ubicación",
    "contact": "Contacto",
    "professional": "Profesional",
    "coaching": "Coaching",
}


def normalize_collected(collected: dict) -> dict:
    """Resolve field aliases to canonical vital field names."""
    if not collected:
        return {}
    result = dict(collected)
    for alias, canonical in FIELD_ALIASES.items():
        if alias in result and alias != canonical:
            if canonical not in result or not result[canonical]:
                result[canonical] = result.pop(alias)
            else:
                result.pop(alias)
    return result


def extract_vital_fields(collected: dict) -> dict:
    """Return only the vital fields present in collected data (after normalization)."""
    normalized = normalize_collected(collected)
    return {k: v for k, v in normalized.items() if k in VITAL_FIELDS and v}


def group_vital_fields(vital: dict) -> dict[str, list[dict]]:
    """Group vital fields by section for display."""
    sections: dict[str, list] = {}
    for key, value in vital.items():
        meta = VITAL_FIELDS.get(key, {})
        section = meta.get("section", "other")
        sections.setdefault(section, []).append({
            "key": key,
            "label": meta.get("label", key.replace("_", " ").title()),
            "value": value,
        })
    return sections
