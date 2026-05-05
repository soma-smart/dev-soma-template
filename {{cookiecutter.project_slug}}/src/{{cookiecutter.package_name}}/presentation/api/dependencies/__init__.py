"""FastAPI ``Depends`` wiring around the infrastructure container.

Each dependency is a thin wrapper that pulls the required collaborator from
``infrastructure/container.py``. Tests override these via
``app.dependency_overrides`` to inject fakes.
"""

from {{ cookiecutter.package_name }}.presentation.api.dependencies.common import (
    get_clock,
    get_id_generator,
    get_random_source,
    get_session,
    get_settings_dependency,
)

__all__ = [
    "get_clock",
    "get_id_generator",
    "get_random_source",
    "get_session",
    "get_settings_dependency",
]
