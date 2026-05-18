# Template validation — TODO API walkthrough

**Date** : 2026-05-12
**Objectif** : valider empiriquement que le template SOMA contient **exactement** ce qu'il faut pour construire un service métier réel, en exerçant chaque skill, chaque agent et chaque feature d'infrastructure. Le verdict est binaire : si une étape demande de l'improvisation hors-skill, c'est un trou à combler dans le template.

Cette doc planifie le test. Le rapport final (ce qui a marché ou pas) sera ajouté en fin de doc une fois le walkthrough fini.

## 1. Portée et hors-portée

### Dans la portée

- Bake du template avec les options "complètes" (`postgres + helm + otel + auth + typescript SDK`).
- Construction d'une API TODO réaliste (cf. § 3 pour le périmètre fonctionnel).
- Utilisation de **chaque** skill au moins une fois, dans son contexte naturel.
- Utilisation de **chaque** sub-agent au moins une fois.
- Exécution de chaque feature infra : auth, idempotency, outbox, alerts, runbooks, event sourcing.
- Self-review final avec `reviewing-a-pr-soma-style`.

### Hors portée

- Ne pas déployer en prod (Helm `lint` + `template` suffisent).
- Ne pas exercer le mode `database=sqlite` ni `database=none` (couvert par les bake tests existants).
- Ne pas tester le mode `include_helm=no` ni `include_otel=no` (idem).
- Ne pas faire de load test (le harness n'est pas shipped).

## 2. Méthode

- Bake dans `/tmp/todo-validation/` pour isoler du template repo.
- Suivre les 7 itérations ci-dessous, dans l'ordre. Chacune a un objectif clair + un check de fin.
- À chaque itération, noter dans le rapport final :
  - ✅ ce qui a marché out-of-the-box (skill claire, code complet, agent qui scaffold correctement)
  - ⚠️ ce qui a nécessité d'extrapoler (skill ambiguë, exemple manquant, friction modérée)
  - ❌ ce qui ne marche pas (code cassé, skill fausse, agent qui génère du non-compilable)
- À la fin de chaque itération : tests verts (`uv run pytest -m "unit or integration or e2e"`), lints verts (`just lint`), mutmut ≥ 90% sur code touché.

### 2.1 Pureté du test — règles que je m'impose

Le but est de simuler **un dev qui découvre le template**, pas un dev qui se souvient de ce qu'on a câblé ensemble pendant cette conversation. Sans ça, le test est cuit d'avance et ne révèle rien.

**Pour les sub-agents** (Task tool) : pas de souci, ils démarrent en contexte vierge par design. Ils ne voient que :
- Leur propre fichier `.md` de définition
- Le prompt explicite que je leur passe

**Pour moi (agent principal)**, le risque c'est de m'appuyer sur la mémoire de la session plutôt que sur les skills shipped. Règles que je m'engage à suivre :

1. **À chaque skill que je prétends utiliser, je la `Read` fresh** au moment où j'en ai besoin — pas "je me souviens qu'elle dit X". Si je m'aperçois que je sais déjà la réponse sans la lire, je la lis quand même pour vérifier.
2. **Pour briefer un sub-agent, le prompt est self-contained.** Aucune référence du genre "comme on en a parlé", "rappelle-toi que", "le pattern qu'on a câblé". Le prompt décrit le contexte du zéro.
3. **Si je veux faire un choix non documenté dans la skill, c'est un trou à logger.** Le walkthrough doit révéler ces moments. Quand je vois "la skill ne couvre pas ce cas" ou "la skill est ambiguë", je le note dans le rapport **et** je documente quelle décision arbitraire j'ai prise faute de mieux.
4. **Pas de pre-fix.** Si je sais qu'un fichier a un bug parce qu'on l'a fixé pendant la session, je ne le pre-fix pas — je laisse le walkthrough buter dessus comme un dev neuf le ferait, et je log l'incident.
5. **Pas de raccourci sur les commandes.** Si la skill dit `just test` et que je sais qu'on a aussi `just test-all`, j'utilise `just test` (ce que la skill prescrit). Toute deviation est un signal que la skill est sous-spécifiée.
6. **Briefs aux builders : strictement le template documenté.** La skill `orchestrating-feature-dev` ship 3 templates de brief (un par builder). À chaque dispatch je les utilise comme grille — chaque slot rempli, chaque skill citée. Si je découvre qu'un slot manque (« où ai-je mis l'event payload ? »), c'est un trou dans le template à logger.

Ces règles ne rendent pas le test parfait — je reste le même Claude tout du long — mais elles maximisent la friction observable. Le rapport final notera explicitement les moments où j'ai craqué.

### 2.2 Rappel — la philosophie "main agent = architecte" en 3 lignes

- **Main agent design** : Protocol shape + DTO + event payload + exceptions + status codes — en conversation, pas en fichiers.
- **Main agent ne touche PAS** au code de prod (use case body, repo impl, route handler). Seul cross-cutting (`adding-a-new-abstraction` pour un nouveau Protocol transverse, `error_handlers.py` mapping si le route-builder rate le set).
- **Builders exécutent** sur la base du brief self-contained. Refus du builder = brief incomplet = bug à logger.

## 3. Domaine fonctionnel à construire — TODO API

Modélisation classique pour exercer la diversité des patterns :

### Entités

* **`TodoList`** — collection nommée appartenant à un user, audit-heavy → cible pour event sourcing
* **`TodoItem`** — élément dans une liste (titre, description, priorité, due_date, completed)
* **`TodoListShare`** — relation many-to-many entre TodoList et users invités (collaboration)

### Value objects

* **`Priority`** — enum `LOW | MEDIUM | HIGH | URGENT`
* **`DueDate`** — datetime contrainte (>= now), TZ-aware
* **`TodoListId`**, **`TodoItemId`** — UUID typés

### Use cases (9 au total)

CRUD complet exercé via **TodoItem** (plus riche en state transitions). **TodoList** se limite à `Create` (suffit pour exercer la création d'aggregate + auth + idempotency + event). Le use case **complexe** est `MoveTodoItem` — il touche deux aggregates, exige authz sur les deux, demande atomicité, et stresse le pattern multi-entity transaction.

| # | Use case | Entrée auth | Idempotent ? | Émet event ? | Pattern stressé |
|---|---|---|---|---|---|
| 1 | CreateTodoList | user | oui (POST) | TodoListCreated | use case basique + idempotency + outbox |
| 2 | AddTodoItem | owner OR sharee | oui (POST) | TodoItemAdded | use case avec validation (MaxItemsExceededError) |
| 3 | CompleteTodoItem | owner OR sharee | non (PATCH) | TodoItemCompleted | state machine (déjà complété → error) |
| 4 | UncompleteTodoItem | owner OR sharee | non (PATCH) | TodoItemUncompleted | reverse state machine |
| 5 | ChangeItemPriority | owner OR sharee | non (PATCH) | — | mutation simple sans event |
| 6 | DeleteTodoItem | owner OR sharee | non (DELETE) | TodoItemDeleted | delete + event |
| 7 | ListItems | owner OR sharee | — (GET) | — | finder method sur le Protocol Repo |
| 8 | ShareTodoList | owner only | oui (POST) | TodoListShared | **abstraction nouvelle** (NotificationSender) + audit + event |
| 9 | MoveTodoItem | owner OR sharee sur **les deux** listes | non (PATCH) | TodoItemMoved | **complexe** : 2 aggregates, authz cross, atomicité |

### Exceptions métier (7)

`TodoListNotFoundError`, `TodoItemNotFoundError`, `NotAuthorizedToModifyError`, `NotAuthorizedToShareError`, `TodoItemAlreadyCompletedError`, `TodoItemNotCompletedError`, `MaxItemsExceededError`.

### Abstractions nouvelles (4)

Repositories (sous-Protocols de `Repository[TEntity, TId]`) :

* **`TodoListRepository(Repository[TodoList, TodoListId])`** — ajoute `find_by_owner`, `find_by_id_with_shares`.
* **`TodoItemRepository(Repository[TodoItem, TodoItemId])`** — ajoute `find_by_list`, `count_active_by_list` (pour `MaxItemsExceededError`).
* **`TodoListShareRepository(Repository[TodoListShare, TodoListShareId])`** — ajoute `find_by_list`, `find_by_user`.

Collaborator nouveau (pas un repo) :

* **`NotificationSender`** Protocol — notifie le user invité quand `ShareTodoList`. Exercise `adding-a-new-abstraction`.

## 4. Matrice de couverture skills → itération

| Skill | Itération qui l'exerce | Comment |
|---|---|---|
| `onboarding-soma` | 0 | Lecture du file map avant de coder |
| `clean-architecture-layers` | 1, 2, 3 | Décisions de placement à chaque nouveau fichier |
| `writing-domain-code` | 1 | Entities + Value Objects + invariants |
| `adding-a-use-case` | 2, 4 | Chaque use case de la liste |
| `adding-a-new-abstraction` | 4 | `NotificationSender` |
| `adding-a-domain-exception` | 1, 4 | Toutes les exceptions ci-dessus |
| `tdd-workflow` | 2, 3, 4 | Red → green pour chaque use case |
| `writing-tests` | 2, 3, 4, 6 | Unit + integration + e2e |
| `using-the-di-container` | 2, 4 | Factories pour chaque use case + nouvelles bindings |
| `database-and-migrations` | 3 | Migrations todo_lists, todo_items, todo_list_shares |
| `observability-patterns` | 5 | Vérifier que `_instrumented` wrap les use cases (sans modif) |
| `naming-conventions` | toutes | Continu — chaque nommage |
| `writing-a-helm-change` | 5 | Ajouter `MAX_ITEMS_PER_LIST` à values + schema + configmap |
| `adding-auth` | 2, 4 | Toutes les routes sont protégées ; sharing requiert owner check |
| `idempotency-and-retries` | 4 | Test `Idempotency-Key` sur POST /todo-lists |
| `transactions-and-events` | 4 | Émission de `TodoListCreated`, handler in-process pour log |
| `event-sourcing-pattern` | 6 | Event-source `TodoList` (entity audit-heavy par hypothèse) |
| `incident-response` | 7 | Lecture passive si un test casse en route |
| `reviewing-a-pr-soma-style` | 7 | Self-review final |
| `orchestrating-feature-dev` | toutes | Méta — quand dispatcher un sous-agent |

## 5. Matrice de couverture sub-agents → itération

Le template ship 8 agents (3 feature-level builders + 5 tech-narrow utilities). Le walkthrough exerce les 6 qui sont pertinents pour ce périmètre fonctionnel — les 2 test-writers démotés (`soma-unit-test-writer`, `soma-integration-test-writer`) ne sont pas exercés ici car leur cas d'usage (combler une coverage gap sur du code existant) ne se présente pas dans une construction from-scratch. Si un cas se présente en cours de route, on le notera.

### Feature-level builders (chacun exercé plusieurs fois)

| Agent | Phases | Tâches |
|---|---|---|
| `soma-use-case-builder` | 2, 4, 5, 7 | CreateTodoList ; AddTodoItem / Complete / Uncomplete / ChangePriority / Delete / ListItems ; ShareTodoList ; MoveTodoItem (complexe multi-aggregate) — **9 dispatches** au total |
| `soma-persistence-builder` | 3, 4, 5 | `SqlAlchemyTodoListRepository` + migration ; `SqlAlchemyTodoItemRepository` + migration ; `SqlAlchemyTodoListShareRepository` + migration — **3 dispatches** |
| `soma-route-builder` | 2, 4, 5, 7 | Un dispatch par endpoint exposé : CreateTodoList, 6 TodoItem routes, ShareTodoList, MoveTodoItem — **9 dispatches** |

### Tech-narrow utilities

| Agent | Phases | Tâche |
|---|---|---|
| `soma-helm-engineer` | 8 | Ajouter `MAX_ITEMS_PER_LIST` au chart |
| `soma-event-sourcing-bootstrapper` | 9 | Scaffold ES pour `TodoItem` |
| `soma-migration-writer` | — | Pas exercé : toutes les migrations de ce walkthrough sont attelées à des nouveaux repos donc absorbées par `soma-persistence-builder`. Si une migration standalone se présente (alter column sur table existante, ajout d'index), on le notera. |
| `soma-unit-test-writer` | — | Pas exercé from-scratch (couvert par les builders). Si une coverage gap apparaît, on dispatche. |
| `soma-integration-test-writer` | — | Idem. |

## 6. Itérations

Découpage fin : **10 phases × 1 à 3 étapes** chacune. Chaque étape a un objectif, des skills exercées, des actions, et un check de fin. Chaque étape fait 15-30 min — point de pause possible entre n'importe lesquelles.

Format de chaque étape : `**X.Y — <titre> (≈ Z min)**` + objectif + skills + actions + check.

---

### Phase 0 — Setup & sanity

**0.1 — Bake + smoke tests (≈ 15 min)**
- *Objectif* : bake le template, vérifier que la baseline est verte avant de toucher quoi que ce soit.
- *Skills* : aucune (pré-walkthrough).
- *Actions* :
  - `rm -rf /tmp/todo-validation`
  - `cookiecutter <template> --no-input -o /tmp/todo-validation` avec `project_name="Todo API"`, `database=postgres`, `include_helm=yes`, `include_otel=yes`, `frontend_sdk=typescript`, `license=proprietary`
  - `cd /tmp/todo-validation/todo-api && uv sync --group dev`
  - `uv run pytest -m "unit or integration or e2e"`
  - `helm lint helm/todo-api/`
  - `curl -H "Authorization: Bearer $(just dev-token alice)" http://localhost:8000/v1/auth/whoami` (après `just dev` en background)
- *Check* : 70+ tests verts, helm lint clean, `/v1/auth/whoami` renvoie 200 avec `{"subject": "alice"}`.

---

### Phase 1 — Domain layer

**1.1 — Value objects (≈ 20 min)**
- *Objectif* : créer `Priority`, `DueDate`, `TodoListId`, `TodoItemId`, `TodoListShareId` avec leurs invariants.
- *Skills* : `onboarding-soma`, `clean-architecture-layers`, `writing-domain-code`, `naming-conventions`.
- *Actions* : 5 fichiers sous `domain/value_objects/` + tests unitaires des invariants (Priority enum 4 valeurs, DueDate refuse passé, IDs typés autour de UUID).
- *Check* : `pytest -m unit -k "test_priority or test_due_date or test_todo_list_id or test_todo_item_id"` vert ; `scripts/checks/no_third_party_in_domain.py` clean.

**1.2 — Entities (≈ 25 min)**
- *Objectif* : `TodoList(Entity[TodoListId])` et `TodoItem(Entity[TodoItemId])` avec state machine "open / completed".
- *Skills* : `writing-domain-code`, `naming-conventions`.
- *Actions* : 2 fichiers `domain/entities/`, méthodes business (`TodoItem.complete()`, `uncomplete()`, `change_priority()`, `move_to()`), pas de `_pending_events` à ce stade (CRUD-mode initialement, ES en phase 9).
- *Check* : tests unit sur les state transitions ; `TodoItem.complete()` 2 fois → `TodoItemAlreadyCompletedError`.

**1.3 — Domain exceptions (≈ 10 min)**
- *Objectif* : 7 exceptions métier sous `domain/exceptions/todo.py`.
- *Skills* : `adding-a-domain-exception`.
- *Actions* : 7 sous-classes de `DomainError` avec `code` + `default_message` ClassVars + entrées dans `ERROR_HTTP_MAPPING`.
- *Check* : `pytest -m unit -k test_error_mapping` vert (le test exhaustif sur les subclasses détecte les manques).

**1.4 — Repository Protocol skeletons (≈ 10 min)**
- *Objectif* : 3 Protocol skeletons sous `application/repositories/` : `TodoListRepository`, `TodoItemRepository`, `TodoListShareRepository`. Aucune méthode business à ce stade — le main agent crée juste le `class …Repository(Repository[Entity, EntityId], Protocol): pass`. Les méthodes business-named (`find_active_by_owner_and_name`, `count_active_by_list`, etc.) seront ajoutées par `soma-use-case-builder` au moment où chaque use case en a besoin (cf. `orchestrating-feature-dev` et `naming-conventions` § Repository method naming).
- *Skills* : `clean-architecture-layers`, `naming-conventions`.
- *Actions* : créer chaque sous-Protocol avec un docstring qui décrit le rôle de l'entity, sans méthode (seulement `add` + `find_by_id` hérités).
- *Check* : ruff + `ty` passent ; aucun import infrastructure ; les 3 Fake repos vides existent sous `tests/fakes/repositories/`.

---

### Phase 2 — Premier use case end-to-end (via builders)

**2.1 — Design + dispatch `soma-use-case-builder` pour CreateTodoList (≈ 30 min)**
- *Objectif* : faire produire au builder le slice application : DTO + Fake repo + Protocol extension + use case + tests unit avec mutmut ≥ 90%.
- *Skills lues par le main agent* : `orchestrating-feature-dev`, `adding-a-use-case`, `naming-conventions` (§ Repository method naming), `transactions-and-events`.
- *Design phase (main agent)* : décider Protocol methods + DTO + event + exceptions, puis rédiger le brief.
- *Actions* :
  - Le main agent design la feature :
    - DTO : `CreateTodoListInput(name: str, owner_id: UUID)` → `CreateTodoListOutput(id, name, owner_id, created_at)`
    - Méthode Protocol à ajouter : `find_active_by_owner_and_name(owner_id, name) -> TodoList | None` (filter contract : ignore soft-deleted, used for unique-name-per-owner check)
    - Event : `todo_list.created` avec payload `{id, name, owner_id, created_at_iso}`
    - Exception : `TodoListAlreadyExistsError` (code `TODO_LIST_ALREADY_EXISTS`)
  - Dispatch `soma-use-case-builder` avec un brief self-contained suivant le template de `orchestrating-feature-dev` § "Brief pour soma-use-case-builder".
  - Vérifier le rapport de l'agent : files créés/modifiés ; mutation kill-rate ≥ 90% ; ajout de `find_active_by_owner_and_name` au Protocol ET au Fake.
- *Check* :
  - `pytest -m unit -k create_todo_list` vert
  - `scripts/checks/no_third_party_in_domain.py` + `test_naming.py` clean
  - Le Protocol `TodoListRepository` contient maintenant `find_active_by_owner_and_name` avec un docstring qui explique le filter
  - L'event `todo_list.created` est bien ajouté à `ERROR_HTTP_MAPPING` ? Non — c'est une exception, pas un event. Vérifier que `TodoListAlreadyExistsError` est mappé (409).

**2.2 — Dispatch `soma-route-builder` pour POST /v1/todo-lists (≈ 25 min)**
- *Objectif* : faire produire au builder le slice presentation : schema + route + container factory + dependency wrapper + e2e.
- *Skills lues par le main agent* : `using-the-di-container`, `adding-auth`, `idempotency-and-retries`.
- *Design phase (main agent)* : trancher HTTP semantics + auth + status codes + idempotency.
- *Actions* :
  - Le main agent design :
    - Method + path : `POST /v1/todo-lists`
    - Auth : authenticated
    - Idempotency : oui (POST)
    - Status codes : 201 happy, 401 sans token, 409 `TodoListAlreadyExistsError`, 422 payload invalide
  - Dispatch `soma-route-builder` avec un brief self-contained suivant le template de `orchestrating-feature-dev` § "Brief pour soma-route-builder".
  - Vérifier le rapport : files créés ; mapping ajouté à `ERROR_HTTP_MAPPING` ; e2e tests verts.
- *Check* :
  - `pytest -m e2e -k todo_lists` vert (≥ 2 tests : happy 201 + critical 401)
  - `curl -H "Authorization: Bearer $(just dev-token alice)" -X POST http://localhost:8000/v1/todo-lists -d '{"name":"shopping"}' -H 'Content-Type: application/json'` renvoie 201 avec le payload attendu
  - **Question méta** : le brief était-il complet ? Y a-t-il eu un aller-retour avec le builder (refus, demande de précision) ? À noter dans le rapport.

---

### Phase 3 — Persistence TodoList (via `soma-persistence-builder`)

**3.1 — Dispatch `soma-persistence-builder` pour TodoListRepository (≈ 30 min)**
- *Objectif* : faire produire au builder le slice infrastructure complet — SQLAlchemy model + Alembic migration (avec roundtrip vérifié) + impl SQL du Protocol + integration tests.
- *Skills lues par le main agent* : `orchestrating-feature-dev`, `database-and-migrations`.
- *Design phase (main agent)* : trancher le schéma exact, les contraintes uniques, le soft-delete, et le mapping IntegrityError → DomainError.
- *Actions* :
  - Le main agent design :
    - Schema `todo_lists` : `id UUID PK, owner_id UUID NOT NULL indexed, name VARCHAR(255) NOT NULL, created_at TIMESTAMPTZ NOT NULL, deleted_at TIMESTAMPTZ NULL`
    - Contrainte UNIQUE partielle : `(owner_id, name) WHERE deleted_at IS NULL`
    - Soft-delete via `deleted_at` (convention SOMA)
    - IntegrityError sur duplicate → `TodoListAlreadyExistsError`
  - Dispatch `soma-persistence-builder` avec un brief self-contained suivant le template de `orchestrating-feature-dev` § "Brief pour soma-persistence-builder".
  - Vérifier le rapport : migration cure + roundtrip clean ; toutes les méthodes du Protocol implémentées ; tests d'intégration couvrant `add` happy + `add` duplicate → `TodoListAlreadyExistsError` + `find_by_id` missing → None + `find_active_by_owner_and_name` ignore les soft-deleted.
- *Check* :
  - `just migrate → migrate-down → migrate` clean
  - `uv run alembic revision --autogenerate -m drift` produit une migration vide
  - `pytest -m integration -k todo_list_repository` vert
  - Le e2e de la phase 2 (CreateTodoList POST) continue de passer **avec le repo SQL en place** (le container doit être swappé du Fake vers `SqlAlchemyTodoListRepository`)
  - **Question méta** : le builder a-t-il bien lu les docstrings du Protocol pour deriver les WHERE clauses ? Le `find_active_by_owner_and_name` exclut-il bien les soft-deleted ? À vérifier dans le code généré.

---

### Phase 4 — TodoItem CRUD (6 use cases via builders)

Chaque step suit le pattern Phase 2 : main agent design → dispatch `soma-use-case-builder` → dispatch `soma-route-builder`. Le brief reprend le template documenté dans `orchestrating-feature-dev`. Vue récap des 6 use cases :

| Use case | Method + path | Idempotency | Event émis | Exceptions raise-able |
|---|---|---|---|---|
| AddTodoItem | POST /v1/todo-lists/{id}/items | yes | `todo_item.added` | `TodoListNotFoundError`, `MaxItemsExceededError` |
| CompleteTodoItem | PATCH /v1/todo-items/{id}/complete | no | `todo_item.completed` | `TodoItemNotFoundError`, `TodoItemAlreadyCompletedError` |
| UncompleteTodoItem | PATCH /v1/todo-items/{id}/uncomplete | no | `todo_item.uncompleted` | `TodoItemNotFoundError`, `TodoItemNotCompletedError` |
| ChangeItemPriority | PATCH /v1/todo-items/{id}/priority | no | — | `TodoItemNotFoundError` |
| DeleteTodoItem | DELETE /v1/todo-items/{id} | no | `todo_item.deleted` | `TodoItemNotFoundError` |
| ListItems | GET /v1/todo-lists/{id}/items | — (GET) | — | `TodoListNotFoundError` |

**4.1 — AddTodoItem + state machine Complete/Uncomplete (≈ 75 min)**
- *Objectif* : 3 use cases + 3 routes pour la state machine TodoItem (Add → Complete ↔ Uncomplete).
- *Skills lues par le main agent* : `adding-a-use-case`, `naming-conventions` (méthodes Protocol business-named pour TodoItem), `transactions-and-events`.
- *Actions* (3 fois le pattern) :
  - Pour chacun des 3 use cases :
    - Le main agent design la méthode Protocol nécessaire sur `TodoItemRepository` (ex: `find_open_by_id(id) -> TodoItem | None` qui retourne `None` si l'item est completed, pour `UncompleteTodoItem` la symétrie `find_completed_by_id`)
    - Dispatch `soma-use-case-builder` avec le brief
    - Dispatch `soma-route-builder` avec le brief HTTP
- *Check* :
  - `pytest -m unit -k "add_todo_item or complete or uncomplete"` vert
  - `pytest -m e2e -k todo_items` vert
  - Mutmut ≥ 90% sur les 3 use cases
  - State machine : `CompleteTodoItem` 2× → `TodoItemAlreadyCompletedError` (409)
  - **Question méta** : les 3 builders ont-ils proposé des noms Protocol cohérents (`find_open_by_id` vs `find_active_by_id` vs `find_by_id` + check inline) ? Si incohérent, le brief doit être plus directif.

**4.2 — ChangeItemPriority + DeleteTodoItem + ListItems (≈ 60 min)**
- *Objectif* : 3 use cases peripheral.
- *Skills* : `adding-a-use-case`.
- *Actions* : même pattern. Note pour `ListItems` : c'est un GET, donc le brief route-builder est plus court (pas d'idempotency, pas de body, response = list[TodoItemReadSchema]).
- *Check* : unit + e2e verts ; mutmut 90% sur ChangeItemPriority et DeleteTodoItem (ListItems n'a pas de logique métier, mutmut moins pertinent).

**4.3 — TodoItem persistence (≈ 30 min)**
- *Objectif* : dispatch `soma-persistence-builder` pour `TodoItemRepository`.
- *Skills lues par le main agent* : `orchestrating-feature-dev`, `database-and-migrations`.
- *Design phase (main agent)* :
  - Schema `todo_items` : `id UUID PK, list_id UUID NOT NULL FK → todo_lists, title VARCHAR(255), description TEXT NULL, priority VARCHAR(16) NOT NULL ('LOW'|'MEDIUM'|'HIGH'|'URGENT'), completed_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL, deleted_at TIMESTAMPTZ NULL`
  - FK `list_id` avec ON DELETE CASCADE (si la liste est purgée, les items partent avec)
  - Index sur `list_id` (pour `find_by_list`)
- *Actions* : Dispatch `soma-persistence-builder` avec le brief.
- *Check* :
  - Migration roundtrip clean
  - Toutes les méthodes du Protocol `TodoItemRepository` implémentées (`add`, `find_by_id`, `find_open_by_id`, `find_completed_by_id`, `find_by_list`, `count_active_by_list`, …)
  - Les 6 e2e tests du CRUD TodoItem passent **avec le repo SQL en place**
  - **Question méta** : la migration drift-check est-elle vraiment vide ? Si autogen propose des modifications, c'est que le model SQLAlchemy ne matche pas la migration — bug à logger.

---

### Phase 5 — Sharing & nouvelle abstraction

**5.1 — NotificationSender abstraction (≈ 20 min)**
- *Objectif* : Protocol + Fake + impl null.
- *Skills* : `adding-a-new-abstraction`.
- *Actions* :
  - `application/notification_sender.py` Protocol avec `async def notify_shared(self, *, recipient: Email, list_name: str) -> None`
  - `infrastructure/notifications/null_notification_sender.py` (no-op + log)
  - `tests/fakes/notification_sender.py` (records `.notified: list[tuple[Email, str]]`)
  - Fixture `notification_sender` dans root conftest
  - Wire dans `container.py` et dans `dependencies/`
- *Check* : la skill `adding-a-new-abstraction` a-t-elle un anti-pattern qui te bloque ? Si oui, log dans le rapport.

**5.2 — ShareTodoList use case (via builders) (≈ 50 min)**
- *Objectif* : `ShareTodoList` avec authz owner-only + appel `NotificationSender` + event ; full vertical slice avec persistence pour la nouvelle entity `TodoListShare`.
- *Skills lues par le main agent* : `orchestrating-feature-dev`, `adding-a-use-case`, `adding-auth`, `database-and-migrations`, `naming-conventions`.
- *Design phase (main agent)* :
  - Use case `ShareTodoListUseCase` : load list, vérifie owner (raise `NotAuthorizedToShareError` sinon), crée `TodoListShare`, appelle `NotificationSender.notify_shared`, émet `todo_list.shared`.
  - Méthodes Protocol nouvelles :
    - `TodoListRepository.find_owned_by_owner_and_id(owner_id, list_id) -> TodoList | None` (retourne `None` si la liste n'existe pas OU n'est pas owned by `owner_id`)
    - `TodoListShareRepository.find_by_list_and_user(list_id, user_id) -> TodoListShare | None` (check si déjà shared)
  - Event `todo_list.shared` payload : `{list_id, shared_with_user_id, shared_at_iso}`
  - Exception `NotAuthorizedToShareError` (code `NOT_AUTHORIZED_TO_SHARE`, mapping 403)
  - HTTP : `POST /v1/todo-lists/{id}/shares` body `{user_id: UUID}` → 201 happy, 403 si pas owner, 409 si déjà sharé, 404 si liste inexistante
- *Actions* :
  - Dispatch `soma-use-case-builder` pour le use case
  - Dispatch `soma-persistence-builder` pour `SqlAlchemyTodoListShareRepository` + migration (table `todo_list_shares` : `id UUID PK, list_id UUID FK, user_id UUID, shared_at TIMESTAMPTZ NOT NULL`, UNIQUE `(list_id, user_id)`)
  - Dispatch `soma-route-builder` pour l'endpoint
- *Check* :
  - 4 tests unit (happy + not owner → 403 + share with self → error métier + repeated share → 409)
  - `NotificationSender` est appelé une fois par share réussi (Spy via Fake, asserté dans le unit test)
  - Migration roundtrip clean
  - e2e tests verts

---

### Phase 6 — Cross-cutting validation

**6.1 — Outbox handlers (≈ 15 min)**
- *Objectif* : in-process handlers consomment les events `todo_*` et écrivent un log structuré.
- *Skills* : `transactions-and-events`.
- *Actions* : ajouter `infrastructure/jobs/event_handlers.py` avec 6 handlers (`@handler("todo_list.created")` etc.) qui logent les events. Test d'intégration : push une row dans `outbox_events`, run `_drain_once`, vérifier que le handler a été appelé.
- *Check* : integration test du roundtrip outbox+handler vert pour `todo_list.created`.

**6.2 — Idempotency e2e (≈ 15 min)**
- *Objectif* : prouver que `Idempotency-Key` marche sur `POST /v1/todo-lists` et `POST /v1/todo-lists/{id}/items`.
- *Skills* : `idempotency-and-retries`.
- *Actions* : 2 tests e2e — POST avec key, retry avec même key → response identique, handler n'a tourné qu'une fois (vérifiable via le repo Fake `.users` ou `.todo_lists` ne contient qu'une row).
- *Check* : 2 e2e verts ; idempotency_records contient la row.

---

### Phase 7 — Use case complexe (MoveTodoItem)

C'est l'étape qui stresse le plus l'architecture : un use case multi-aggregate avec authz cross-list. Si les builders n'ont pas été conçus pour ça, le brief sera lourd ou ambigu — on le notera.

**7.1 — Design + dispatch `soma-use-case-builder` pour MoveTodoItem (≈ 35 min)**
- *Objectif* : use case multi-aggregate (`TodoItem` + 2× `TodoList`) avec authz **cross-list** + atomicité + event.
- *Skills lues par le main agent* : `orchestrating-feature-dev`, `adding-a-use-case`, `writing-domain-code`, `naming-conventions`, `transactions-and-events`.
- *Design phase (main agent)* :
  - DTO : `MoveTodoItemInput(item_id: UUID, to_list_id: UUID, actor: CurrentUser)` → `MoveTodoItemOutput(item_id, new_list_id, moved_at)`
  - Méthode domain à ajouter : `TodoItem.move_to(to_list_id: TodoListId) -> None` (no-op si déjà dans la cible ; raise `CannotMoveCompletedItemError` si l'item est completed)
  - Méthodes Protocol nouvelles ou réutilisées :
    - `TodoItemRepository.find_active_by_id(id) -> TodoItem | None` (déjà ajoutée en phase 4 probablement — sinon à clarifier)
    - `TodoListRepository.find_accessible_by_user_and_id(user_id, list_id) -> TodoList | None` (NEW — retourne la liste si user est owner OU sharee, None sinon ; **business-named** car "accessible" = la sémantique métier)
    - `TodoItemRepository.count_active_by_list(list_id) -> int` (déjà en phase 4)
  - Exception `CannotMoveCompletedItemError` (code `CANNOT_MOVE_COMPLETED_ITEM`, mapping 409)
  - Event `todo_item.moved` payload `{item_id, from_list_id, to_list_id, moved_at_iso}`
  - Use case logic :
    1. Load item via `find_active_by_id` → `TodoItemNotFoundError` 404 si None
    2. Load from_list via `find_accessible_by_user_and_id(actor, item.list_id)` → `NotAuthorizedToModifyError` 403 si None
    3. Load to_list via `find_accessible_by_user_and_id(actor, to_list_id)` → `NotAuthorizedToModifyError` 403 si None
    4. Si to_list == from_list : no-op (200 sans event ; documenter ce choix)
    5. Si `count_active_by_list(to_list_id) >= settings.max_items_per_list` → `MaxItemsExceededError` 409
    6. `item.move_to(to_list_id)` → peut raise `CannotMoveCompletedItemError`
    7. `save(item)` + publish event
- *Actions* :
  - Dispatch `soma-use-case-builder` avec le brief.
  - **Note critique** : le brief doit décrire les 6 chemins d'erreur explicitement. Le builder n'invente rien.
- *Check* :
  - 6 tests unit (happy + actor pas autorisé sur from_list + actor pas autorisé sur to_list + to_list pleine + item inexistant + item déjà completed)
  - Mutmut ≥ 90%
  - **Question méta importante** : le builder a-t-il géré le pattern multi-aggregate sans confusion ? La skill `adding-a-use-case` l'a-t-elle bien guidé ? Logger précisément : combien d'aller-retours avec le builder, quelles questions du builder, quelles ambiguïtés détectées.

**7.2 — Dispatch `soma-route-builder` pour PATCH /v1/todo-items/{id}/move (≈ 20 min)**
- *Objectif* : exposer `MoveTodoItem` en PATCH.
- *Design phase* :
  - Method + path : `PATCH /v1/todo-items/{id}/move`
  - Body : `{to_list_id: UUID}`
  - Auth : authenticated
  - Status codes : 200 happy (avec response body), 403 authz, 404 item ou list, 409 (`MaxItemsExceededError` ou `CannotMoveCompletedItemError`)
- *Check* :
  - 4 e2e tests (1 happy + 3 critical : 403 + 404 + 409)
  - **Question méta** : un PATCH avec body est-il bien supporté par le builder ? Status code 200 (vs 204) sur un PATCH avec response : la skill `using-the-di-container` ou `adding-auth` traite-t-elle ce cas ?

---

### Phase 8 — Helm change + observability

**8.1 — MAX_ITEMS_PER_LIST via agent (≈ 15 min)**
- *Objectif* : ajouter la config + la propager jusqu'au use case `AddTodoItem`.
- *Skills* : `writing-a-helm-change`.
- *Actions* :
  - Dispatch `soma-helm-engineer` avec brief self-contained : « Add `MAX_ITEMS_PER_LIST` (integer, default 100) to values.yaml + values.schema.json + configmap. The app reads it from env var. »
  - Ajouter le field dans `Settings`, le passer au use case via DI.
- *Check* : `helm lint`, `helm template` verts ; `AddTodoItem` raise `MaxItemsExceededError` quand `count_active >= max_items_per_list` (test unit).

**8.2 — Observabilité visuelle (≈ 15 min)**
- *Objectif* : vérifier que les use cases sont bien wrappés par `_instrumented` (rien à coder, juste vérifier).
- *Skills* : `observability-patterns`.
- *Actions* : lancer le projet en local, faire 1 POST `/v1/todo-lists`, regarder l'output : (a) span OTel imprimé sur le console exporter, (b) access log structuré, (c) compteur Prometheus incrémenté visible sur `/metrics`.
- *Check* : les 3 surfaces (span + log + metric) sont visibles pour le même request_id.

---

### Phase 9 — Event sourcing TodoItem

**9.1 — Dispatch bootstrapper (≈ 15 min)**
- *Objectif* : invoquer l'agent et examiner le scaffold sans rien modifier.
- *Skills* : `event-sourcing-pattern`.
- *Actions* :
  - Lire `event-sourcing-pattern`, valider que TodoItem coche la decision table (audit-heavy : qui a complété quoi quand, historique des moves).
  - Dispatch `soma-event-sourcing-bootstrapper` avec brief self-contained décrivant TodoItem (champs, méthodes existantes, repository Protocol existant).
  - Lire les 4 fichiers générés.
- *Check* : les 4 fichiers existent (events module, event store, ES repo, migration) ; le code compile (ruff + ty) ; pas de test cassé (les nouveaux fichiers ne sont pas encore wirés).

**9.2 — Rewrite TodoItem entity (≈ 25 min)**
- *Objectif* : convertir TodoItem en event-emitting (suivre les TODOs reportés par l'agent).
- *Skills* : `event-sourcing-pattern`, `writing-domain-code`.
- *Actions* :
  - Ajouter `_pending_events`, `_version` dans `__init__`.
  - Renommer les events du scaffold en business facts (`TodoItemAdded`, `TodoItemCompleted`, `TodoItemUncompleted`, `TodoItemPriorityChanged`, `TodoItemMoved`, `TodoItemDeleted`).
  - Réécrire chaque méthode de mutation pour `_record(event)` + appliquer le change.
  - Implémenter `from_events(events) -> Self`.
- *Check* : tests unit de la phase 4 toujours verts (les use cases appellent les mêmes méthodes).

**9.3 — Swap + backfill + verify (≈ 25 min)**
- *Objectif* : utiliser le repo ES en prod-mode, backfiller les rows existantes, vérifier le round-trip.
- *Skills* : `event-sourcing-pattern`.
- *Actions* :
  - Swap `build_todo_item_repository` dans `container.py` vers `EventSourcedTodoItemRepository`.
  - Migration de backfill : `INSERT INTO events SELECT ... FROM todo_items` (générer 1 `TodoItemAdded` event par row existante).
  - Test d'intégration round-trip : add → complete → move → delete, puis `from_events(events_for_id)` reproduit exactement l'état de la projection.
  - `MoveTodoItem` use case (phase 7) doit toujours marcher **sans modification**.
- *Check* : tous les tests d'intégration TodoItem passent ; `MoveTodoItem` use case inchangé ; `SELECT COUNT(*) FROM events WHERE aggregate_type = 'TodoItem'` cohérent avec les mutations.

---

### Phase 10 — Self-review + rapport

**10.1 — Review pass (≈ 15 min)**
- *Objectif* : appliquer la checklist de `reviewing-a-pr-soma-style` au code du walkthrough.
- *Skills* : `reviewing-a-pr-soma-style`.
- *Actions* : ouvrir la skill, parcourir chaque section (Architecture / Base classes / Abstractions / Tests / Events / Migrations / Helm / Supply chain), noter les violations.
- *Check* : `just lint && just test-all && just mutate && helm lint` tout vert ; aucune violation de la checklist.

**10.2 — Compilation du rapport (≈ 15 min)**
- *Objectif* : remplir la section § 8 ci-dessous.
- *Skills* : aucune (méta).
- *Actions* : compiler les tableaux skills / agents / features + la liste priorisée des trous + les suggestions d'amélioration.
- *Check* : la section "Rapport final" du présent document est complète.

## 7. Critères de succès global

Le template **réussit** si :

1. ✅ Bake initial sans erreur (itération 0 OK)
2. ✅ Chaque skill listée § 4 a été utilisée **sans improviser** au-delà de ce qu'elle documente
3. ✅ Chaque sub-agent a été dispatché et a généré du code qui compile et passe ses tests
4. ✅ 100% des features infra (auth + idempotency + outbox + alerts + ES) marchent dans les tests
5. ✅ `just lint && just test-all && just mutate && helm lint` tout vert sur le projet final
6. ✅ Aucune feature attendue n'est manquante pour livrer une vraie API CRUD multi-user collaborative

Le template **a un trou** si :

- ❌ Une skill est ambiguë et oblige à inventer un pattern
- ❌ Un agent génère du code non-compilable ou hors-conventions
- ❌ Une feature documentée ne marche pas comme annoncée (cf. `idempotency`, `outbox backoff`, etc.)
- ❌ Un cas d'usage classique (e.g. "user veut accéder à une liste partagée") force à patcher la `clean-architecture-layers` ou les Protocols base

## 8. Format du rapport final

Le rapport sera ajouté à la fin de ce document après le walkthrough. Structure :

### 8.1 Tableau synthétique par skill

| Skill | Utilisée ? | Verdict | Friction observée |
|---|---|---|---|
| `onboarding-soma` | ✅ | OK / OK avec note / KO | … |
| ... | ... | ... | ... |

### 8.2 Tableau synthétique par agent

| Agent | Utilisé ? | Code généré compile ? | Tests passent ? | Friction observée |
|---|---|---|---|---|

### 8.3 Tableau synthétique par feature infra

| Feature | Marche ? | Comment vérifié | Problème observé |
|---|---|---|---|
| Auth JWT | ✅ / ❌ | curl `/v1/auth/whoami` | … |
| Idempotency middleware | ✅ / ❌ | test e2e retry | … |
| Outbox + handlers | ✅ / ❌ | log handler exécuté | … |
| Helm chart | ✅ / ❌ | `helm lint && helm template` | … |
| PrometheusRule | ✅ / ❌ | `helm template` rend les 8 alertes | … |
| Event sourcing | ✅ / ❌ | round-trip events + projection | … |
| Devcontainer | ✅ / ❌ | `docker compose up` | … |
| Migration roundtrip | ✅ / ❌ | up → down → up | … |
| Mutmut ≥ 90% | ✅ / ❌ | `just mutate` | … |
| Lints (ruff + 4 AST) | ✅ / ❌ | `just lint` | … |

### 8.4 Liste prioritaire des trous identifiés

```
[ ] P0 — <description>, observed in iteration X, fix proposé : ...
[ ] P1 — ...
[ ] P2 — ...
```

### 8.5 Suggestions d'amélioration du template

- Documentation : skills à clarifier / exemples à ajouter
- Code : refactos à faire dans la reference feature User
- Tests : tests bake supplémentaires à ajouter
- Skills à ajouter : patterns récurrents pas encore documentés (e.g. "soft delete pattern" ?)
- Agents à ajouter : workflows pas couverts (e.g. "soma-route-writer" ?)

## 9. Risques et plan B

| Risque | Mitigation |
|---|---|
| Le walkthrough est long (~3-5h de travail dense) | Faisable en plusieurs sessions ; chaque itération est checkpoint avec commit |
| Un blocage dur en itération 3-6 (bug template) | Documenter le bug, l'ajouter en P0, sauter l'itération si possible, sinon stop |
| Le sub-agent ES génère du code qui ne compile pas | Documenter en P0, scaffold à la main, ne casse pas le reste du walkthrough |
| Manque de temps pour les 7 itérations | Prioriser 0 → 4 (couvre auth, idempotency, outbox, sub-agents principaux) ; 5 → 7 si temps |

## 10. Estimation de temps

Les estimations ont été revues après le pivot architectural (commit `fc3d7d3`) : chaque dispatch de builder feature-level fait plus de boulot qu'un dispatch d'agent tech-narrow, donc les étapes individuelles sont plus longues mais on en a moins.

| Phase | Détail | Cumulé |
|---|---|---|
| 0 — Setup | 1 étape (bake + smoke) | 15 min |
| 1 — Domain | 4 étapes (VOs, entities, exceptions, Protocol skeletons) | 1h10 |
| 2 — CreateTodoList | 2 dispatches (use-case + route) | 55 min |
| 3 — Persistence TodoList | 1 dispatch (persistence-builder) | 30 min |
| 4 — TodoItem CRUD | 7 dispatches (6 use cases × 2 dispatches each, batch in 3 phases) + 1 persistence | 2h45 |
| 5 — Sharing + NotificationSender | NotificationSender inline + 3 dispatches (use-case + persistence + route) | 1h |
| 6 — Outbox + idempotency | 2 étapes (handlers + e2e idempotency) | 30 min |
| 7 — MoveTodoItem (complex) | 2 dispatches (use-case + route) | 55 min |
| 8 — Helm + observability | 2 étapes (helm-engineer + obs visuel) | 30 min |
| 9 — Event sourcing TodoItem | 3 étapes (bootstrap + rewrite + swap) | 1h05 |
| 10 — Self-review + rapport | 2 étapes | 30 min |
| **Total** | | **~9h45** |

Le total monte par rapport au plan précédent (8h) parce que les phases 4, 5, 7 ont gagné des dispatches `soma-route-builder` qui sont des appels d'agent réels avec leur propre cycle écriture+tests. Honnête : c'est une charge plus réaliste, et chaque dispatch est un test du builder.

Découpage suggéré en sessions :
- **Session A — Foundation** (≈ 2h50) : phases 0 → 3 (setup, domain skeleton, CreateTodoList complet, persistence TodoList)
- **Session B1 — TodoItem CRUD** (≈ 2h45) : phase 4 seule (la plus dense, 6 use cases × 2 dispatches)
- **Session B2 — Sharing + cross-cutting** (≈ 1h30) : phases 5 + 6
- **Session C — Complex + ES + Helm** (≈ 2h30) : phases 7 + 8 + 9
- **Session D — Verdict** (≈ 30 min) : phase 10

Pause possible entre n'importe quelles étapes via commit (1 commit par phase, soit 10 commits total). Si une étape révèle un trou bloquant, je documente et passe à la suivante.

---

## Rapport final

*À compléter au fur et à mesure du walkthrough.*
