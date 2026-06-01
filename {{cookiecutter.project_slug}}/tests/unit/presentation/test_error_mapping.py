"""The HTTP mapping is exhaustive over ``DomainError`` subclasses.

This test catches the case where a developer adds a new ``DomainError`` and
forgets to declare its HTTP status code in ``ERROR_HTTP_MAPPING``.
"""

from __future__ import annotations

import pytest

# Import representative modules so all subclasses are discovered.
from {{ cookiecutter.package_name }}.domain.exceptions import user as _user  # noqa: F401
from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError
from {{ cookiecutter.package_name }}.domain.value_objects import email as _email  # noqa: F401
from {{ cookiecutter.package_name }}.presentation.api.error_handlers import ERROR_HTTP_MAPPING


def _all_subclasses(cls: type) -> set[type]:
    seen: set[type] = set()
    stack: list[type] = list(cls.__subclasses__())
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(node.__subclasses__())
    return seen


@pytest.mark.unit
def test_given_all_domain_errors_when_inspecting_mapping_then_each_has_http_status() -> None:
    # GIVEN
    subclasses = _all_subclasses(DomainError)

    # WHEN
    missing = sorted(cls.__name__ for cls in subclasses if cls not in ERROR_HTTP_MAPPING)

    # THEN
    assert missing == [], (
        f"DomainError subclasses missing from ERROR_HTTP_MAPPING: {missing}. "
        "Add an entry in presentation/api/error_handlers.py."
    )
