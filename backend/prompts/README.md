# backend/prompts
**Role:** Centralized prompt management, composition, templating, and validation.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `templates/` | Plain-text prompt templates using XML-based tags and standard placeholders. |
| `tests/` | Unit tests for prompt loading, placeholder validation, and few-shot formatting. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `loader.py` | Centralized prompt template loading and interpolation logic. | `PromptLoader` |

## 🧩 Architectural Context
*   **Dependencies:** `backend.config`, PyYAML.
*   **Flow:** The `PromptBuilder` and sub-agents retrieve text templates from this directory via `PromptLoader`, which interpolates runtime context and can inject YAML few-shot examples when an `examples.yaml` is present.

## 🛠️ Usage & Conventions
*   **Patterns:** Text templates must adhere to strict XML tag schemas.
*   **Testing:** Local unit tests inside `tests/` and offline evaluations via `scripts/run_evals.py`.
