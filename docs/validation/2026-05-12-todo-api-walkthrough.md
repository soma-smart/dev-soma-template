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

Ces règles ne rendent pas le test parfait — je reste le même Claude tout du long — mais elles maximisent la friction observable. Le rapport final notera explicitement les moments où j'ai craqué.

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

| Agent | Itération | Tâche |
|---|---|---|
| `soma-unit-test-writer` | 2, 4 | Tests unit pour 2 use cases au moins |
| `soma-integration-test-writer` | 3 | Tests d'intégration pour `SqlAlchemyTodoListRepository` |
| `soma-migration-writer` | 3 | Migrations `0005_init_todos.py` |
| `soma-helm-engineer` | 5 | Ajouter `MAX_ITEMS_PER_LIST` au chart |
| `soma-event-sourcing-bootstrapper` | 6 | Scaffold ES pour `TodoList` |

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

**1.4 — Repository Protocols (≈ 15 min)**
- *Objectif* : 3 Protocols sous `application/repositories/` : `TodoListRepository`, `TodoItemRepository`, `TodoListShareRepository`.
- *Skills* : `clean-architecture-layers`, `adding-a-new-abstraction`.
- *Actions* : chaque Protocol extend `Repository[TEntity, TId]` et ajoute les finders métier (`find_by_owner`, `find_by_list`, `count_active_by_list`, `find_by_list_and_user`).
- *Check* : ruff + `ty` passent sur `application/repositories/` ; aucun import infrastructure depuis ces fichiers.

---

### Phase 2 — Premier use case end-to-end

**2.1 — CreateTodoList — use case + tests unit (≈ 25 min)**
- *Objectif* : DTO + use case + Fake repo + tests unitaires via `soma-unit-test-writer`.
- *Skills* : `adding-a-use-case`, `tdd-workflow`, `writing-tests`, `transactions-and-events` (pour la publication d'event).
- *Actions* :
  - DTO `CreateTodoListInput`, `CreateTodoListOutput`
  - Fake `InMemoryTodoListRepository`
  - Dispatch `soma-unit-test-writer` avec brief self-contained : « Write unit tests for `CreateTodoListUseCase` covering: happy path returns output with id+name+created_at; emits `todo_list.created` event with name and owner_id; duplicate name for same owner raises `TodoListAlreadyExistsError`. Use the existing user_repository / event_bus fixtures pattern. »
  - Use case `CreateTodoListUseCase` (publie `todo_list.created` via EventBus)
- *Check* : `pytest -m unit -k create_todo_list` vert ; `just mutate` sur `application/use_cases/create_todo_list.py` ≥ 90%.

**2.2 — CreateTodoList — route + e2e (≈ 20 min)**
- *Objectif* : route `POST /v1/todo-lists` protégée + container factory + tests e2e.
- *Skills* : `adding-auth`, `using-the-di-container`, `writing-tests` (e2e).
- *Actions* : `presentation/api/v1/todo_lists.py` avec `Depends(get_current_user)`, schema Pydantic, container factory `build_create_todo_list_use_case`, dependency wiring.
- *Check* : 3 e2e tests verts (201 avec token, 401 sans token, payload invalide → 422).

---

### Phase 3 — Persistence

**3.1 — Migration via agent (≈ 15 min)**
- *Objectif* : table `todo_lists` créée avec roundtrip clean.
- *Skills* : `database-and-migrations`.
- *Actions* : dispatch `soma-migration-writer` avec brief self-contained : « Create migration for table `todo_lists` (id UUID PK, owner_id UUID NOT NULL indexed, name VARCHAR(255) NOT NULL, created_at TZ-aware NOT NULL, deleted_at TZ-aware NULL). Test the upgrade/downgrade roundtrip. »
- *Check* : `just migrate → migrate-down → migrate` propre ; pas de drift detected.

**3.2 — SqlAlchemyTodoListRepository + integration tests (≈ 20 min)**
- *Objectif* : impl SQLAlchemy + tests d'intégration testcontainers via `soma-integration-test-writer`.
- *Skills* : `database-and-migrations`, `writing-tests`.
- *Actions* : model SQLAlchemy + repository impl + wire dans le container ; dispatch agent avec brief self-contained sur les 4 invariants à tester (round-trip, IntegrityError → DomainError, missing → None, find_by_owner scope).
- *Check* : integration tests verts ; le e2e de la phase 2 continue de passer avec le repo SQL en place.

---

### Phase 4 — TodoItem CRUD (state machine côté items)

**4.1 — AddTodoItem + state machine (≈ 25 min)**
- *Objectif* : `AddTodoItem`, `CompleteTodoItem`, `UncompleteTodoItem` use cases + leurs tests.
- *Skills* : `adding-a-use-case`, `tdd-workflow`, `writing-tests`.
- *Actions* : 3 use cases avec leurs DTOs + Fakes + tests unit + routes ; events `todo_item.added`, `todo_item.completed`, `todo_item.uncompleted` émis.
- *Check* : unit + e2e verts ; mutation 90% ; state machine test : complete 2× → `TodoItemAlreadyCompletedError`.

**4.2 — ChangeItemPriority + DeleteTodoItem + ListItems (≈ 25 min)**
- *Objectif* : 3 use cases peripheral + leurs tests.
- *Skills* : `adding-a-use-case`.
- *Actions* : même pattern. `DeleteTodoItem` émet `todo_item.deleted` ; `ListItems` est un GET (pas d'event, pas idempotent).
- *Check* : unit + e2e verts ; mutation 90%.

**4.3 — TodoItem persistence (≈ 20 min)**
- *Objectif* : migration + impl SQL + integration tests pour `TodoItem`.
- *Skills* : `database-and-migrations`, `writing-tests`.
- *Actions* : dispatch `soma-migration-writer` (table todo_items), puis impl + dispatch `soma-integration-test-writer`.
- *Check* : integration tests verts ; les 6 e2e du CRUD TodoItem passent avec le repo SQL.

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

**5.2 — ShareTodoList use case (≈ 25 min)**
- *Objectif* : `ShareTodoList` avec authz owner-only + NotificationSender + audit + event.
- *Skills* : `adding-a-use-case`, `adding-auth`.
- *Actions* :
  - `ShareTodoListUseCase` : load list, vérifie owner, crée `TodoListShare` row, appelle `NotificationSender.notify_shared`, émet `todo_list.shared`.
  - Migration + repo pour `TodoListShare` (dispatch agents)
  - Route `POST /v1/todo-lists/{id}/shares`
- *Check* : 4 tests (happy + not owner + share with self → error + repeated share idempotent) verts ; vérifier que `NotificationSender` est appelé une fois par share (Spy via Fake).

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

### Phase 7 — Use case complexe

**7.1 — MoveTodoItem domain logic (≈ 20 min)**
- *Objectif* : la méthode `TodoItem.move_to(to_list_id)` côté domain + tests unit.
- *Skills* : `writing-domain-code`.
- *Actions* : méthode pure sur l'entity, raise `CannotMoveCompletedItemError` si l'item est completed, no-op si déjà dans la cible. Tests unit (4 cas).
- *Check* : pytest unit pure-domain vert.

**7.2 — MoveTodoItem use case + e2e (≈ 25 min)**
- *Objectif* : use case multi-aggregate avec authz cross + atomicité.
- *Skills* : `adding-a-use-case`, `adding-auth`, `using-the-di-container`.
- *Actions* :
  - `MoveTodoItemUseCase` : load item + from_list + to_list ; vérifier authz **sur les deux listes** (owner ou sharee) ; vérifier `to_list.count_active < MAX_ITEMS_PER_LIST` ; appel `item.move_to(to_list_id)` ; save item ; émet `todo_item.moved`.
  - 6 tests : happy + actor non-autorisé sur from_list + actor non-autorisé sur to_list + to_list pleine + item inexistant + item déjà completed.
  - Route `PATCH /v1/todo-items/{id}/move` avec `to_list_id` dans le body.
- *Check* : 6 tests verts. **Question méta** : la skill `adding-a-use-case` t'a-t-elle bien guidé pour le cas multi-aggregate, ou tu as dû inventer le pattern ? Logge dans le rapport.

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

22 étapes au total, 15-30 min chacune. Chaque fin d'étape est un checkpoint commitable.

| Phase | Étapes | Cumulé |
|---|---|---|
| 0 — Setup | 1 étape × 15 min | 15 min |
| 1 — Domain | 4 étapes (20+25+10+15) | 1h10 |
| 2 — CreateTodoList | 2 étapes (25+20) | 45 min |
| 3 — Persistence TodoList | 2 étapes (15+20) | 35 min |
| 4 — TodoItem CRUD | 3 étapes (25+25+20) | 1h10 |
| 5 — Sharing + abstraction | 2 étapes (20+25) | 45 min |
| 6 — Outbox + idempotency | 2 étapes (15+15) | 30 min |
| 7 — MoveTodoItem (complex) | 2 étapes (20+25) | 45 min |
| 8 — Helm + observability | 2 étapes (15+15) | 30 min |
| 9 — Event sourcing TodoItem | 3 étapes (15+25+25) | 1h05 |
| 10 — Self-review + rapport | 2 étapes (15+15) | 30 min |
| **Total** | **22 étapes** | **~8h** |

Le total a augmenté (8h vs 5h30 précédent) parce que le découpage révèle des étapes qu'on avait sous-estimées. C'est le bon chiffre, pas une régression.

Découpage suggéré en sessions :
- **Session A — Foundation** (≈ 2h45) : phases 0 → 3 (setup, domain, premier use case, persistence)
- **Session B — Features** (≈ 2h30) : phases 4 → 6 (TodoItem CRUD, sharing, cross-cutting)
- **Session C — Complex + ES** (≈ 1h45) : phases 7 → 9 (multi-aggregate, helm, event sourcing)
- **Session D — Verdict** (≈ 30 min) : phase 10 (self-review + rapport final)

Pause possible entre n'importe quelles étapes via commit. Si une étape révèle un trou bloquant, je documente et passe à la suivante.

---

## Rapport final

*À compléter au fur et à mesure du walkthrough.*
