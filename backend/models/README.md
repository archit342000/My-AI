# backend/models
**Role:** Backend-side view of the model registry: exposes model configuration to the app and forwards model-management requests to the inference proxy.

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Model config loading, per-role model getters, and the `/api/models` pass-through blueprint (the model list is open; load, unload and other non-GET calls are admin only; the caller's Access JWT, cookies and Authorization are never forwarded). | `models_bp`, `load_model_config`, `get_embedding_model`, `get_model_metadata` |

## 🧩 Architectural Context
*   **Dependencies:** `backend.config` (`AI_PROXY_URL`), `requests`.
*   **Flow:** Model lifecycle (loading, unloading, swapping) and the registry live in `inference_proxy/`. `load_model_config()` fetches `/api/models/config` from the proxy, caches it, and falls back to `inference_proxy/config.json`, then to a hardcoded default. All `/api/models/*` requests are streamed through to the proxy unchanged.

## 🛠️ Usage & Conventions
*   **Registry-first:** select models through the getters (`get_general_text_model`, and so on); never hardcode model names.
*   **Tests:** `tests/test_models.py`.
