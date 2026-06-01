"""Persistence concretes (SQLAlchemy 2.0 async).

ORM models live under ``models/`` and are NEVER exposed outside this package.
Repositories implement the abstractions declared in
``application/repositories/`` and translate between domain entities and ORM
models in private ``_to_entity`` / ``_to_model`` helpers.
"""
