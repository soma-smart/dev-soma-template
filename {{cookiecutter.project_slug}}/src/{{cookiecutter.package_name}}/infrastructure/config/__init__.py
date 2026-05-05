"""Application configuration."""

from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
