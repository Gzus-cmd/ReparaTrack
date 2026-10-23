"""Configuración de la aplicación: umbrales de negocio y base de datos.

`Settings` es un objeto inmutable con valores por defecto tomados de la spec
(90/180/30 días) y `from_env()` permite sobrescribirlos por entorno, de modo
que los tests usan SQLite en memoria sin tocar la base real (NFR-05).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./reparatrack.db"

DEFAULT_WARRANTY_DAYS = 90
DEFAULT_ABANDONMENT_DAYS = 180
DEFAULT_APPROVAL_DAYS = 30


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    """Lee un entero positivo del entorno, o devuelve el valor por defecto."""
    raw = environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un entero, se recibió {raw!r}.") from exc
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero, se recibió {value}.")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuración tipada del sistema."""

    database_url: str = DEFAULT_DATABASE_URL
    warranty_days: int = DEFAULT_WARRANTY_DAYS
    abandonment_days: int = DEFAULT_ABANDONMENT_DAYS
    approval_days: int = DEFAULT_APPROVAL_DAYS

    def __post_init__(self) -> None:
        if not self.database_url.strip():
            raise ValueError("DATABASE_URL no puede estar vacío.")
        for field_name in ("warranty_days", "abandonment_days", "approval_days"):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} debe ser mayor que cero.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Construye la configuración leyendo variables de entorno."""
        source = os.environ if environ is None else environ
        database_url = (source.get("DATABASE_URL") or DEFAULT_DATABASE_URL).strip()
        return cls(
            database_url=database_url,
            warranty_days=_positive_int(source, "WARRANTY_DAYS", DEFAULT_WARRANTY_DAYS),
            abandonment_days=_positive_int(source, "ABANDONMENT_DAYS", DEFAULT_ABANDONMENT_DAYS),
            approval_days=_positive_int(source, "APPROVAL_DAYS", DEFAULT_APPROVAL_DAYS),
        )
