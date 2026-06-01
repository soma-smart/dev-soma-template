{% raw %}# Swagger UI OAuth2 / Authorization Code flow

## TL;DR — local Keycloak (devcontainer)

Projects generated with `swagger_auth_scheme=oauth2_auth_code` ship a local Keycloak inside the devcontainer (`.devcontainer/docker-compose.yml`, realm `dev` auto-imported from `.devcontainer/keycloak/realm-export.json`). `.env.example` is already wired to it.

1. Open the devcontainer — Postgres, Keycloak and the API start automatically.
2. Run `just dev`, visit `http://localhost:8000/docs`.
3. Click **Authorize** → the browser redirects to `http://localhost:8080`.
4. Log in as **`alice` / `alice`** (regular user) or **`admin` / `admin`** (admin role).
5. Swagger UI receives the token and uses it on every subsequent call.

Keycloak admin console is at `http://localhost:8080`, admin/admin. Tokens issued from the `dev` realm carry `aud=api`, which `AUTH_JWT_AUDIENCE=api` in `.env` validates.

The rest of this document explains the underlying mechanism and how to point at Azure AD / Auth0 / a managed Keycloak in staging.

---

## Switching schemes

By default the API ships with the **HTTPBearer** Swagger UI scheme:
click "Authorize", paste a JWT, every subsequent request is
authenticated. Functional but every dev has to obtain a token elsewhere
first (curl + a refresh script, an internal portal, …).

When the IdP supports OpenID Connect (Azure AD / Entra ID, Auth0,
Keycloak, Okta, AWS Cognito, …) you can switch to the **Authorization
Code + PKCE** flow: clicking "Authorize" in `/docs` redirects the
browser to the IdP, the dev logs in with their SSO, and Swagger UI
receives the token back automatically.

The code already supports both schemes — flipping is a matter of
setting four env vars (see below) plus registering a dedicated app for
Swagger UI on your IdP.

## How the switch works

`presentation/api/dependencies/auth.py::_build_security_scheme` reads
the settings at startup:

- `SWAGGER_OAUTH2_AUTHORIZATION_URL` and `SWAGGER_OAUTH2_TOKEN_URL`
  both set → the API publishes the `OAuth2AuthorizationCodeBearer`
  scheme in its OpenAPI document.
- `SWAGGER_OAUTH2_CLIENT_ID` set → `app.py` configures Swagger UI with
  `swagger_ui_init_oauth` so the Authorize button knows which client to
  identify as.

Restart the API after changing the env vars.

## env vars

```env
SWAGGER_OAUTH2_AUTHORIZATION_URL=<IdP authorize endpoint>
SWAGGER_OAUTH2_TOKEN_URL=<IdP token endpoint>
SWAGGER_OAUTH2_CLIENT_ID=<dedicated Swagger UI app/client id>
SWAGGER_OAUTH2_SCOPES=openid,email,profile
SWAGGER_OAUTH2_PKCE_ENABLED=true
```

## App registration walkthrough — Azure AD / Microsoft Entra ID

1. **Open Azure portal** → Azure Active Directory → *App registrations* →
   *New registration*.
2. **Name**: `<your-service-name>-swagger-ui` (this is a DIFFERENT app
   from the one that backs your API audience — keep them separate so
   Swagger UI can be a public client without compromising your API
   secret).
3. **Supported account types**: pick the same audience as your API
   (single tenant typically).
4. **Redirect URI**:
   - Platform: **Single-page application**.
   - URI: `https://<your-api-host>/docs/oauth2-redirect`. For local dev
     add `http://localhost:8000/docs/oauth2-redirect` as well.
5. **Register**. Note the *Application (client) ID* — this is your
   `SWAGGER_OAUTH2_CLIENT_ID`.
6. **API permissions** → *Add a permission* → select your API app →
   pick the scopes your API expects (typically `openid`, `email`,
   `profile`, plus any custom scope you defined). Grant admin consent
   if required by tenant policy.
7. **Manifest** → confirm `accessTokenAcceptedVersion = 2` (v2.0
   tokens carry `email` and `name` claims when the matching scopes are
   granted).
8. **Authentication** → *Implicit grant and hybrid flows*: leave both
   checkboxes UNCHECKED. SPA + PKCE replaces them.

### Settings to put in your `.env`

```env
AUTH_JWT_ALGORITHM=RS256
AUTH_JWT_JWKS_URL=https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys
AUTH_JWT_AUDIENCE=<your-api-app-id>      # NOT the Swagger UI app id
AUTH_JWT_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0

SWAGGER_OAUTH2_AUTHORIZATION_URL=https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize
SWAGGER_OAUTH2_TOKEN_URL=https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token
SWAGGER_OAUTH2_CLIENT_ID=<swagger-ui-app-id>
SWAGGER_OAUTH2_SCOPES=openid,email,profile
SWAGGER_OAUTH2_PKCE_ENABLED=true
```

## App registration walkthrough — other IdPs (short notes)

### Auth0

- *Applications* → *Create Application* → *Single Page Application*.
- Allowed Callback URLs: `https://<api>/docs/oauth2-redirect`.
- `SWAGGER_OAUTH2_AUTHORIZATION_URL`: `https://<tenant>.auth0.com/authorize`.
- `SWAGGER_OAUTH2_TOKEN_URL`: `https://<tenant>.auth0.com/oauth/token`.
- The API itself is registered separately under *APIs* — its
  *Identifier* is your `AUTH_JWT_AUDIENCE`.

### Keycloak

- Create a *Public* client (SPA).
- Valid Redirect URIs: `https://<api>/docs/oauth2-redirect`.
- `SWAGGER_OAUTH2_AUTHORIZATION_URL`:
  `https://<host>/realms/<realm>/protocol/openid-connect/auth`.
- `SWAGGER_OAUTH2_TOKEN_URL`:
  `https://<host>/realms/<realm>/protocol/openid-connect/token`.
- Audience mapping is configured on the API client.

### Okta

- *Applications* → *Create App Integration* → *OIDC* + *Single-Page
  Application*.
- Sign-in redirect URIs: `https://<api>/docs/oauth2-redirect`.
- Authorize / Token URLs come from the org's authorization server.

## Verifying the flow

1. Start the API with the OAuth2 env vars set.
2. Open `https://<api>/docs`.
3. Click **Authorize** — Swagger UI shows the OAuth2 scopes; tick the
   ones you need and click **Authorize** again.
4. Browser redirects to the IdP login page, you authenticate, the IdP
   redirects back to `/docs/oauth2-redirect`, Swagger UI captures the
   token.
5. From now on, "Try it out" attaches the token to every request.

## Troubleshooting

- **Redirect URI mismatch** — the IdP rejects the callback. Verify the
  URL registered on the IdP exactly matches
  `<api-url>/docs/oauth2-redirect` (including the scheme).
- **PKCE not supported** — Set `SWAGGER_OAUTH2_PKCE_ENABLED=false`. Use
  only with non-public clients ; SPAs MUST keep PKCE.
- **Audience / issuer rejected** — verify the JWT inspector at the IdP
  shows `aud = <your-api-app-id>` and `iss = <your-tenant-issuer>`.
- **`AUTH_MISSING_PROFILE_CLAIMS`** on `/v1/users/me` — the IdP is not
  emitting `email` / `name`. Grant the `email` and `profile` scopes on
  the API permissions side of the Swagger UI app.
{% endraw %}