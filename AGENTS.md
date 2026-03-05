# [Nom du projet]

> Ce fichier fournit le contexte du projet aux outils IA.
> Gardez-le à jour à chaque changement significatif d'architecture ou de stack.
> Pour les outils qui ne le lisent pas automatiquement, copiez-collez son contenu en début de session.

## Projet

**Description :** [Décrivez en 2-3 phrases ce que fait le projet et sa valeur métier]

**Stack technique :**
- Langage : Python 3.13
- Framework principal : [ex: FastAPI 0.115]
- Base de données : [ex: PostgreSQL 17]
- Autres dépendances clés : [ex: Redis, Celery, SQLAlchemy]

**Structure du projet :**
```
[Coller ici l'arbre du projet — ex: src/, tests/, docs/]
```

## Conventions obligatoires

### Git
- **Conventional Commits** : `<type>[scope]: <description>`
- Types autorisés : `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`, `perf`
- **Jamais de commit direct sur `main`**
- Nommage des branches : `feature/`, `fix/`, `hotfix/`, `docs/`, `refactor/`
- PRs obligatoires, reviewées par quelqu'un d'autre que l'auteur

### Code
- Fonctions de **25 lignes maximum**
- **Pas de duplication** de code
- Nommage **explicite** (pas d'abréviations obscures)
- Linter : `ruff` + type checker : `mypy` (configurés dans `pyproject.toml`)

### Tests
- Tests écrits avant ou en même temps que le code (TDD si possible)
- CI bloque le merge si les tests échouent

### Sécurité
- **Aucun secret dans le code** (tokens, mots de passe, clés API)
- Variables d'environnement pour toute configuration sensible
- Fichier `.env` dans `.gitignore`

## Ce qu'il ne faut surtout pas faire

- Commiter directement sur `main`
- Utiliser `git push --force`
- Contourner le linter (`# noqa`, `# type: ignore`) sans justification dans un commentaire
- Merger sans que les tests CI passent
- Inclure des données réelles (clients, production) dans les exemples ou les tests
- Coller des secrets dans les prompts IA

## Informations pratiques

**Installer les dépendances :**
```bash
uv sync
```

**Lancer le projet en local :**
```bash
[commandes pour démarrer le projet]
```

**Lancer les tests :**
```bash
uv run pytest
```

**Linter + format :**
```bash
uv run ruff check .
uv run ruff format .
```

**Documentation technique :** [lien si disponible]
**CI/CD :** GitHub Actions — qualité (ruff + mypy + pytest) + sécurité (bandit + pip-audit + gitleaks) + conventional commits
