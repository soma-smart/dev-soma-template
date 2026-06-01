"""Authentication contracts (CurrentUser, TokenVerifier).

Auth identity is intentionally separate from the ``User`` entity. A user
of the service is identified by the IdP-issued token; the User business
entity is whatever the project models. The two may overlap or not.
"""
