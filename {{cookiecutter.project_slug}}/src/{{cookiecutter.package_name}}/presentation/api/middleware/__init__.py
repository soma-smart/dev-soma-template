"""Application middlewares."""

from {{ cookiecutter.package_name }}.presentation.api.middleware.security_headers import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
