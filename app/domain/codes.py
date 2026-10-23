"""Formato del código interno correlativo de equipos (RN-02).

`EQ-` más seis dígitos, independiente del `id` de la fila: el contador real
vive en la persistencia y aquí solo se formatea y se interpreta.
"""

from __future__ import annotations

CODE_PREFIX = "EQ-"
CODE_DIGITS = 6
MAX_SEQUENCE = 10**CODE_DIGITS - 1


def format_internal_code(sequence: int) -> str:
    """Devuelve el código interno para una secuencia correlativa positiva."""
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise TypeError(f"La secuencia debe ser un entero, se recibió {sequence!r}.")
    if sequence <= 0:
        raise ValueError("La secuencia del código interno debe ser mayor que cero.")
    if sequence > MAX_SEQUENCE:
        raise ValueError(f"La secuencia {sequence} desborda el formato de {CODE_DIGITS} dígitos.")
    return f"{CODE_PREFIX}{sequence:0{CODE_DIGITS}d}"


def parse_internal_code(code: str) -> int:
    """Interpreta un código interno y devuelve su secuencia correlativa."""
    if not isinstance(code, str):
        raise TypeError(f"El código interno debe ser texto, se recibió {code!r}.")

    normalized = code.strip().upper()
    digits = normalized[len(CODE_PREFIX) :]
    if not normalized.startswith(CODE_PREFIX) or len(digits) != CODE_DIGITS or not digits.isdigit():
        raise ValueError(f"Código interno inválido: {code!r}.")

    sequence = int(digits)
    if sequence <= 0:
        raise ValueError(f"Código interno inválido: {code!r}.")
    return sequence
