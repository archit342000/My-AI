# backend/auth
**Role:** Who is calling. Verifies the caller's identity, exposes the current user, and manages users.

## 📂 Files
| File | Purpose | Key Symbols |
| :--- | :--- | :--- |
| `providers.py` | Identity providers. `CloudflareAccessProvider` verifies the `Cf-Access-Jwt-Assertion` JWT (RS256, `aud`, `iss`, `exp`, `iat`, `email`); `StaticProvider` is development only. | `get_provider`, `Identity` |
| `context.py` | The current user (`{id, email, role}`) in a ContextVar, plus the admin-only route decorator. | `current_user`, `user_context`, `admin_required` |
| `cli.py` | `python -m backend.auth.cli add <email> [--role user\|admin] \| deactivate <email> \| list`. | `main` |

## ⚙️ Configuration (`backend/config.py`)
`AUTH_PROVIDER` (`cloudflare_access` default, or `static`), `CF_ACCESS_TEAM_DOMAIN` (for example `myteam.cloudflareaccess.com`), `CF_ACCESS_AUD` (the Access application AUD tag), `ADMIN_EMAIL` (seeded as the admin by `init_db()`), `AUTH_STATIC_EMAIL` (static provider; defaults to `ADMIN_EMAIL`). The app refuses to start when they are inconsistent.

## 🧩 Architectural Context
*   `app.py`'s `authenticate_request` hook calls the provider on every request, WebSocket upgrades included: no identity is 401, an unknown or inactive user is 403. `GET /api/me` returns `{id, email, role}`.
*   `backend/auth/__init__.py` re-exports nothing (import cycle with `backend.logging`); import from the submodules.
*   Keys rotate; the JWKS is cached for 5 minutes. A JWKS outage fails closed (401, logged as `auth_jwks_error`).
*   `ADMIN_EMAIL` is additive: `init_db()` promotes and re-activates that address on every start and never demotes others. After changing it, deactivate the old admin with the CLI (the CLI refuses to deactivate the current `ADMIN_EMAIL`).
*   `log_event` entries carry `user_id` while a request is handled (streamed bodies included, via `after_request` `bind_user_to_stream`). Threads and background tasks record null until they run inside `user_context`.
*   Users live in the `users` table (`backend/database/wrapper/user_ops.py`).

## 🧪 Testing
*   `tests/test_providers.py`, `tests/test_context.py`, `tests/test_cli.py`.
*   **Run Tests:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. ./venv/bin/python -m pytest backend/auth/`
