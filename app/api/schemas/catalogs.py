"""Esquemas de los cuatro maestros (RF-01)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CatalogValueRead(BaseModel):
    """Valor de maestro con su estado y su uso actual."""

    id: int = Field(description="Identificador del valor.")
    name: str = Field(description="Nombre visible del valor.")
    is_active: bool = Field(description="Falso cuando el valor fue dado de baja lógica.")
    in_use: bool = Field(description="Verdadero cuando algún registro referencia el valor.")


class CatalogValueWrite(BaseModel):
    """Cuerpo de alta y renombrado de un valor de maestro."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80, description="Nombre del valor.")
