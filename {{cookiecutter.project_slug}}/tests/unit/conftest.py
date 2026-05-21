"""Unit-layer conftest.

Reserved for fixtures that are only meaningful in unit tests (Fakes-only,
no I/O, no FastAPI app). Currently empty: ``frozen_clock``,
``sequential_ids``, ``seeded_random``, ``user_repository`` and
``ensure_user_exists_use_case`` live in the root conftest because both
unit tests and e2e tests use them. Add unit-only fixtures here as the
project grows.
"""
