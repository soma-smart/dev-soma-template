"""Abstract repositories.

One file per aggregate. The class name is the unsuffixed stereotype
(``UserRepository``), not ``UserRepositoryPort``. Concrete implementations
live in ``infrastructure/persistence/<entity>_repository.py`` and are prefixed
by mechanism (``SqlAlchemyUserRepository``).
"""
