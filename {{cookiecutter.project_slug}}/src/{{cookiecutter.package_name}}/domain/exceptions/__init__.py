"""Domain exceptions.

All exceptions raised by the domain inherit from DomainError. Subclasses
carry a machine-readable code and human-readable message. The HTTP mapping
lives in presentation/api/error_handlers.py and is enforced by a test that
iterates DomainError.__subclasses__().
"""

from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError

__all__ = ["DomainError"]
