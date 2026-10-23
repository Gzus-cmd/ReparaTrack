"""Esquemas de clientes (RF-02)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    """Alta de cliente con contacto mínimo obligatorio."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120, description="Nombre del cliente.")
    phone: str = Field(min_length=1, max_length=30, description="Teléfono de contacto.")
    email: str | None = Field(default=None, max_length=120, description="Correo opcional.")
    document: str | None = Field(default=None, max_length=20, description="Documento opcional.")


class CustomerUpdate(BaseModel):
    """Actualización parcial del contacto."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=120)
    document: str | None = Field(default=None, max_length=20)


class CustomerRead(BaseModel):
    """Cliente con su contacto registrado."""

    id: int
    name: str
    phone: str
    email: str | None
    document: str | None
    created_at: datetime


class CustomerPage(BaseModel):
    """Página de clientes con el total de coincidencias."""

    items: list[CustomerRead]
    total: int
