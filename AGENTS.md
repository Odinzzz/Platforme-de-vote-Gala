# Repository Guidelines

## Project Structure & Module Organization
- `run.py` boots the Flask app and registers public/admin blueprints.
- Core packages live under `routes/`, `models/`, `templates/`, and `static/`. Admin-specific views sit in `routes/admin_routes.py`, `templates/admin/`, and `static/js/admin_users.js`.
- Database artifacts and schema scripts are in `data/`; automated tests reside in `tests/` with shared fixtures in `tests/conftest.py`.

## Build, Test, and Development Commands
- `& "venv\Scripts\python.exe" run.py` — start the development server with hot reload enabled.
- `& "venv\Scripts\python.exe" -m pytest` — execute the full test suite, covering auth and admin flows.
- `python -m models.init_db` — recreate the SQLite database from `data/schema.sql` (run from repo root).

## Coding Style & Naming Conventions
- Python: 4-space indentation, snake_case functions, PascalCase classes. Reuse existing blueprint/module naming (e.g., `*_routes.py`).
- Templates: prefer lowercase hyphenated filenames inside `templates/` (e.g., `admin/users.html`).
- JavaScript/CSS in `static/` follows camelCase for variables and keeps files ASCII-only.

## Testing Guidelines
- Pytest is the standard; place new tests under `tests/` mirroring the module under test (`tests/test_admin.py`, `tests/test_auth.py`).
- Use fixtures via `tests/conftest.py` for DB setup. Run `& "venv\Scripts\python.exe" -m pytest` before committing.

## Commit & Pull Request Guidelines
- Commit messages are imperative and concise (e.g., `Affiche le menu admin des connexion`). Group related changes together.
- Pull requests should describe user-facing changes, note testing performed, and include screenshots/GIFs for UI updates when practical.

## Security & Configuration Tips
- Keep secrets out of the repo; `app.secret_key` in `run.py` should be overridden via environment variables in production.
- Regenerate the SQLite database with `models.init_db` when schema changes land, and ensure new roles or fixtures align with `routes/admin_routes.py` logic.
