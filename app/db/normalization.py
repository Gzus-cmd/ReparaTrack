"""Normalización de nombres de catálogo en un único lugar.

`trim` + colapso de espacios + `casefold` es la regla que impide duplicados
por mayúsculas o espacios (RF-01); semilla y repositorios la reutilizan.
"""

from __future__ import annotations


def normalize_name(value: str) -> str:
    """Devuelve la forma canónica de un nombre para comparar duplicados."""
    if not isinstance(value, str):
        raise TypeError(f"El nombre debe ser texto, se recibió {value!r}.")
    return " ".join(value.split()).casefold()
