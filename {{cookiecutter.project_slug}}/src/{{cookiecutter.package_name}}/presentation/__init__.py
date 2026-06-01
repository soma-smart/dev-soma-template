"""Presentation layer.

Delivery mechanisms: FastAPI routes, Pydantic schemas, error handlers,
middlewares, optional CLI. Imports `application` (and `domain` for types).
Never imports `infrastructure` directly — concretes are injected via the
DI container exposed through FastAPI `Depends`.
"""
