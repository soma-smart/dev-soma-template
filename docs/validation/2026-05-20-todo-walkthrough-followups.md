# SOMA Template — Walkthrough follow-ups

- **Date** : 2026-05-20
- **Source** : `docs/validation/2026-05-20-todo-walkthrough.md` (Phase 1)
- **Status** : Backlog, à traiter après la fin du walkthrough

Cette liste regroupe toutes les actions identifiées pendant le walkthrough qui doivent être appliquées **au niveau du template** (donc dans `dev-soma-template`, pas dans le projet généré). Chaque item indique le fichier ou la skill à éditer.

---

## P0 — Bugs template critiques (à fixer avant prochain usage SOMA réel)

**Statut 2026-05-20 (après-midi)** : tous les P0 ont été fixés directement dans la branche `rework`. Les sections ci-dessous gardent le diagnostic pour traçabilité, et chaque item porte ✅ + le SHA du commit de fix.

### 1. ✅ Config `[tool.mutmut]` invalide
- **Fichier** : `{{cookiecutter.project_slug}}/pyproject.toml`
- **Problème** : `paths_to_mutate` et `tests_dir` sont des strings, mutmut 3.5+ exige des listes. Le `also_copy` manque, donc mutmut tente de copier `/sys/class/powercap/intel-rapl:1` (chemin du kernel powercap) et plante.
- **Bug récurrent** : déjà observé lors du walkthrough précédent du 2026-05-12. Toujours pas fixé.
- **Fix** :
  ```toml
  [tool.mutmut]
  paths_to_mutate = ["src/{{ cookiecutter.package_name }}/domain", "src/{{ cookiecutter.package_name }}/application"]
  also_copy = [
      "src/{{ cookiecutter.package_name }}/infrastructure",
      "src/{{ cookiecutter.package_name }}/presentation",
      "src/{{ cookiecutter.package_name }}/__init__.py",
      "tests",
      "pyproject.toml",
      "uv.lock",
      "alembic",
      "alembic.ini",
  ]
  runner = "uv run pytest -m unit -x -q"
  tests_dir = ["tests/unit"]
  ```

**Fix appliqué (commit `17579f2`)**.

### 2. ✅ `models/__init__.py` ne register pas tous les modèles
- **Fichier** : `{{cookiecutter.project_slug}}/src/{{cookiecutter.package_name}}/infrastructure/persistence/models/__init__.py`
- **Problème** : Le fichier n'importe que `Base`. Les modèles concrets (`UserModel`, `OutboxEventModel`, `IdempotencyRecord`) ne sont chargés "par accident" que via les imports des repositories. Conséquence : quand un nouveau modèle apparaît sans repository, `alembic revision --autogenerate` ne le voit pas. Pire, l'import manuel d'**un seul** nouveau modèle fait apparaître les autres comme "supprimés" → migration destructrice.
- **Fix** : importer tous les modèles dès le bake initial, avec `# noqa: F401` :
  ```python
  from {{ cookiecutter.package_name }}.infrastructure.persistence.models import (  # noqa: F401
      idempotency_record as _idempotency_record,
  )
  from {{ cookiecutter.package_name }}.infrastructure.persistence.models import (  # noqa: F401
      outbox_event as _outbox_event,
  )
  from {{ cookiecutter.package_name }}.infrastructure.persistence.models import (  # noqa: F401
      user as _user,
  )
  from {{ cookiecutter.package_name }}.infrastructure.persistence.models.base import Base
  ```
  Documenter dans le commentaire du module qu'**EVERY new model must be added here**.

**Fix appliqué (commit `71c5c34`)**.

### 3. ✅ Drift modèles ↔ migrations existantes
- **Fichiers** :
  - `{{cookiecutter.project_slug}}/alembic/versions/0001_init_users.py` (lignes `create_unique_constraint` + `create_index` séparés pour `email`)
  - `{{cookiecutter.project_slug}}/alembic/versions/0002_init_outbox.py` (noms d'index `ix_outbox_*` vs ce que SQLAlchemy autogenererait `ix_outbox_events_*`)
- **Problème** : autogenerate détecte une différence permanente entre ce que les modèles déclarent et ce que les migrations existantes ont créé. Toute future migration aura du bruit (drops + creates parasites) à nettoyer manuellement.
- **Fix** : aligner les migrations sur ce que les modèles produisent par défaut. Le test `ci-migration-drift.yml` devrait être ajouté ou activé pour détecter ce drift.

**Fix appliqué (commit `0cf2a07`)**. Autogenerate sur projet baké frais produit désormais un migration vide.

### 4. ✅ `just lint` échoue sur projet baké à J+0
- **Fichiers concernés** : `infrastructure/auth/dev_token.py`, `infrastructure/auth/jwt_verifier.py`, `infrastructure/jobs/backoff.py`, `tests/integration/conftest.py`, `tests/integration/infrastructure/auth/test_jwt_verifier.py`, `tests/integration/jobs/test_outbox_relay.py`, `tests/integration/middleware/test_idempotency.py`, `tests/unit/application/test_create_user_use_case.py`, `tests/unit/presentation/test_auth_dependencies.py`, `tests/e2e/api/test_health_endpoints.py`.
- **Problème** : 20 erreurs lint (S106 mots `token`/`secret` dans args de test, B008 default arg=`Field`, D101/D102 docstrings manquants). Un nouveau projet SOMA ne passe pas son propre lint dès le `git init`.
- **Fix** : soit corriger les erreurs (préférable), soit étendre `[tool.ruff.lint.per-file-ignores]` :
  ```toml
  [tool.ruff.lint.per-file-ignores]
  "tests/**" = ["S101", "S106", "PLR2004", "D101", "D102", "D103"]
  ```
  Approche raisonnable : ignorer S106 et la plupart des D* sur `tests/**`, fixer les vraies erreurs dans `infrastructure/`.

**Fix appliqué (commit `a5bad00`)**. Per-file-ignores étendus pour les tests + 4 corrections source (jwt_verifier, backoff, dev_token, idempotency middleware).

### 5. ✅ Devcontainer mount stale après bake successif
- **Fichier** : `{{cookiecutter.project_slug}}/.devcontainer/post-up.sh` ou nouveau script `down.sh`
- **Problème** : après un premier bake + `docker compose up`, un deuxième bake vers un autre `/tmp` réutilise les conteneurs Docker existants avec le mount du précédent workspace → `chdir /workspaces/<slug>: no such file or directory`.
- **Fix** : documenter (README ou runbook) que `docker compose down -v` doit précéder tout nouveau bake quand on travaille via plain `docker compose` plutôt que le devcontainer CLI. Alternativement, ajouter une recette `just devcontainer-reset` qui fait le `down -v` + `up -d --build` proprement.

---

**Fix appliqué (commit `be438e4`)**. Nouvelle recette `just devcontainer-reset`.

## P1 — Améliorations skills

**Statut 2026-05-20 (fin d'après-midi)** : 3 des 4 items doc-only sont fixés. Reste l'item #7 qui nécessite une décision utilisateur (réintroduire ou non un sub-agent `soma-feature-planner`).

### 6. ✅ Skill `building-a-feature` : durcir la règle "no domain pre-decision in plan"
- **Fichier** : `{{cookiecutter.project_slug}}/.claude/skills/building-a-feature/SKILL.md`
- **Problème** : malgré la section "What does NOT go in the plan" qui interdit déjà class names / Protocol method names / etc., le main agent a quand même listé des bullets "Le VO `name` rejette …" lors du plan v1 de Phase 1. Le user a dû corriger ("c'est du TDD ça DOIT découler des tests"). Indique que la règle n'est pas assez visible / saillante dans la skill.
- **Fix** :
  - Ajouter un encart en haut de la section "The 5-section plan" : "⚠ The Tests section is at use case level ONLY. Adding 'domain drill' bullets is a leak."
  - Ajouter un mauvais exemple explicite : "❌ `Le VO Name rejette les blancs` → ✅ `WHEN creating with a blank name THEN raises validation error`"

**Fix appliqué (commit `7c07a67`)**. Callout en tête de § 3 du plan + exemple bad/good.

### 7. 🤔 Évaluer un sub-agent `soma-feature-planner` *(décision utilisateur)*
- **Contexte** : le user avait proposé un sub-agent dédié au planning en contexte frais, on a retiré ce sub-agent lors du trim. Le walkthrough confirme que le main agent a un biais d'accumulation : il pré-décide des structures domain malgré les règles. Un agent en contexte frais n'aurait que la skill et les Q&A — pas l'historique des features précédentes.
- **Décision à prendre** : remettre un sub-agent `soma-feature-planner` (one-shot, Read/Grep/Glob uniquement) ? Le seul sub-agent du template, justifié par l'enforcement de discipline.
- **Si oui** : ajouter `{{cookiecutter.project_slug}}/.claude/agents/soma-feature-planner.md` + mettre à jour bake test + spec §18.

### 8. ✅ Skill `building-a-feature` : ajout d'un pattern "Mutmut context kwargs"
- **Fichier** : `{{cookiecutter.project_slug}}/.claude/skills/building-a-feature/SKILL.md` (section Mutate)
- **Problème** : Mutmut signale comme survivants les mutations sur les kwargs de `DomainError(...)` (e.g. `raise InvalidNameError(length=N)` → `length=None`). Ces mutations sont sémantiquement bénignes (le context sert au log), mais comptent dans le kill rate. Pour atteindre 90% il faut soit asserter sur `.context[...]`, soit configurer mutmut pour exclure ces mutations.
- **Fix** : documenter le choix (asserter pour le rigueur, exclure si le bruit nuit). Mention explicite "Si tu choisis d'asserter, ajoute systématiquement `assert excinfo.value.context['<key>'] == ...` après le `pytest.raises`".

---

## P2 — Nice-to-have

### 9. Recette `just mutate-show <id>` pour montrer un mutant
- **Fichier** : `{{cookiecutter.project_slug}}/justfile`
- **Problème** : `uv run mutmut show <full-id>` est verbeux et le full-id contient un caractère unicode bizarre `ǁ`. Un alias `just mutate-show 3` qui résout automatiquement le full-id serait plus pratique.

### 10. Sortie mutmut TUI moins bruyante
- **Problème** : les spinners + compteurs s'affichent à chaque tick, saturant la sortie quand on copie le log. Ce serait mieux avec `--quiet` par défaut dans `just mutate` ou une vue résumée à la fin.

---

## Décisions à valider avec le user

- [ ] **Item 7** : remettre un sub-agent `soma-feature-planner` ou pas ? Le walkthrough confirme l'argument du user mais le trim agressif avait été validé. **Seul item P1 encore ouvert.**
- [x] **Item 4** : approche pour le lint baked-project — **les deux** : per-file-ignores étendus sur `tests/**` (S105, S106, PLR0913) + 4 corrections de source dans `infrastructure/` et `presentation/`. Commit `a5bad00`.
- [x] **Item 8** : asserter sur `.context[...]` systématiquement → **rigueur retenue** (la checklist de `tdd-workflow` § Mutate documente le trade-off mais oriente vers l'assertion systématique pour rester au-dessus du seuil 90%). Commit `31b1af5`.

---

## Ajouts Phase 2 (2026-05-20 après-midi)

### P0 nouveaux

### 11. ✅ Idempotency middleware non-testable en e2e
- **Fichier** : `{{cookiecutter.project_slug}}/.claude/skills/building-a-feature/SKILL.md` § Idempotency + `{{cookiecutter.project_slug}}/tests/e2e/conftest.py`
- **Problème** : `IdempotencyMiddleware` lit `app.state.session_factory` qui est setté par le FastAPI lifespan. Le fixture `client` en e2e bypasse le lifespan exprès (pour éviter un vrai DB engine + instrumentation OTel). Conséquence : impossible d'écrire un test e2e qui démontre `Idempotency-Key` replay — le middleware log `idempotency.no_session_factory` et by-pass.
- **Fix** : deux options :
  - (a) **Documenter** dans la skill que l'idempotency replay est validé via `tests/integration/middleware/test_idempotency.py` (real PG via testcontainers), pas via les e2e endpoint-par-endpoint. Le rôle des e2e reste "wiring + status codes", pas "feature complète du middleware".
  - (b) **Ajouter un fixture** `app_with_real_session` qui démarre le lifespan + pointe sur un testcontainer Postgres, pour les rares tests e2e qui doivent traverser le middleware. Plus complexe, peut-être overkill.

**Fix appliqué (commit `c115663`)**. Limitation documentée dans § Idempotency de la skill.

### P1 nouveaux

### 12. ✅ Skill `building-a-feature` : pattern "Aggregate avec children"
- **Fichier** : `{{cookiecutter.project_slug}}/.claude/skills/building-a-feature/SKILL.md` (nouvelle section)
- **Problème** : la skill décrit bien le pattern "use case → repo.find_by_id → mutation → save()" pour des aggregates "plats" (User). Pour TodoList avec ses items, il a fallu déduire : `selectinload(items)` à la lecture, `cascade="all, delete-orphan"` + `lazy="selectin"` sur la relationship, diff items par id à l'écriture. Tout ça n'est documenté nulle part dans le template.
- **Fix** : ajouter une section "Aggregates with nested children" dans `building-a-feature` qui montre :
  - le `relationship(..., cascade="all, delete-orphan", lazy="selectin", order_by=...)` côté ORM
  - le `selectinload(Parent.children)` côté `find_by_id`
  - le pattern de `save()` qui diffe les enfants par id (update existants + insert nouveaux + delete enlevés)
  - Exemple complet, ~50 lignes.

**Fix appliqué (commit `6ea6798`)**. Nouvelle sous-section "Aggregates with nested children" avec relationship + selectinload + save-diff worked example.

### 13. ✅ Skill `tdd-workflow` § Mutate : checklist "kill the obvious"
- **Fichier** : `{{cookiecutter.project_slug}}/.claude/skills/tdd-workflow/SKILL.md` § Mutate
- **Problème** : Phase 1 et Phase 2 ont produit les mêmes types de mutants survivants : (a) boundary off-by-one (`>` vs `>=`), (b) context kwargs des `DomainError` mutés en `None`, (c) `CreateXOutput.field = None` non détecté car aucun test n'asserte sur l'output. Sans une checklist explicite, chaque dev tombera dans le même piège et passera 10-15 min à investiguer "pourquoi 86% au lieu de 90%".
- **Fix** : ajouter dans `tdd-workflow` § Mutate une sous-section "Tests à ajouter pour passer 90% naturellement" avec les patterns :
  1. Pour chaque bornes `len(x) > N` : un test "exactly N succeeds", un test "exactly N+1 fails"
  2. Pour chaque `raise SomeError(key=value)` : un test qui assert sur `excinfo.value.context["key"]`
  3. Pour chaque DTO Output retourné : un test par champ (id, name, …) qui assert `output.<field> == <expected>`
- Pourrait aussi mentionner que ces tests font 10-15 lignes chacun et sont systématiquement nécessaires.

### Décisions Phase 2

- [x] **Item 11** : option (a) retenue — docs explicite dans `building-a-feature` § Idempotency que le replay est validé via le test d'intégration du middleware seul. Commit `c115663`.
- [x] **Item 12** : section ajoutée tout de suite — le pattern est suffisamment validé par la Phase 2 et chaque nouvelle feature avec un aggregate-with-children tombera dans le même cas. Commit `6ea6798`.
- [x] **Item 13** : checklist ajoutée — clairement utile vu la répétition Phase 1 → Phase 2. Commit `31b1af5`.
