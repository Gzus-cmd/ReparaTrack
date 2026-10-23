"""Agregador de routers de la API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routers import catalogs, customers, equipments, health, service_orders

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(catalogs.router)
api_router.include_router(customers.router)
api_router.include_router(equipments.router)
api_router.include_router(service_orders.router)
