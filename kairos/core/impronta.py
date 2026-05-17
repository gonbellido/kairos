from pydantic import BaseModel, Field


class Impronta(BaseModel):
    directividad: float = Field(default=0.5, ge=0.0, le=1.0)
    emocionalidad: float = Field(default=0.5, ge=0.0, le=1.0)
    analiticidad: float = Field(default=0.5, ge=0.0, le=1.0)
    riesgo: float = Field(default=0.5, ge=0.0, le=1.0)

    formalidad: float = Field(default=0.5, ge=0.0, le=1.0)
    proactividad: float = Field(default=0.5, ge=0.0, le=1.0)
    estructura: float = Field(default=0.5, ge=0.0, le=1.0)
    personalizacion: float = Field(default=0.5, ge=0.0, le=1.0)

    extra: dict[str, float] = Field(default_factory=dict)

    def update(self, overrides: dict) -> "Impronta":
        data = self.model_dump()
        data.update(overrides)
        return Impronta(**data)


class ImprontaConstraints(BaseModel):
    min: Impronta
    max: Impronta

    def clamp(self, impronta: Impronta) -> Impronta:
        clamped = {}
        for field in impronta.model_fields_set:
            val = getattr(impronta, field)
            if isinstance(val, (int, float)):
                min_val = getattr(self.min, field, 0.0)
                max_val = getattr(self.max, field, 1.0)
                clamped[field] = max(min_val, min(max_val, val))
        return impronta.update(clamped)
