# SOMA Python Template v2 — Design Spec

- **Date** : 2026-05-05
- **Auteur** : Vianney Bacoup (`hgaillard@soma-smart.com`)
- **Statut** : Draft (en attente de relecture utilisateur)
- **Repo** : `dev-soma-template`
- **Branche cible** : `main`

---

## 1. Contexte et objectifs

Le repo `dev-soma-template` est aujourd'hui un squelette Python minimal (uv, ruff, mypy, pre-commit basique, 3 workflows CI). Il sert de point de départ pour les nouveaux projets SOMA mais ne dicte ni l'architecture, ni les conventions de test, ni les pratiques d'observabilité, ni l'environnement de développement.

**Objectif v2** : transformer ce template en un **générateur Cookiecutter** qui produit un projet Python "state-of-the-art" prêt à coder, avec des **garde-fous multi-couches** (skills Claude, hooks Claude Code, pre-commit, git hooks, CI) qui rendent **techniquement difficile** de coder en dehors des conventions définies.

**Cibles d'usage** :
1. Nouveau projet SOMA → `cookiecutter dev-soma-template` → projet utilisable en moins de 5 minutes.
2. Nouveau dev sur un projet généré → onboarding sans tribal knowledge, conventions visibles dès `git clone`.
3. Claude (n'importe quelle session) → conventions imposées via skills, hooks et CLAUDE.md, pas via mémoire.

**Critères de succès** :
- Un dev qui n'a jamais vu SOMA ouvre le projet généré dans VSCode, lance "Reopen in Container", et a une stack qui tourne (FastAPI + Postgres + Jaeger + traces visibles).
- Une PR qui viole une convention SOMA (import tiers en `domain/`, fonction > 25 lignes, test sans GIVEN/WHEN/THEN, DomainError sans mapping HTTP, mutation score < 90%) est **bloquée mécaniquement** avant le merge.
- Une session Claude vierge sur un projet généré applique les conventions sans qu'on lui rappelle.

---

## 2. Scope et non-goals

### In scope
- Migration `dev-soma-template` → générateur Cookiecutter
- Stack backend : FastAPI 0.115+, SQLAlchemy 2.0 async, asyncpg, Alembic, Pydantic Settings
- Architecture : Clean Architecture stricte (4 couches Uncle Bob)
- Tooling : uv, ruff (ruleset étendu), `ty` (Astral) en remplacement de mypy, mutmut, pytest, testcontainers
- Observabilité : structlog + OpenTelemetry (auto-switch console/OTLP)
- Containerisation : Dockerfile prod (Pattern 1 multi-stage), devcontainer séparé, docker-compose stack dev complète
- Déploiement : chart Helm multi-environnement avec hook Alembic
- Garde-fous Claude Code : `CLAUDE.md`, `.claude/settings.json` (permissions + hooks), skills versionnées
- Garde-fous Git : pre-commit étendu, commit-msg, pre-push
- CI/CD : workflows GitHub Actions (qualité, sécurité, mutation, helm, conventional commits, release)
- Versioning : SemVer + Commitizen + CHANGELOG auto

### Out of scope (explicite)
- Frontend / SDK clients
- Authentification ready-to-use (laissé aux projets ; le template fournit l'emplacement et un exemple de middleware)
- I18n du payload user-facing (codes machine-readable + messages EN par défaut ; chaque projet branche son catalogue)
- Stack monitoring complète (Prometheus/Grafana hors templates) — le chart expose un `ServiceMonitor` optionnel mais le cluster est supposé fournir l'ingestion
- Workflows multi-services / monorepo

---

## 3. Architecture du repo template (Cookiecutter)

```
dev-soma-template/
├── README.md                              # doc du template, comment générer un projet (EN)
├── CLAUDE.md                              # règles pour l'IA qui modifie LE TEMPLATE (EN)
├── cookiecutter.json                      # variables d'instanciation
├── hooks/
│   ├── pre_gen_project.py                 # validation des inputs (slug, python version)
│   └── post_gen_project.py                # git init, uv sync, pre-commit install, .env from .env.example
├── tests/                                 # tests du template lui-même (pytest-cookies)
│   ├── conftest.py
│   └── test_template_bake.py              # bake avec différents combos de variables, lance ruff/ty/pytest dessus
├── docs/
│   └── superpowers/specs/                 # ce document et autres specs
└── {{cookiecutter.project_slug}}/         # le projet généré (voir §4)
```

### Variables Cookiecutter

```jsonc
{
  "project_name": "My SOMA Service",
  "project_slug": "{{ cookiecutter.project_name|lower|replace(' ', '-') }}",
  "package_name": "{{ cookiecutter.project_slug|replace('-', '_') }}",
  "project_description": "Short one-line description.",
  "author_name": "SOMA",
  "author_email": "team@soma-smart.com",
  "python_version": "3.13",
  "database": ["postgres", "sqlite", "none"],
  "include_helm": ["yes", "no"],
  "include_otel": ["yes", "no"],
  "include_cli": ["no", "yes"],
  "license": ["proprietary", "MIT", "Apache-2.0"]
}
```

`pre_gen_project.py` valide :
- `package_name` matche `^[a-z][a-z0-9_]+$`
- `python_version` ∈ `{3.13, 3.14}`
- Combinaisons impossibles bloquées (ex: `database=none` + use case d'exemple persisté → erreur explicite)

`post_gen_project.py` exécute :
1. Suppression conditionnelle des dossiers (si `include_helm=no`, `rm -rf helm/`)
2. `git init && git add . && git commit -m "feat: initial commit from soma template v2"`
3. `uv sync --group dev`
4. `cp .env.example .env`
5. `uv run pre-commit install --install-hooks --hook-type commit-msg --hook-type pre-push`
6. Affichage d'un message de fin avec les 5 commandes essentielles

### Tests du template

`pytest-cookies` génère le projet avec 3 combinaisons (`postgres+helm+otel`, `sqlite+no-helm+otel`, `none+no-helm+no-otel`) puis exécute dessus :
- `uv run ruff check .`
- `uv run ty check src/`
- `uv run pytest -m unit`
- `helm lint helm/<slug>` (si `include_helm=yes`)

Ces tests tournent dans un workflow CI dédié au repo template (`ci-template.yml`).

---

## 4. Architecture du projet généré

### Layout

```
{{project_slug}}/
├── README.md                              # EN, court : 5 commandes essentielles + lien docs/
├── CLAUDE.md                              # routeur skills + règles courtes (EN)
├── .env.example                           # toutes les vars documentées, valeurs vides ou placeholders
├── pyproject.toml                         # deps + config ruff/ty/pytest/mutmut/commitizen
├── uv.lock
├── Dockerfile                             # prod multi-stage (builder + runtime), Pattern 1
├── alembic.ini
├── docker-compose.yml                     # stack dev (delegation depuis .devcontainer/docker-compose.yml)
├── .python-version
├── .gitignore
├── .pre-commit-config.yaml
├── .commitizen.toml                       # ou section dans pyproject.toml
│
├── .claude/
│   ├── settings.json                      # permissions + hooks (versionné)
│   ├── hooks/
│   │   ├── pre-commit-gate.sh
│   │   ├── pre-push-gate.sh
│   │   ├── audit-edit.sh
│   │   └── inject-context.sh
│   └── skills/                            # cf. §15
│
├── .devcontainer/
│   ├── devcontainer.json
│   ├── docker-compose.yml                 # app + postgres + jaeger + otel-collector
│   └── Dockerfile                         # FROM mcr.microsoft.com/devcontainers/python:3.13 + uv
│
├── .github/
│   ├── workflows/
│   │   ├── ci-quality.yml                 # ruff, ty, pytest unit/integration/e2e (parallèle)
│   │   ├── ci-security.yml                # bandit, pip-audit, gitleaks
│   │   ├── ci-mutation.yml                # mutmut sur domain+application, seuil 90%
│   │   ├── ci-helm.yml                    # helm lint + kubeconform + polaris
│   │   ├── ci-conventional-commits.yml    # validation messages
│   │   └── release.yml                    # semver bump + changelog + image push
│   ├── ISSUE_TEMPLATE.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
│
├── docs/
│   ├── architecture.md                    # diagramme couches + règle de dépendance (référence unique)
│   └── adr/
│       ├── 0001-clean-architecture.md
│       ├── 0002-tdd-and-mutation-testing.md
│       └── 0003-fakes-only-in-unit-tests.md
│
├── helm/
│   └── {{project_slug}}/                  # cf. §13
│
├── alembic/
│   ├── env.py                             # async Alembic (cf. §8)
│   ├── script.py.mako
│   └── versions/
│
├── scripts/
│   └── checks/
│       └── quality.sh                     # commande partagée pre-commit / Claude hook
│
├── src/
│   └── {{package_name}}/
│       ├── domain/
│       │   ├── entities/                  # User, Order, etc. (classes avec identité)
│       │   ├── value_objects/             # Email, Money, etc. (frozen dataclasses)
│       │   └── exceptions/                # DomainError + sous-classes par bounded context
│       ├── application/
│       │   ├── use_cases/                 # 1 fichier = 1 use case, classe `…UseCase`
│       │   ├── repositories/              # interfaces abstraites (UserRepository, …)
│       │   ├── clock.py                   # abstract Clock
│       │   ├── id_generator.py            # abstract IdGenerator
│       │   ├── random_source.py           # abstract RandomSource
│       │   ├── event_bus.py               # abstract EventBus
│       │   ├── audit_log.py               # abstract AuditLog
│       │   └── dtos/                      # …Input / …Output dataclasses
│       ├── infrastructure/
│       │   ├── persistence/
│       │   │   ├── models/                # SQLAlchemy ORM (UserModel, …)
│       │   │   ├── user_repository.py     # SqlAlchemyUserRepository(UserRepository)
│       │   │   └── session.py             # async engine + session factory
│       │   ├── http_clients/              # clients externes typés
│       │   ├── observability/
│       │   │   ├── tracing.py             # OTel setup + @traced decorator
│       │   │   └── logging.py             # structlog config + processors OTel
│       │   ├── config/
│       │   │   └── settings.py            # Pydantic BaseSettings, validation au boot
│       │   ├── clock.py                   # SystemClock(Clock)
│       │   ├── id_generator.py            # Uuid4IdGenerator(IdGenerator)
│       │   └── container.py               # factories pures (build_*) → cf. §9
│       └── presentation/
│           └── api/
│               ├── app.py                 # FastAPI factory, instrumentations OTel
│               ├── v1/                    # routers par version
│               │   └── users.py
│               ├── schemas/               # Pydantic …Schema (request/response DTOs)
│               ├── dependencies/          # Depends(...) qui wrappent le container
│               ├── middleware/            # SecurityHeaders, RequestId, etc.
│               └── error_handlers.py      # DomainError → HTTPResponse mapping
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── domain/                        # entités, value objects, exceptions
│   │   └── application/                   # use cases, FAKES uniquement
│   ├── integration/
│   │   └── infrastructure/                # repos avec testcontainers, clients HTTP
│   ├── e2e/
│   │   └── api/                           # 1 happy + 1 erreur critique par endpoint
│   └── fakes/
│       ├── clock.py                       # FrozenClock
│       ├── id_generator.py                # SequentialIdGenerator
│       ├── random_source.py               # SeededRandomSource
│       └── repositories/                  # InMemoryUserRepository, …
│
└── examples/
    └── feature_user_signup/               # feature de référence COMPLÈTE traversant les 4 couches
        # Documenté dans CLAUDE.md comme "lis ça avant d'ajouter ta première feature"
```

### Règle de dépendance (Clean Architecture)

```
presentation  ──→  application  ──→  domain
                       ↑
infrastructure  ───────┘
       │
       └──────────────→ domain (types only)
```

- `domain/` : aucune dépendance tierce ; pas de side-effect non-déterministe (datetime.now(), uuid4(), random) — utilise les abstractions correspondantes (Clock, IdGenerator, RandomSource).
- `application/` : importe `domain/` uniquement.
- `infrastructure/` : importe `domain/` et `application/`.
- `presentation/` : importe `application/` et `domain/` (types). **Jamais** d'import direct de `infrastructure/` ; les implémentations sont injectées via le container.

**Enforcement** :
- `flake8-tidy-imports` (via ruff) configuré pour interdire les imports cross-couches violant la règle
- Skill `clean-architecture-layers` (description normative)
- `audit-edit.sh` Claude hook qui flag toute violation à l'édition
- Test pytest qui parse les imports du `src/` et vérifie la règle (anti-régression)

---

## 5. Conventions de domaine

### Types
- **Argent / quantités précises** : `decimal.Decimal`. `float` interdit dans `domain/` et `application/`. Lint custom détecte les annotations `float` dans ces couches.
- **Datetimes** : tous TZ-aware, stockés en UTC. `datetime.now()` interdit dans `domain/application` (utilise `Clock`). Dans `infrastructure/presentation`, `datetime.now(tz=UTC)` obligatoire ; un `datetime.now()` nu est rejeté par lint custom.
- **Identifiants** : value objects typés (`UserId`, `OrderId`) wrappant un `UUID`. Pas de `str` ni `UUID` nu en signature publique.

### Value Objects
- `@dataclass(frozen=True, slots=True)`
- Validation dans `__post_init__`, lève des `DomainError` typées
- Égalité par valeur (héritée du `@dataclass`)

### Entities
- Classes régulières (pas `@dataclass`)
- Identité explicite par attribut `id: <Type>Id`
- `__eq__` et `__hash__` basés sur `id` uniquement
- Mutables, mais les transitions d'état passent par des méthodes nommées (`order.cancel()`, pas `order.status = "cancelled"`)

### Enums
- `enum.StrEnum` pour les états/types métier persistés
- `typing.Literal` pour les narrow types ad-hoc dans les signatures

### DTOs (`application/dtos/`)
- `@dataclass(frozen=True, slots=True)` strict
- Suffixes `…Input` (entrée use case), `…Output` (retour use case)
- Pas de logique, uniquement des données

### Exceptions
- Toutes héritent de `domain/exceptions/base.py::DomainError(code: str, context: dict[str, Any])`
- Une sous-classe par cas métier (`UserAlreadyExistsError`, `InsufficientBalanceError`)
- `code` machine-readable (SCREAMING_SNAKE), utilisé dans la réponse HTTP user-facing
- Test exhaustif itère `DomainError.__subclasses__()` et vérifie qu'une entrée existe dans `presentation/api/error_handlers.py::ERROR_HTTP_MAPPING`

---

## 6. Conventions de nommage (Uncle Bob strict)

### Règles globales (skill `naming-conventions` + ruff `N` + lint custom)
- **Intention-revealing** : pas d'abréviations (`usr`, `cnt`, `tmp`)
- **Pas d'encodages de type** : pas de `I` préfixe, pas de Hungarian, pas de `m_`
- **Un mot par concept** : `get_*` (lookup local), `find_*` (peut retourner `None`), `load_*` (I/O explicite). Vocabulaire fixé par la skill.
- **Class = noun phrase, method = verb phrase**
- **Booléens** : `is_*`, `has_*`, `can_*`. Pas de négation dans le nom.
- **Constantes** : `SCREAMING_SNAKE_CASE`, regroupées dans `constants.py` par module. Magic numbers interdits (ruff `PLR2004`).
- **Modules interdits** : `Utils`, `Helpers`, `Common`, `Misc`, `Manager`, `Processor`, `Service` (générique)

### Stéréotypes reconnus pour les abstractions

Whitelist livrée dans la skill `naming-conventions`. Si un de ces stéréotypes correspond, on l'utilise sans suffixe `Port` :

`Repository`, `Gateway`, `Bus`, `Sender`, `Publisher`, `Subscriber`, `Generator`, `Source`, `Provider`, `Reader`, `Writer`, `Factory`, `Strategy`, `Validator`, `Cache`, `Log`, `Clock`, `Lock`, `Mutex`.

Le suffixe `Port` est autorisé **uniquement** si aucun stéréotype ne convient ; la classe doit alors porter une docstring justifiant le choix.

### Use cases
- Suffixe `UseCase` **obligatoire** (rappel explicite du rôle archi)
- Méthode publique : `async def execute(self, input: …Input) -> …Output:`
- 1 fichier = 1 use case

### Implementations concrètes
- Préfixées par mécanisme : `SqlAlchemyUserRepository`, `SystemClock`, `Uuid4IdGenerator`, `RedisEventBus`, `StripeRefundGateway`
- Suffixées si elles sont des fakes de test : `InMemoryUserRepository`, `FrozenClock`, `SequentialIdGenerator`, `SeededRandomSource` (toutes dans `tests/fakes/`)

### Schémas et modèles
- Pydantic (presentation) : suffixe `Schema` → `UserCreateSchema`, `UserReadSchema`, `ErrorResponseSchema`
- SQLAlchemy (infrastructure) : suffixe `Model` → `UserModel`, `OrderModel`

### Fichiers et dossiers
- Snake_case pour fichiers et modules
- Pluriel pour collections : `use_cases/`, `entities/`, `repositories/`
- Singulier pour concept-module : `clock.py`, `container.py`, `app.py`

### Tests
- Fichiers : `test_<sut_name>.py` mirroir de l'arborescence source
- Fonctions : `test_given_<context>_when_<action>_then_<expectation>` (cf. §10)

---

## 7. Style et lint (ruff étendu + ty)

### Ruleset ruff (`pyproject.toml`)

```toml
[tool.ruff.lint]
select = [
  "E", "F", "I", "B", "S",      # base actuelle
  "UP",                          # pyupgrade
  "ANN",                         # annotations obligatoires
  "ARG",                         # args inutilisés
  "RET",                         # returns explicites
  "SIM",                         # simplifications
  "TCH",                         # TYPE_CHECKING imports
  "PTH",                         # pathlib
  "T20",                         # no print
  "ERA",                         # no commented-out code
  "RUF",                         # ruff-specific
  "C90",                         # cyclomatic complexity
  "D",                           # docstrings (Google)
  "PL",                          # pylint subset
  "N",                           # PEP8 naming
  "TID",                         # tidy imports (cross-layer enforcement)
]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D", "S101", "ANN"]   # docstrings + assert + annotations relâchés en test
"alembic/versions/*" = ["D", "ERA"]
```

### Lints custom (scripts dans `scripts/checks/`)
- `no_third_party_in_domain.py` : grep AST des imports dans `src/<pkg>/domain/`, échoue si une dépendance non-stdlib est importée
- `no_naive_datetime.py` : détecte `datetime.now()` sans `tz=` argument hors tests
- `no_float_in_domain.py` : détecte annotations `float` dans `domain/` et `application/`
- `domain_error_mapping.py` : (test pytest) itère `DomainError.__subclasses__()` et vérifie `ERROR_HTTP_MAPPING`
- `test_naming.py` : valide `test_given_*_when_*_then_*` + corps GIVEN/WHEN/THEN

### `ty` (Astral)
- Mode strict, équivalent `mypy --strict`
- `# ty: ignore` interdit sans commentaire-justification (regex ruff)
- Generics PEP 695 (`def foo[T](x: T) -> T:`) — `TypeVar` legacy interdit (lint custom)

### Limites de fonction
- 25 lignes max (corps, hors signature et docstring) — vérifié par lint custom (pas de plugin ruff officiel pour cette limite)

---

## 8. Base de données et migrations

### Stack
- **SQLAlchemy 2.0 async** (Core + ORM)
- **asyncpg** driver
- **Alembic async** (`script.py.mako` configuré pour `async def upgrade/downgrade`)

### Pattern
- Modèles ORM dans `infrastructure/persistence/models/` — **jamais** exposés hors `infrastructure/`
- Repos dans `infrastructure/persistence/<entity>_repository.py` implémentent les abstractions de `application/repositories/`
- Mapping `Entity ↔ Model` explicite dans le repo (méthodes privées `_to_entity`, `_to_model`)
- Session async injectée via le container DI ; FastAPI `Depends(get_session)` ouvre une session par requête, fermée en fin de cycle

### Migrations
- Génération : `uv run alembic revision --autogenerate -m "add_users_table"`
- Skill `database-and-migrations` impose la **lecture humaine** de la révision générée
- `downgrade()` non-vide obligatoire (lint custom qui parse les versions)
- Test d'intégration `test_migrations_round_trip.py` qui fait `upgrade head → downgrade base → upgrade head` sur testcontainers Postgres

### Pool
- `DB_POOL_SIZE` env (default 10), `DB_POOL_MAX_OVERFLOW` (default 5), `DB_POOL_TIMEOUT` (default 30s) — exposés dans `Settings`

---

## 9. Dependency Injection

### Pattern : container léger maison + Depends FastAPI

`infrastructure/container.py` expose des **factories pures** (fonctions Python, pas de framework DI) :

```python
def build_user_repository(session: AsyncSession) -> UserRepository:
    return SqlAlchemyUserRepository(session)

def build_create_user_use_case(
    users: UserRepository,
    clock: Clock,
    ids: IdGenerator,
) -> CreateUserUseCase:
    return CreateUserUseCase(users=users, clock=clock, ids=ids)
```

`presentation/api/dependencies/users.py` wrappe en `Depends` :

```python
async def get_session() -> AsyncIterator[AsyncSession]: ...

def get_clock() -> Clock:
    return SystemClock()

def get_id_generator() -> IdGenerator:
    return Uuid4IdGenerator()

def get_user_repository(s: AsyncSession = Depends(get_session)) -> UserRepository:
    return build_user_repository(s)

def get_create_user_use_case(
    users: UserRepository = Depends(get_user_repository),
    clock: Clock = Depends(get_clock),
    ids: IdGenerator = Depends(get_id_generator),
) -> CreateUserUseCase:
    return build_create_user_use_case(users=users, clock=clock, ids=ids)
```

**Avantages** :
- Aucune dépendance externe
- Le container marche aussi en CLI / worker (sans FastAPI)
- En test, on remplace les factories ou on instancie directement avec des fakes
- Lecture immédiate par n'importe quel dev / Claude

---

## 10. Stratégie de test

### Pyramide

```
tests/
├── unit/           # FAST, FIRST strict, mutation testing target
│   ├── domain/
│   └── application/
├── integration/    # tests sur infra réelle (testcontainers)
│   └── infrastructure/
├── e2e/            # FastAPI bootée + DB test
│   └── api/
└── fakes/          # implémentations in-memory des abstractions
```

### Règles par couche

| Couche | Doubles autorisés | Cible |
|---|---|---|
| `unit/domain/` | aucun (code pur) | invariants, value objects, exceptions |
| `unit/application/` | **Fakes uniquement** (zéro Mock, zéro Spy, zéro Stub) | toutes les branches métier des use cases |
| `integration/infrastructure/` | **Vrai** système via testcontainers (Postgres, Redis…) ; Mock **uniquement** pour SaaS externe non self-hostable | contrat de l'implémentation concrète |
| `e2e/api/` | **Vrai** stack via httpx.AsyncClient + DB test | wiring (route → DI → use case → response). **1 happy + 1 erreur critique par endpoint maximum.** |

### Anti-duplication e2e (règle explicite)
Si un use case a 12 branches métier, il a 12 tests unit et **1-2 tests e2e**. La skill `writing-tests` cite cette règle mot pour mot. Dépasser ce ratio = signal qu'il manque un test unit, pas qu'il manque des e2e.

### Format de test : GIVEN / WHEN / THEN strict

**Niveau 1 — nom de fonction** :
`test_given_<context>_when_<action>_then_<expectation>`

**Niveau 2 — corps** : 3 blocs commentés exactement, dans l'ordre, séparés par lignes vides :

```python
async def test_given_existing_email_when_creating_user_then_raises_user_already_exists():
    # GIVEN
    repo = InMemoryUserRepository(seed=[User(id=UserId.new(), email="a@b.com")])
    clock = FrozenClock(at=datetime(2026, 5, 5, tzinfo=UTC))
    use_case = CreateUserUseCase(users=repo, clock=clock, ids=SequentialIdGenerator())

    # WHEN / THEN
    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(CreateUserInput(email="a@b.com", name="Alice"))
```

- Tolérance `# WHEN / THEN` combiné **uniquement** avec `pytest.raises`
- Strict en `unit/` et `integration/`
- En `e2e/`, le GIVEN peut être implicite via fixture (la fixture nommée est le GIVEN partagé), `# WHEN` et `# THEN` toujours présents

**Enforcement** : script AST `scripts/checks/test_naming.py` lancé en pre-commit + dans `audit-edit.sh` Claude hook + en CI.

### Mutation testing

- **Outil** : `mutmut`
- **Scope** : `src/<pkg>/domain/` + `src/<pkg>/application/` uniquement
- **Seuils CI bloquants** :
  - Coverage lignes (pytest-cov) : ≥ 95% sur le scope ci-dessus
  - Mutation score : ≥ 90% sur le scope ci-dessus
- **Workflow CI** : `ci-mutation.yml` séparé, déclenché sur PR contre `main` ; publie un commentaire de PR avec le rapport ; bloque le merge si seuils non atteints
- **Cron hebdomadaire** : `mutmut` lancé sur `main`, échec → issue auto-créée

### Marqueurs pytest

```toml
[tool.pytest.ini_options]
markers = [
  "unit: pure unit tests, no I/O, no testcontainers",
  "integration: require testcontainers or external service mocks",
  "e2e: full stack via httpx.AsyncClient",
]
```

CI lance les 3 catégories en **jobs parallèles** pour temps de feedback minimum.

---

## 11. TDD (workflow imposé)

Skill `tdd-workflow` impose :

1. **Red** : écrire un test qui échoue (use case inexistant ou logique manquante). `uv run pytest -m unit` doit échouer sur ce test précis.
2. **Green** : code minimum pour passer le test. Pas de fonctionnalité non testée.
3. **Refactor** : nettoyage sans casser les tests.
4. **Mutate** : `uv run mutmut run --paths-to-mutate src/<pkg>/<modified-paths>` sur le périmètre touché. Mutants survivants → tests trop faibles → retour Red.

La skill **interdit explicitement** :
- D'écrire le code de production avant le test
- De skipper l'étape mutate quand on touche `domain/` ou `application/`
- De désactiver un test pour faire passer le CI ("fix the test, not the assertion")

### Hook injection
`inject-context.sh` détecte les prompts contenant "feature", "use case", "endpoint", "fix bug" et injecte un rappel : "use the `tdd-workflow` skill — write the failing test first."

---

## 12. Logs et observabilité

### Stack
- **structlog** comme façade unique
- **OpenTelemetry SDK** + auto-instrumentations
- **Sortie auto-switch** :
  - `OTEL_EXPORTER_OTLP_ENDPOINT` non défini → `ConsoleSpanExporter` (lisible en dev, ingerable via collecteur sidecar)
  - `OTEL_EXPORTER_OTLP_ENDPOINT` défini → `OTLPSpanExporter` (gRPC)
- **Format de log auto-switch** :
  - `LOG_FORMAT=console` (default si TTY) → console renderer coloré
  - `LOG_FORMAT=json` (default si non-TTY) → JSON structuré pour ingestion ops

### Instrumentations livrées
- `opentelemetry-instrumentation-fastapi`
- `opentelemetry-instrumentation-sqlalchemy`
- `opentelemetry-instrumentation-asyncpg`
- `opentelemetry-instrumentation-httpx`
- `opentelemetry-instrumentation-logging` (auto-injection `trace_id` / `span_id` dans structlog)

### Décorateur custom
`infrastructure/observability/tracing.py::traced(span_name: str)` ouvre un span avec attributs custom autour d'un use case ou d'une fonction d'infra :

```python
@traced("create_user")
async def execute(self, input: CreateUserInput) -> CreateUserOutput: ...
```

### Règles de logging (skill `observability-patterns`)
- **Aucun log dans `domain/`** ni `application/` (le domaine est muet ; les use cases laissent remonter les exceptions)
- Logger style **event-style** : `logger.info("user.created", user_id=str(user.id), email=user.email)` (pas de string interpolation)
- **Redaction automatique** : un structlog processor redacte les clés `password`, `token`, `authorization`, `*_secret`, `*_key`
- **Pas de `print`** (ruff `T20`)

### Sampling
- Dev / test : `always_on`
- Prod : `parentbased_traceidratio` configurable via `OTEL_TRACES_SAMPLER_ARG` (default 0.1)

---

## 13. Erreurs et exceptions

### Architecture
1. **Domain lève** des exceptions métier typées (sous-classes de `DomainError`), aucune référence à HTTP, aucun log.
2. **Application laisse remonter** (ou wrappe en cas d'enrichissement nécessaire).
3. **Presentation** a un exception handler central :

```python
# presentation/api/error_handlers.py
ERROR_HTTP_MAPPING: dict[type[DomainError], int] = {
    UserAlreadyExistsError: 409,
    UserNotFoundError: 404,
    InsufficientBalanceError: 402,
    # ...
}

@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    logger.warning(
        "domain_error",
        code=exc.code,
        context=exc.context,
        path=request.url.path,
    )
    status = ERROR_HTTP_MAPPING.get(type(exc), 500)
    return JSONResponse(
        status_code=status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    trace_id = get_current_trace_id()
    logger.exception("unexpected_error", trace_id=trace_id)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": f"Contact support with trace {trace_id}"}},
    )
```

### Tests d'enforcement
- `test_all_domain_errors_have_http_mapping.py` : itère `DomainError.__subclasses__()` et échoue si une sous-classe n'a pas d'entrée dans `ERROR_HTTP_MAPPING`
- Skill `adding-a-domain-exception` rappelle : "ajoute toujours l'entrée mapping HTTP, sinon le test bloque la CI"

---

## 14. Containerisation

### Pattern 1 : Dockerfile prod multi-stage (séparé du devcontainer)

`Dockerfile` racine (utilisé par Helm) :

```dockerfile
# ─── builder ────────────────────────────────────────
FROM python:3.13-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ─── runtime ────────────────────────────────────────
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends tini ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --no-create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app src/ /app/src/
COPY --chown=app:app alembic/ /app/alembic/
COPY --chown=app:app alembic.ini /app/
USER app
EXPOSE 8000
ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "{{package_name}}.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Devcontainer Dockerfile (séparé, court)

`.devcontainer/Dockerfile` :

```dockerfile
FROM mcr.microsoft.com/devcontainers/python:3.13
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
USER vscode
```

L'image MS gère déjà : `vscode` user, `git`, `sudo`, common-utils, mises à jour de sécurité, support Codespaces.

### `.devcontainer/devcontainer.json`

```jsonc
{
  "name": "{{project_name}}",
  "dockerComposeFile": "docker-compose.yml",
  "service": "app",
  "workspaceFolder": "/workspaces/${localWorkspaceFolderBasename}",

  "remoteUser": "vscode",
  "updateRemoteUserUID": true,

  "containerEnv": { "TZ": "Europe/Paris" },

  "mounts": [
    "source=${localEnv:HOME}/.gitconfig,target=/home/vscode/.gitconfig,type=bind,readonly",
    "source=${localEnv:HOME}/.ssh,target=/home/vscode/.ssh,type=bind,readonly"
  ],

  "postCreateCommand": "uv sync --group dev && uv run pre-commit install --install-hooks --hook-type commit-msg --hook-type pre-push",
  "postStartCommand": "uv run alembic upgrade head",

  "customizations": {
    "vscode": {
      "extensions": ["charliermarsh.ruff", "ms-python.python", "tamasfe.even-better-toml"]
    }
  }
}
```

### `.devcontainer/docker-compose.yml`

Lance `app` (build local depuis `.devcontainer/Dockerfile`), `postgres:17`, `jaegertracing/all-in-one`, `otel/opentelemetry-collector` ; volumes nommés persistants pour PG ; network commun ; env vars pré-câblées vers ces services.

### Compatibilité

| Environnement | Comportement |
|---|---|
| Linux local | `updateRemoteUserUID: true` rebuild `vscode` avec UID/GID hôte → fichiers édités dans le container appartiennent à l'hôte, éditables hors container |
| macOS local | Docker Desktop fait sa traduction → fonctionne avec `vscode:1000` |
| GitHub Codespaces | Image MS supportée nativement, `vscode` user reconnu, GitHub auth auto-injectée |

---

## 15. Helm

### Scope (cf. §2 — pas de subcharts DB/OTel)

```
helm/{{project_slug}}/
├── Chart.yaml
├── values.yaml                    # défauts documentés
├── values.schema.json             # schéma JSON validé par helm + skills Claude
├── values-dev.yaml
├── values-staging.yaml
├── values-prod.yaml               # 3 replicas, HPA, PDB, resources tunées
├── templates/
│   ├── _helpers.tpl
│   ├── deployment.yaml            # probes liveness/readiness/startup, securityContext non-root
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml             # OTEL_EXPORTER_OTLP_ENDPOINT, LOG_FORMAT, DB_POOL_SIZE, …
│   ├── secret.yaml                # template, secrets externes via External Secrets ou values
│   ├── hpa.yaml
│   ├── pdb.yaml
│   ├── serviceaccount.yaml
│   ├── servicemonitor.yaml        # optionnel via .Values.metrics.enabled
│   └── migration-job.yaml         # Helm hook pre-install/pre-upgrade : alembic upgrade head
└── tests/
    └── test-connection.yaml       # helm test
```

### Hook migrations
`migration-job.yaml` est annoté `helm.sh/hook: pre-install,pre-upgrade` et `helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded`. Lance l'image avec `["alembic", "upgrade", "head"]`. Désactivable via `migrations.enabled: false`.

### CI Helm (`ci-helm.yml`)
1. `helm lint helm/{{project_slug}}`
2. `helm template helm/{{project_slug}} -f helm/{{project_slug}}/values-prod.yaml | kubeconform -strict -summary`
3. `helm template ... | polaris audit --audit-path -`
4. `helm template ...` against schema (auto si `values.schema.json` présent)

---

## 16. Configuration et secrets

### Pydantic Settings

`infrastructure/config/settings.py` :

```python
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")

    # App
    app_name: str = "{{project_name}}"
    log_format: Literal["console", "json"] = "console"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Database
    db_url: SecretStr = Field(...)
    db_pool_size: int = 10
    db_pool_max_overflow: int = 5

    # Observability
    otel_exporter_otlp_endpoint: str | None = None
    otel_traces_sampler_arg: float = 0.1
    service_name: str = "{{package_name}}"

    # Security
    cors_allowed_origins: list[str] = []
```

- `extra="forbid"` : toute env var inconnue échoue le boot
- Les champs sans default sont obligatoires ; un boot sans eux crash explicitement
- `SecretStr` pour les secrets : leur `repr()` est masqué, leur valeur n'apparaît jamais dans les logs

### `.env.example` (versionné)
Toutes les variables documentées avec valeurs vides ou placeholders. `.env` (gitignored) auto-créé par `post_gen_project.py`.

---

## 17. Intégration Claude Code

### `CLAUDE.md` (racine du projet généré, EN)
Routeur vers les skills, court (< 200 lignes). Structure :
- Project context (1 paragraphe)
- Stack list
- "When you do X, use skill Y" table
- Hard rules (non-négociables, ex: "never mock in unit tests", "never log in domain")
- Pointer vers `docs/architecture.md` et `examples/`

### `.claude/settings.json` (versionné)

```jsonc
{
  "permissions": {
    "deny": [
      "Bash(git push --force*)",
      "Bash(git push --force-with-lease*)",
      "Bash(git commit --no-verify*)",
      "Bash(git rebase --no-verify*)",
      "Bash(rm -rf*)",
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/secrets/**)"
    ],
    "ask": [
      "Bash(alembic downgrade*)",
      "Bash(helm upgrade*)",
      "Bash(helm install*)",
      "Bash(kubectl delete*)",
      "Bash(uv remove*)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash(git commit*)",  "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-commit-gate.sh", "timeout": 60 }] },
      { "matcher": "Bash(git push*)",    "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-push-gate.sh", "timeout": 120 }] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write", "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/audit-edit.sh" }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/inject-context.sh" }] }
    ]
  }
}
```

### Hooks Claude (`.claude/hooks/`)

| Script | Event | Action | Bloquant |
|---|---|---|---|
| `pre-commit-gate.sh` | `PreToolUse(Bash git commit)` | Lance `scripts/checks/quality.sh` (ruff + ty + pytest -m unit + lints custom) | Oui (`exit 2` si échec) |
| `pre-push-gate.sh` | `PreToolUse(Bash git push)` | Lance `pytest -m unit -m integration` | Oui |
| `audit-edit.sh` | `PostToolUse(Edit/Write)` | Détecte : import tiers dans `domain/`, nouvelle `DomainError` sans entrée mapping, nouveau use case sans test, violation du format GIVEN/WHEN/THEN, `datetime.now()` nu, `float` en domain | Warning fort (la 2e ligne reste pre-commit/CI) |
| `inject-context.sh` | `UserPromptSubmit` | Détection mots-clés (feature/use case/bug/migration) → injection rappel skill correspondante | Non (enrichissement) |

`scripts/checks/quality.sh` est l'entrée unique partagée par : pre-commit local (Claude hook), pre-commit framework (`.pre-commit-config.yaml` invoque ce script), CI.

---

## 18. Skills livrées dans `.claude/skills/`

14 skills, chacune dans son dossier avec `SKILL.md` (frontmatter `name`, `description`, `when_to_use`) :

| Skill | Trigger |
|---|---|
| `onboarding-soma` | session vierge, prompt sur la structure du projet |
| `clean-architecture-layers` | quand on parle de "where to put", "which layer", "import" |
| `writing-domain-code` | édition dans `src/<pkg>/domain/` |
| `tdd-workflow` | "feature", "fix", "use case", "bug" |
| `adding-a-use-case` | "add a use case", "new endpoint" |
| `adding-a-domain-exception` | "new error", "exception" |
| `writing-tests` | édition dans `tests/`, ou prompt "write a test" |
| `writing-a-fake` | édition dans `tests/fakes/` |
| `using-the-di-container` | édition `infrastructure/container.py` ou `presentation/api/dependencies/` |
| `database-and-migrations` | "migration", "schema", "alembic" |
| `observability-patterns` | "logging", "tracing", "metrics", édition `infrastructure/observability/` |
| `naming-conventions` | toute création de classe/fonction/module |
| `writing-a-helm-change` | édition dans `helm/` |
| `reviewing-a-pr-soma-style` | "review", "PR" |

---

## 19. Pre-commit étendu

`.pre-commit-config.yaml` :

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: detect-private-key
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: ty
        name: ty (type check)
        entry: uv run ty check src/
        language: system
        pass_filenames: false
      - id: quality-checks
        name: SOMA quality checks
        entry: bash scripts/checks/quality.sh
        language: system
        pass_filenames: false
      - id: pytest-unit
        name: pytest unit (fast)
        entry: uv run pytest -m unit
        language: system
        pass_filenames: false
        stages: [pre-push]

  - repo: https://github.com/zricethezav/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks

  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.30.0
    hooks:
      - id: commitizen
        stages: [commit-msg]
```

Installation auto via `post_gen_project.py` : `pre-commit install --install-hooks --hook-type commit-msg --hook-type pre-push`.

---

## 20. CI/CD

### Workflows

| Workflow | Trigger | Contenu |
|---|---|---|
| `ci-quality.yml` | PR | ruff check + ruff format + ty + pytest -m unit / -m integration / -m e2e (3 jobs parallèles) |
| `ci-security.yml` | PR | bandit + pip-audit + gitleaks |
| `ci-mutation.yml` | PR + cron hebdo | mutmut sur domain+application, seuils 90% mutation / 95% coverage |
| `ci-helm.yml` | PR (path-filtered `helm/**`) | helm lint + kubeconform + polaris |
| `ci-conventional-commits.yml` | PR | regex sur tous les commits (existant) |
| `release.yml` | push tag `v*` | commitizen bump → changelog → docker build (target runtime) → push GHCR → GitHub Release |

### Versioning
- **SemVer** strict
- **Commitizen** : `uv run cz bump` automatise tag + version pyproject + CHANGELOG
- Push de tag `v*` déclenche `release.yml`

---

## 21. Garde-fous : matrice à 4 niveaux

| Niveau | Mécanisme | Quand ça tape | Contournable ? |
|---|---|---|---|
| **1a. Contexte permanent Claude** | `CLAUDE.md` auto-loaded | À chaque session | Faible (instruction) |
| **1b. Contexte ciblé Claude** | Skills déclenchées par sujet | Quand le contexte matche | Moyenne (instruction structurée) |
| **1c. Contexte injecté Claude** | Hook `UserPromptSubmit` | Au prompt utilisateur | Moyenne |
| **1d. Vrai blocage Claude** | `permissions.deny` + hooks `exit 2` | Tentative d'action interdite | Forte (Claude ne peut pas passer) |
| **2. pre-commit** | `.pre-commit-config.yaml` | `git commit` (humain ou Claude) | `--no-verify` interdit côté Claude (deny rule) ; humain doit explicitement bypass |
| **3. Git hooks** | `commit-msg` (commitizen), `pre-push` (pytest unit) | `git commit` / `git push` | Idem |
| **4. CI GitHub Actions** | Workflows | Sur PR | Aucun (bloque le merge) |

Pour chaque règle clé, **au moins 2 niveaux** la couvrent :

| Règle | Niveau(x) qui l'enforcent |
|---|---|
| Pas d'import tiers dans `domain/` | 1b (skill) + 1c (rappel auto) + 1d (audit-edit warning) + 2 (lint custom pre-commit) + 4 (CI) |
| Format GIVEN/WHEN/THEN dans tests | 1b + 1d + 2 (test_naming.py) + 4 |
| DomainError → mapping HTTP | 1b + 1d (audit-edit) + 4 (test pytest) |
| Mutation score ≥ 90% | 4 (ci-mutation.yml) |
| Conventional commits | 1b + 3 (commitizen commit-msg) + 4 (ci-conventional-commits) |
| Pas de `--no-verify` | 1d (deny rule) + culture humaine |
| Function ≤ 25 lignes | 1b + 2 (lint custom) + 4 |
| Pas de `datetime.now()` nu | 1d (audit-edit) + 2 (lint custom) + 4 |

---

## 22. Onboarding flow

### Humain (1er jour)
1. `git clone` le projet
2. Ouvre dans VSCode → "Reopen in Container" → stack complète up (FastAPI + PG + Jaeger + OTel)
3. Lit `README.md` (EN, court) : 5 commandes essentielles + lien `docs/architecture.md`
4. Lit `docs/architecture.md` (1 diagramme couches + règle de dépendance)
5. Ouvre `examples/feature_user_signup/` : feature complète qui traverse les 4 couches, sert de référence
6. Lance `uv run pytest` : tout passe → environnement validé

### Claude (1ère session)
1. Auto-load `CLAUDE.md`
2. Si prompt vierge → skill `onboarding-soma` activée (présente l'archi en ASCII + pointe vers `examples/`)
3. À chaque action, hooks veillent

---

## 23. Déroulé d'implémentation (haut niveau)

L'implémentation détaillée vit dans le **plan** qui suit ce spec (skill `writing-plans`). Vue d'ensemble du séquencement :

1. **Cookiecutter scaffolding** : structure `{{cookiecutter.project_slug}}/`, variables, hooks, tests pytest-cookies de base
2. **pyproject.toml** : deps prod (FastAPI, SQLAlchemy, OTel, structlog, …) + dev (pytest, mutmut, ty, ruff, testcontainers, commitizen)
3. **Couches Clean Archi** : structure de dossiers + `__init__.py` + abstractions de base (Clock, IdGenerator, RandomSource, EventBus, AuditLog, DomainError)
4. **Settings + observability** : Pydantic Settings, structlog, OTel setup, decorator `@traced`
5. **Persistence** : SQLAlchemy async, Alembic config async, migration squelette
6. **DI container** : `infrastructure/container.py` + `presentation/api/dependencies/`
7. **FastAPI app** : `presentation/api/app.py`, error handlers, middlewares
8. **Tests** : conftest, fakes (FrozenClock, SequentialIdGenerator, SeededRandomSource, InMemoryUserRepository), markers
9. **Feature de référence** dans `examples/feature_user_signup/` (entité, value objects, use case, repo, route, schémas, tests unit/integration/e2e)
10. **Lints custom** : `scripts/checks/*.py` + intégration pre-commit + Claude `audit-edit.sh`
11. **Pre-commit + git hooks** : config étendue + commitizen
12. **Dockerfile prod** + **devcontainer** (Dockerfile + docker-compose + devcontainer.json)
13. **Helm chart** complet
14. **CI workflows** : quality, security, mutation, helm, conventional-commits, release
15. **Claude integration** : `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/`, 13 skills
16. **Docs** : `README.md`, `docs/architecture.md`, ADRs (3 livrés)
17. **Tests du template** (pytest-cookies) : 3 combos × bake + ruff/ty/pytest

---

## 24. Décisions à figer plus tard (parking)

- Choix de la lib Pydantic v2 d'i18n des messages user-facing (out of scope v2, à définir si un projet le demande)
- Politique de rétention des releases GHCR
- Décision sur `slowapi` (rate limiting) : code en place mais désactivé par défaut, ou complètement absent ?
- Stratégie de test contre les `httpx` clients externes (VCR.py vs respx vs pytest-httpx) — actuellement non tranchée pour le template
- Comportement si `database=none` : la feature de référence en `examples/` étant persistée, soit on bloque le combo `database=none` au `pre_gen_project`, soit on introduit une variable `include_example` séparée et on génère un exemple non-persisté minimaliste. À trancher au moment du plan d'implémentation.
- Mécanisme exact pour interdire `# ty: ignore` sans justification : règle ruff custom via `ruff` `RUF100`-style ne couvre pas `ty`, donc probablement un check regex maison dans `scripts/checks/` invoqué en pre-commit. Détail d'implé.

---

## 25. Critères d'acceptation du template v2

Le template est livrable quand :

1. `cookiecutter dev-soma-template` produit un projet en < 30 secondes
2. Sur le projet généré, `uv sync && uv run pytest` passe (tous les markers : unit, integration, e2e)
3. `uv run mutmut run --paths-to-mutate src/<pkg>/domain,src/<pkg>/application` donne mutation score ≥ 90% sur la feature de référence
4. `uv run ruff check . && uv run ty check src/` passe
5. `helm lint helm/<slug> && helm template helm/<slug> | kubeconform -strict` passe
6. "Reopen in Container" sur VSCode lance app + PG + Jaeger ; `curl localhost:8000/health` répond ; trace visible sur `localhost:16686`
7. `uv run pre-commit run --all-files` passe
8. Une PR de test qui viole une règle (ajout d'`import requests` dans `domain/`) est rejetée par pre-commit OU par CI
9. Tests pytest-cookies du repo template passent sur les 3 combos de variables
10. Une session Claude vierge sur le projet généré, avec prompt "ajoute un endpoint pour lister les utilisateurs", produit du code conforme aux conventions sans rappel manuel
