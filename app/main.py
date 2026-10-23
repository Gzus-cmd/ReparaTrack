"""Punto de entrada de la aplicación (ASGI).

Arranque: `py -m uvicorn app.main:app --reload`.
"""

from __future__ import annotations

from app.api.app import create_app
from app.db.seed import seed_catalogs

app = create_app()

# Siembra idempotente de los maestros base ("Diagnóstico" incluido) para que la
# aplicación quede usable desde el primer arranque, sin pasos manuales.
with app.state.session_factory() as session:
    seed_catalogs(session)
    session.commit()
