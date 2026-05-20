# SOMA Template — Validation Walkthrough (TodoList)

- **Date** : 2026-05-20
- **Auteur** : Vianney Bacoup (`hgaillard@soma-smart.com`)
- **Statut** : Terminé. Phases 1 et 2 exécutées intégralement ; Phase 3 (auth) a été re-lancée plus tard en scope ciblé après que le user a demandé une validation de la skill `adding-auth`.
- **Objectif** : Valider la configuration trimée du template (9 skills, 0 sub-agent) en construisant 3 features TodoList. Output principal = liste des frictions observées + propositions d'itération sur les skills.

---

## Contexte

Après le trim 2026-05-19 (`docs/superpowers/specs/2026-05-05-soma-template-v2-design.md` §24), le template ne ship plus de sub-agent. Le main agent exécute le flow complet end-to-end via le runbook `building-a-feature`.

Ce walkthrough teste cette configuration sur 3 features choisies pour couvrir les croisements typiques :

| Feature | Couvre |
|---|---|
| **Phase 1** — Create TodoList | Use case basique, uniqueness, event, persistence, route, mapping HTTP |
| **Phase 2** — Complete a Todo item | Méthode mutation sur entité existante, événement de domaine, idempotency middleware en pratique |
| **Phase 3** — Auth + scoping | `adding-auth` skill, multi-tenancy, `CurrentUser` collaborator |

L'objectif n'est PAS la livraison de TodoList. C'est de soumettre les skills à un usage réaliste et de documenter ce qui craque.

---

## Phase 0 — Setup

1. **Bake propre du template** :
   ```bash
   rm -rf /tmp/todo-validation
   uv run cookiecutter . --no-input -o /tmp/todo-validation project_name="Todo Api"
   ```
2. **Devcontainer up** (Docker requis) :
   ```bash
   cd /tmp/todo-validation/todo-api/.devcontainer/
   docker compose up -d
   ```
3. **Wrapper script** `/tmp/todo-validation/run.sh` pour exécuter du Python dans le container, avec les env vars de dev :
   ```bash
   #!/bin/bash
   set -euo pipefail
   exec docker compose \
     -f /tmp/todo-validation/todo-api/.devcontainer/docker-compose.yml \
     exec -T \
     -w /workspaces/todo-api \
     -e DB_URL=postgresql+asyncpg://app:app@postgres:5432/todo_api \
     -e AUTH_JWT_SECRET=dev-secret \
     -e TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal \
     app "$@"
   ```
4. **Smoke test** : `./run.sh just install && ./run.sh just test` doit passer sur le projet vierge (reference User feature).

**Critère de sortie Phase 0** : projet baké, container up, tests verts sur User feature.

---

## Phase 1 — Create TodoList

**Prompt user** (envoyé verbatim à l'agent principal) :

> *« Je veux pouvoir créer une TodoList, une seule par personne, avec un nom et une description »*

### Déroulé attendu (cf. `building-a-feature`)

1. Agent pose 4-6 questions de clarification depuis les packs (Scope, Uniqueness, Auth, Events, Errors, Out-of-scope).
2. User répond.
3. Agent produit le plan 5 sections (Tests / Abstractions BY ROLE / API surface / External contracts / Open questions).
4. User valide.
5. Agent exécute outside-in :
   - **Use case TDD** (`tests/unit/application/test_create_todo_list_use_case.py`) — outer test happy path → `ImportError` chain → minimum surface → green
   - Itérations red-green pour les rules : refuse duplicates, emits `todo_list.created`, validation des champs
   - **Persistence TDD** (`tests/integration/infrastructure/test_todo_list_repository.py`) — testcontainers PG
   - **Route TDD** (`tests/e2e/api/test_create_todo_list_endpoint.py`) — 1 happy + 1 critical
   - **Wiring** dans `infrastructure/container.py`
   - **Mutate** ≥ 90%
   - **Lint** final

### Critères de succès Phase 1

- [x] **91.7% mutation kill rate** sur domain + application (au-dessus du seuil 90%) — 121/132, 11 survivants principalement dans les classes de base pré-existantes (Entity/DomainError) + quelques context kwargs sémantiquement bénins.
- [x] Tests verts aux 3 niveaux : 22 unit use case + 7 integration + 2 e2e + reste = **101 tests verts**
- [x] `scripts/checks/test_naming.py tests/` passe (GIVEN/WHEN/THEN strict)
- [x] `scripts/checks/no_third_party_in_domain.py src/` passe
- [ ] `just lint` passe — **20 erreurs pré-existantes du template**, mais **aucune dans le code TodoList**. Cf. friction #4.
- [x] Domaine pur : aucun import `sqlalchemy`, `pydantic`, `fastapi` sous `domain/`
- [x] Le plan respecté après correction user : aucune classe / méthode Protocol / exception / champ pré-décidé dans le plan v2 final. Le plan v1 initial avait des leaks (cf. friction #6).

---

## Phase 2 — Complete a Todo item

**Prérequis** : Phase 1 verte. Une TodoList existe et a des items (donc on aura besoin d'enrichir l'entité TodoList avec des items en cours de Phase 2 — la première feature Phase 2 sera potentiellement "add item to list" pour atteindre l'état attendu).

**Prompt user** :

> *« Sur une TodoList, je veux pouvoir compléter un item. Ça doit émettre un event `todo_item.completed`, et l'endpoint doit être idempotent. »*

### Déroulé attendu

1. Questions (Auth, Events, Errors, Idempotency).
2. Plan.
3. Exécution outside-in.

### Critères de succès Phase 2

- [x] **93.9% mutation kill rate** sur domain + application (au-dessus du seuil 90%) — 229/244, 15 survivants pré-existants dans Entity/DomainError de base + quelques context kwargs.
- [x] Tests verts aux 3 niveaux : **137 tests** (51 unit + 10 integration + 4 e2e + reste)
- [x] Event publié AFTER le write (vérifié par les tests use case ToggleItem qui attestent ordre add → publish)
- [ ] **Test e2e idempotency-key replay : ÉCHEC** — `IdempotencyMiddleware` requiert `app.state.session_factory` qui n'est pas branché en e2e (le fixture client bypasse le lifespan exprès). Test retiré, le middleware reste couvert par `tests/integration/middleware/test_idempotency.py` (real PG via testcontainers). **Friction template** : pas évident à éviter sans changer le design du middleware ou le pattern e2e.
- [x] Pas de log direct dans `application/` ni `domain/`
- [x] L'entité TodoItem expose `complete(at=now)`, `uncomplete()`, et `is_completed` (property) — mutations via méthodes nommées, jamais d'assignation directe depuis l'extérieur

---

## Phase 3 — Auth + scoping (RÉ-OUVERTE 2026-05-20 soir)

**Décision initiale** : Phase 3 abandonnée pour capitaliser sur les frictions Phase 1+2. **Décision revue** : le user a demandé une validation de la skill `adding-auth` ; scope re-resserré sur "ajouter l'auth + ownership scoping sur les 3 endpoints TodoList existants".

### Scope exécuté

- **Refactor** : `AddTodoItemInput` et `ToggleTodoItemInput` gagnent un champ `caller_id: UserId`. `CreateTodoListInput` inchangé.
- **Use cases** : check ownership ajouté dans `AddTodoItem` et `ToggleTodoItem` (`if todo_list.owner_id != input.caller_id: raise TodoListNotFoundError(...)` — 404 uniforme).
- **Routes** : tous les 3 endpoints gagnent `Depends(get_current_user)`. `POST /v1/todo-lists` perd le champ `owner_id` du body (extrait du JWT). Les 2 endpoints d'item extraient `caller_id` du JWT subject.
- **Schemas** : `TodoListCreateSchema` perd le champ `owner_id`.
- **Tests** : 21 unit tests AddItem + ToggleItem refactored pour passer `caller_id`. +2 tests d'ownership (caller != owner → 404). +3 tests e2e (auth missing → 401, ownership 404).

### Critères de succès Phase 3

- [x] **142 tests verts** (101 Phase 1 + 36 Phase 2 + 5 nouveaux Phase 3 — auth + ownership)
- [x] Skill `adding-auth` lue + appliquée : pattern `Depends(get_current_user)` + `FakeTokenVerifier.accept(token, subject=...)` en e2e — flow fluide
- [x] Multi-tenancy 404-uniforme (pas de leak d'existence)
- [x] Domaine pur préservé (aucun import auth dans `domain/`)

### Frictions observées Phase 3

19. **Code des `DomainError` auth pas explicité dans la skill** — j'ai assumé `MISSING_TOKEN` comme code dans les tests, mais c'est `AUTH_MISSING_TOKEN` (avec le préfixe `AUTH_`). Pareil pour `AUTH_INVALID_TOKEN`. La skill `adding-auth` montre la classe (`MissingTokenError`) mais pas le `code` SCREAMING_SNAKE. Reco : ajouter une mini-table "Exception class → HTTP status → code" dans la skill.

20. **Cast `UUID(current_user.subject)` non couvert** — quand le `sub` claim n'est pas un UUID valide, `UUID(...)` raise un `ValueError` au route layer qui devient un 500. Pas de skill ne mentionne cette friction. Pour SOMA, deux options : (a) catcher le ValueError et raise `InvalidTokenError` ; (b) documenter dans `adding-auth` que les projets qui mappent `subject → UserId` doivent ajouter ce safety. Reco : documenter.

21. **DTO refactor mécanique non-trivial** — ajouter `caller_id` à 2 DTOs a forcé 30+ test edits. Le pattern "constante `_OWNER` au module level + `replace_all` sur le call de `Input(...)`" marche mais est verbeux. La skill `building-a-feature` pourrait mentionner cette technique pour les refactors auth post-coup.

### Positives Phase 3

22. **Fixture `FakeTokenVerifier` parfaitement adaptée** — `verifier.accept(token, subject=...)` + header `Authorization: Bearer <token>` est concis et lisible. Aucune friction de boilerplate.

23. **Mapping HTTP shippé dans le template** — `ERROR_HTTP_MAPPING` contient déjà `MissingTokenError → 401`, `InvalidTokenError → 401`, `InsufficientPermissionsError → 403`. Rien à ajouter pour les 3 endpoints.

24. **CurrentUser comme `ValueObject` immutable** — propre, frozen dataclass, conforme aux conventions SOMA. Pas de friction.

---

## Plan original (gardé pour référence)

**Prérequis** : Phases 1 & 2 vertes.

**Prompt user** :

> *« Toutes les routes TodoList doivent exiger un user authentifié. Un user ne voit / ne modifie que ses propres listes (404 si la liste appartient à quelqu'un d'autre). »*

### Déroulé attendu

1. Questions (Auth scheme, scoping rule, 404 vs 403, audit).
2. Plan.
3. Exécution.

Implique probablement :
- Lecture du skill `adding-auth`
- Ajout du `CurrentUser` collaborator dans les use cases existants
- Ajout d'une méthode Protocol `find_owned_by(owner_id, list_id) -> TodoList | None`
- Retest e2e avec un JWT forgé

### Critères de succès Phase 3

- [ ] Routes 401 si pas de JWT
- [ ] Routes 404 si liste appartient à un autre user (pas 403 — choix doc'd)
- [ ] Aucune route ne fuit l'info "cette liste existe mais n'est pas à toi"
- [ ] Mutation kill rate ≥ 90% sur les checks d'ownership

---

## Frictions observées Phase 1

### Bugs templates (à fixer au niveau template)

1. **Mutmut config invalide** — `[tool.mutmut]` dans `pyproject.toml` utilise `paths_to_mutate = "src/..."` (string) ET `tests_dir = "tests/unit"` (string). Mutmut 3.5+ exige des **listes** pour les deux. De plus `also_copy` manque → mutmut tente de copier `/sys/class/powercap/intel-rapl:1` et crash avec un FileNotFoundError opaque. Bug **déjà observé lors du walkthrough précédent**, toujours pas fixé. Fix template : `paths_to_mutate = ["src/.../domain", "src/.../application"]`, `tests_dir = ["tests/unit"]`, `also_copy = ["src/.../infrastructure", "src/.../presentation", "src/.../{__init__.py}", "tests", "pyproject.toml", "uv.lock", "alembic", "alembic.ini"]`.

2. **Autogenerate Alembic destructeur** — `alembic/env.py` n'importe que `Base` ; les modèles concrets sont chargés "par accident" via les imports des repositories. Quand on ajoute un nouveau modèle, soit on l'importe explicitement (sinon `Base.metadata` ne le voit pas et autogenerate ne crée rien), soit on l'importe via `models/__init__.py` mais alors il faut importer **tous** les autres modèles aussi sinon autogenerate génère des `drop_table` destructeurs sur les modèles oubliés. Fix template : importer **tous** les modèles dans `models/__init__.py` dès le bake initial (avec `# noqa: F401`).

3. **Drift modèles ↔ migrations existantes** — la migration `0001_init_users` crée un index ET un unique constraint séparés pour `email`, mais le `UserModel` déclare `unique=True, index=True` sur la colonne ce qui SQLAlchemy compile en un seul index unique. Autogenerate détecte la différence et propose de "fixer" — bruit dans toute future migration. Idem pour les indexes outbox (`ix_outbox_event_name` vs `ix_outbox_events_event_name`). Fix template : aligner les migrations existantes sur ce que les modèles déclarent.

4. **`just lint` échoue sur projet baké à J+0** — 20 lint errors out of the box, principalement S106 (mots `token`, `secret` dans les arguments de test) dans `tests/integration/`, `tests/unit/`, et quelques `B008` / `D` dans `infrastructure/auth/`, `infrastructure/jobs/`. Un nouveau projet SOMA ne passe pas son propre lint dès le départ. Fix template : soit corriger les erreurs (préférable), soit étendre le `[tool.ruff]` `lint.per-file-ignores` pour les tests.

5. **Stale Docker containers du walkthrough précédent** — `docker compose up -d` réutilisait les containers existants avec un mount workspace stale (`/workspaces/todo-api` pointant vers le précédent `/tmp/todo-validation/todo-api`). Le wrapper `run.sh` plantait avec `chdir: no such file or directory`. Fix workflow : documenter `docker compose down -v` avant tout nouveau bake. (À noter dans le runbook devcontainer ou le `Phase 0` d'un walkthrough.)

### Frictions skill / plan

6. **Main agent biased toward pre-deciding VOs in the plan** — le user a corrigé : "tu me poses des questions sur les VOs alors que c'est du domaine. C'est du TDD ça DOIT découler des tests". Le main agent a inclus dans le plan initial une section "Domain (drill)" avec des bullets sur "Le VO `name` rejette les entrées > 255 chars" — leak d'implémentation. La règle "use case-level only" est dans la skill `building-a-feature` mais n'a pas été appliquée correctement. **Confirme l'argument du user pour un sub-agent planner en contexte frais** (qui n'aurait pas l'accumulation de contexte qui biaise vers la pré-décision). Reco : envisager un sub-agent `soma-feature-planner` qui ne fait que produire le plan en contexte frais. Sauvé en mémoire feedback.

7. **Question pack "Out-of-scope" peu exploitée** — Phase 1 n'avait pas vraiment de scope à clarifier au-delà de "create only". Le pack F est sans doute plus utile en phase 2-3 quand le contexte accumulé créé des extensions tentantes. À revoir en fin de walkthrough.

### Positives (le template fait son job)

8. **`tests/unit/presentation/test_error_mapping.py`** détecte automatiquement les nouvelles `DomainError` sans entrée dans `ERROR_HTTP_MAPPING`. Garde-fou validé — j'ai été averti dès l'ajout des exceptions.

9. **`scripts/checks/no_third_party_in_domain.py`** + `test_naming.py` passent en silence quand le code respecte les conventions. Pas de friction observée.

10. **L'ImportError chain fonctionne** comme prévu — partir d'un test outer puis suivre les ImportErrors a produit la structure attendue (DTO → Protocol → Fake → entity → VO → use case body) en environ 15 minutes.

### Tooling

11. **Mutmut affichage TUI bruyant** — les spinners et compteurs en boucle saturent la sortie. Pas critique mais pas pratique pour log dans un PR.

12. **Mutmut "context kwargs" survivants** sont du bruit — quand `raise SomeError(length=N)` est muté en `raise SomeError(length=None)`, le test ne le détecte pas sauf si on assert sur `.context["length"]`. Ces mutations sont sémantiquement bénignes (le `context` sert uniquement aux logs), mais comptent dans le kill rate. À débattre : soit étendre les tests pour assert sur context (effort + verbosité), soit configurer mutmut pour ignorer ces mutations.

---

## Frictions observées Phase 2

### Bugs / gaps template

13. **Idempotency middleware non-testable en e2e** — comme noté ci-dessus, `IdempotencyMiddleware` lit `app.state.session_factory`, qui est setté par le FastAPI lifespan. Le fixture e2e `client` bypasse le lifespan pour éviter un vrai DB engine. Conséquence : un test e2e qui envoie deux fois la même `Idempotency-Key` voit le handler s'exécuter deux fois (le middleware log un warning `idempotency.no_session_factory` et by-pass). La doc skill `building-a-feature` § Idempotency suggère implicitement qu'on peut tester ça e2e, mais en pratique non. Reco : (a) documenter explicitement dans la skill que l'idempotency replay est validé via le test d'intégration du middleware seul, pas via les e2e de l'endpoint ; ou (b) ajouter un fixture `app_with_real_session_factory` pour les tests e2e qui veulent vraiment exercer le middleware.

14. **Unit-of-work pour aggregate avec collection imbriquée** — implémenter `Repository.save(todo_list)` qui réconcilie domain ↔ ORM avec les items nested a demandé non-trivial reasoning : eager-load via `selectinload`, diff items par id, update existants + insert nouveaux, configurer `cascade="all, delete-orphan"` + `lazy="selectin"` sur la relationship. La skill `building-a-feature` ne décrit pas ce pattern — elle suppose implicitement des aggregates "plats" comme User. Reco : ajouter une section "Aggregate avec children" dans la skill avec un exemple comme TodoList/Items.

15. **Mutmut survivants Phase 2 du même type que Phase 1** — boundaries, context kwargs, output field assignments. Confirme que ces "free holes" sont systématiques pour tout nouveau use case et qu'une checklist "tests à ajouter avant mutate" serait précieuse dans la skill `tdd-workflow` § Mutate. Pattern observé : pour chaque use case behaviourally-complete, ajouter ~5 tests "kill the obvious" pour passer le seuil 90%.

### Positives

16. **Outside-in flow plus fluide en Phase 2** — l'expérience accumulée de Phase 1 a fait que Phase 2 a moins de friction "où mettre quoi". L'ImportError chain est plus rapide à dérouler. Probable que la 3ème feature dans une codebase soit toujours plus rapide qu'une 2ème, indépendamment du template.

17. **Le pattern entity-with-aggregate-method (TodoItem.complete/uncomplete)** est venu naturellement après "l'entité expose des méthodes nommées, pas d'assignation directe". Conforme aux conventions SOMA. Mais a forcé `is_completed` comme property — un détail mineur.

18. **Auto-discovery `ERROR_HTTP_MAPPING`** a re-fonctionné en Phase 2 — détection immédiate des 3 nouvelles exceptions à mapper. Confirme la valeur de ce garde-fou.

---

## Itérations sur les skills (à faire après le walkthrough)

Les 18 frictions identifiées sont triées et regroupées dans **`docs/validation/2026-05-20-todo-walkthrough-followups.md`** — c'est le backlog d'actions au niveau template. P0 = 6 items (bugs bloquants), P1 = 4 items (améliorations skills), P2 = 2 items (nice-to-have).

---

## Décisions intermédiaires

Décisions prises pendant le walkthrough qui doivent remonter dans le spec ou les skills :

1. **2026-05-20** — Sauvé en mémoire feedback ([`feedback_plan_no_domain_predecision.md`](file:///home/vbacoup/.claude/projects/-home-vbacoup-Documents-Repos-dev-soma-template/memory/feedback_plan_no_domain_predecision.md)) : le plan outside-in ne pré-décide JAMAIS où vit la validation (VO vs entity factory vs use case body), les noms de classes Protocol, les exceptions ou les champs DTO. Tous émergent des tests. Règle à durcir dans `building-a-feature` skill (item #6 du followups).

2. **2026-05-20** — `IdempotencyMiddleware` ne peut pas être validé à 100% via les e2e endpoint-par-endpoint. Décision : reste couvert par les tests d'intégration du middleware. Documenter dans `building-a-feature` § Idempotency (item #11 du followups).

3. **2026-05-20** — Pattern "aggregate avec children" (TodoList → items) demande des choix non-triviaux (selectinload, cascade delete-orphan, save-diff). Pas dans la skill `building-a-feature`. À ajouter (item #12 du followups).

4. **2026-05-20** — Confirmation que le main agent a un biais d'accumulation qui rend la discipline outside-in fragile : malgré la skill explicite, plan v1 a leak des VO. Argument pour un sub-agent planner en contexte frais (à débattre, cf. item #7 du followups).

5. **2026-05-20** — Walkthrough stoppé après Phase 2 — signal jugé suffisant. 18 frictions documentées en 2 features. ROI clair pour itérer sur le template avant de continuer la validation.
