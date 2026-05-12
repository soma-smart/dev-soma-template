---
name: adding-auth
description: How bearer-JWT auth is wired and how to protect a route. Covers the seams (CurrentUser, TokenVerifier, dependencies), the swap path to a real IdP (HS256 → RS256 + JWKS), the role-based authz helper, and how tests inject identities without signing real tokens.
when_to_use: Protecting a new route; adding a role check; debugging a 401/403; swapping from the default HS256 secret to a real IdP (Keycloak, Auth0, Okta, Cognito); editing presentation/api/dependencies/auth.py or infrastructure/auth/jwt_verifier.py.
---

# Adding auth

## The chain

```
Authorization: Bearer <token>
   ↓ get_bearer_token          → MissingTokenError (401)
   ↓ get_current_user          → InvalidTokenError (401)
   ↓ require_roles(...)        → InsufficientPermissionsError (403)
   ↓
 your handler
```

Files involved:

| Layer | File | Role |
|---|---|---|
| application | `application/auth/current_user.py` | `CurrentUser` value object (subject, email, roles, claims) |
| application | `application/auth/token_verifier.py` | `TokenVerifier` Protocol |
| domain | `domain/exceptions/auth.py` | `MissingTokenError`, `InvalidTokenError`, `InsufficientPermissionsError` |
| infrastructure | `infrastructure/auth/jwt_verifier.py` | `JwtTokenVerifier` — HS256 or RS256+JWKS |
| presentation | `presentation/api/dependencies/auth.py` | `get_bearer_token`, `get_current_user`, `get_current_user_optional`, `require_roles` |
| presentation | `presentation/api/v1/auth.py` | Reference endpoint `GET /v1/auth/whoami` |

## Protecting a route

### Authentication only

```python
from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.presentation.api.dependencies.auth import get_current_user

@router.get("/v1/profile")
async def read_profile(user: CurrentUser = Depends(get_current_user)) -> ProfileResponse:
    ...
```

### Authentication + role check

Use the dependency factory `require_roles(...)`. It runs `get_current_user` first, then validates membership. Pass roles as positional arguments; **at least one** must match (OR semantics, not AND).

```python
from {{ cookiecutter.package_name }}.presentation.api.dependencies.auth import require_roles

@router.delete(
    "/v1/users/{user_id}",
    dependencies=[Depends(require_roles("admin"))],   # no need to receive the user
)
async def delete_user(user_id: UUID, use_case: ... = Depends(...)) -> None:
    ...

# Or, when the handler needs the user object:
async def archive_user(
    user_id: UUID,
    user: CurrentUser = Depends(require_roles("admin", "moderator")),
) -> None:
    ...
```

### Optional auth (anonymous or authenticated)

```python
from {{ cookiecutter.package_name }}.presentation.api.dependencies.auth import get_current_user_optional

@router.get("/v1/feed")
async def feed(user: CurrentUser | None = Depends(get_current_user_optional)) -> FeedResponse:
    if user is None:
        return public_feed()
    return tailored_feed(user)
```

A malformed Authorization header still raises `MissingTokenError` — that is a client bug, not "anonymous".

## Configuration

All under the `AUTH_*` env vars (see `.env.example`):

| Variable | HS256 | RS256 | Notes |
|---|---|---|---|
| `AUTH_JWT_ALGORITHM` | `HS256` | `RS256` | Default `HS256` for dev / internal |
| `AUTH_JWT_SECRET` | **required** | unused | The shared secret. Pydantic-Settings wraps it in `SecretStr` |
| `AUTH_JWT_JWKS_URL` | unused | **required** | e.g. `https://auth.example.com/.well-known/jwks.json` |
| `AUTH_JWT_AUDIENCE` | optional | optional | Empty = no `aud` check |
| `AUTH_JWT_ISSUER` | optional | optional | Empty = no `iss` check |
| `AUTH_JWT_ROLES_CLAIM` | optional | optional | Dotted path — e.g. `realm_access.roles` for Keycloak |

## Swap path — from HS256 to a real IdP

For a real IdP (Keycloak, Auth0, Okta, AWS Cognito), the only changes you need are environment variables — no code change:

```env
AUTH_JWT_ALGORITHM=RS256
AUTH_JWT_JWKS_URL=https://<your-idp>/.well-known/jwks.json
AUTH_JWT_AUDIENCE=<your-api-audience>
AUTH_JWT_ISSUER=<your-idp-issuer-url>
AUTH_JWT_ROLES_CLAIM=realm_access.roles    # Keycloak
# AUTH_JWT_ROLES_CLAIM=https://your-namespace/roles  # Auth0 custom claim
```

`AUTH_JWT_SECRET` becomes unused under RS256 — the public keys are fetched from the JWKS URL and cached by `PyJWKClient`.

For a more invasive swap (mTLS, opaque tokens, IdP introspection endpoint), edit `infrastructure/auth/jwt_verifier.py` or replace it with a different binding in `infrastructure/container.build_token_verifier`. The `TokenVerifier` protocol is the only seam — nothing else changes.

## Tests

### Unit tests of an authenticated handler

Don't call the protected handler directly — instead test that the dependency wiring rejects bad input. The protected handler's body is best covered at the use-case level (no auth concerns) plus an e2e test (auth concerns).

### E2E test of a protected route

The e2e `client` fixture has the `TokenVerifier` overridden by `FakeTokenVerifier`. Register a token with `token_verifier.accept(...)` and send it as `Authorization: Bearer <token>`.

```python
def test_given_admin_token_when_calling_delete_then_returns_204(
    client: TestClient,
    token_verifier: FakeTokenVerifier,
) -> None:
    # GIVEN
    token_verifier.accept("admin-token", subject="alice", roles=("admin",))

    # WHEN
    response = client.delete("/v1/users/abc", headers={"Authorization": "Bearer admin-token"})

    # THEN
    assert response.status_code == 204
```

The `FakeTokenVerifier` lives in `tests/fakes/auth.py` — read it for the available helpers.

### Integration test of the production `JwtTokenVerifier`

Already shipped under `tests/integration/infrastructure/auth/test_jwt_verifier.py` (signs a JWT with PyJWT, verifies through the production binding). When you change the verifier (custom claims, audience policy, …), update or add tests there.

## Local dev — calling protected endpoints from curl

```bash
just dev-token alice                 # plain authenticated user, no roles
just dev-token alice admin,user      # with roles

# Then:
curl -H "Authorization: Bearer $(just dev-token alice admin)" \
  http://localhost:8000/v1/auth/whoami
```

The recipe mints an HS256-signed token good for one hour using your local `AUTH_JWT_SECRET`. It refuses to run if `AUTH_JWT_ALGORITHM != HS256` — production deployments are not expected to use it.

## Common mistakes

* **Forgetting `Depends(get_current_user)` in the handler signature.** Without it, the route is public — auth is opt-in.
* **Using `require_roles` without a current_user injection in the route.** Either pass it as `dependencies=[...]` or as the user parameter. Both are valid; using neither makes the dependency tree not include it.
* **Leaking the verification failure cause to the response.** The `InvalidTokenError` deliberately uses a generic message; the `context` lands in the structured warning log only. Do not change this without a security review.
* **Adding a new `DomainError` subclass for auth without an entry in `ERROR_HTTP_MAPPING`.** The error-mapping unit test will fail and the request will fall back to 500. Always add the status code in `presentation/api/error_handlers.py`.
* **Using `AUTH_JWT_SECRET` in prod.** HS256 is for dev / internal services. In prod, the IdP signs with its private key and the service verifies via JWKS — `AUTH_JWT_ALGORITHM=RS256`.
