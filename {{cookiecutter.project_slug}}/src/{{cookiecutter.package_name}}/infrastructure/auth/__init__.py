"""Production auth bindings.

Currently ships :class:`JwtTokenVerifier` (HS256 or RS256 + JWKS). Swap by
editing :func:`{{ cookiecutter.package_name }}.infrastructure.container.build_token_verifier`.
"""
