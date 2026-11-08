# 🌌 My-AI v5.0.0


A high-performance, Multi-Agent AI Workspace natively powered by [llama.cpp](https://github.com/ggerganov/llama.cpp) for deep autonomy and statful collaboration. My-AI seamlessly unifies specialized agents for research, autonomous web browsing, file attachments, and long-term semantic memory with a virtualized agentic file system, creating a premium chat interface running entirely on local hardware. The multi-agent orchestration offloads complex tasks to transient agents, thus preserving the context window. This allows for long conversations without the AI losing coherence. 

## ✨ Core Logic & Features

*   **Multi-Agent System**: A unified chat interface that seamlessly routes tasks to specialized agents:
    *   **Research Agent**: A multi-pass autonomous engine that scouts context, designs a research plan, executes targeted searches, and synthesizes reports—operating entirely within the normal chat flow so conversations can continue naturally.
    *   **Autonomous Browsing Agent**: Utilizes a headless Playwright browser for complex, multi-step web interactions and data extraction.
    *   **Web Search & Visit Page Agents**: Upgraded tools that use an agentic architecture for autonomous summarization and answering queries, significantly reducing AI context window usage.
    *   **File System Agent**: Manages a virtualized true file system capable of handling complex file operations (CRUD, search, move) across virtualized paths, ensuring state is preserved across sessions with built-in versioning and concurrency locking. The files in this system can be accessed and organized through the frontend and edited using a built-in code editor with support for version history management.
    *   **Document & File Agent**: Handles user-uploaded files, intelligent file reading, multi-modal analysis, OCR for scanned PDFs, and integrates with the RAG system (Hybrid Search with BM25 + Vector and syntax-aware code chunking) to enable semantic recall.
    *   **Git Agent**: An autonomous Git operations specialist capable of managing repositories, performing clones, checkout, branch operations, commits, status, and logging safely inside virtual system paths with secure environment shielding.
    *   **Code Runner Agent**: A secure sandboxed environment for compiling and executing multi-file scripts (supporting Python, Node.js, C/C++, Java, Go, Rust, and PHP) with safety static analysis, isolated container executions, and dynamic package installation (`/install`; currently fails because the runner has no outbound network, see `code_runner_mcp/README.md`).
*   **System-Wide Skill Store**: Empower users to define, manage (CRUD), and trigger custom instructions (skills) globally. Includes a premium autocomplete command-line menu triggering on `/` with smooth keyboard/Tab navigation, system tags, zero-latency client-side interceptors (for `/help` and `/skills`), and structured in-memory prompt compilation boundaries (`[SKILL: {name}]...[/SKILL]`) to isolate instruction context cleanly for inference.
*   **Performance Profiling**: Built-in LLM benchmarking tool to measure TTFT and TPS directly from the UI.
*   **Multimodal VLM Support**: Native handling of vision payloads for image analysis, OCR, and scene description.
*   **Thought Streaming**: Interactive rendering of model "chain-of-thought" blocks.

## 🛠️ Technical Specifications

*   **Inference Engine**: [llama.cpp](https://github.com/ggerganov/llama.cpp) (Server Mode)
*   **Retrieval**: **Hybrid Search** leveraging **ChromaDB** (Vector) and **BM25** (Lexical).
*   **Persistent Storage**: **SQLite** for conversation metadata and history.
*   **Research Infrastructure**: 
    *   **Tavily API** for high-precision web search and link discovery.
    *   **MCP Architecture**: Decoupled worker containers for search (`tavily_mcp`), scraping (`playwright_mcp`), and sandboxed code execution (`code_runner_mcp`).
*   **Backend**: Python 3.12 (Flask) with a modular domain-driven architecture.
*   **Frontend**: React 19 + TypeScript single-page app built with Vite (`frontend/`). The previous vanilla UI remains at `/legacy/` for one release.

## 📋 Prerequisites

*   **llama.cpp Server**: Must be running and accessible (default port `8080`).
*   **Recommended Models** (as defined in `backend/models/config.json`):
    *   **Reasoning/Chat (Main/Research)**: `NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL`
    *   **Coding**: `Qwen/Qwen3-Coder-Next-UD-Q4_K_XL`
    *   **Vision**: `Qwen/Qwen3.6-35B-A3B-UD-Q4_K_XL`, `Qwen/Qwen3.5-122B-A10B-UD-Q2_K_XL`, or `Google/Gemma4-26B-A4B-it`
    *   **Embedding**: `embeddinggemma/embeddinggemma-300M-Q8_0`
*   **Tavily API**: Required for web search and deep research functionality.

## 🚀 Installation & Setup

> **Frontend:** the UI is built with Node 22+ (`cd frontend && npm ci && npm run build`). The Docker image builds it automatically. Set `FRONTEND=legacy` to serve the old UI. See `docs/frontend.md`.


### 1. Repository Setup
```bash
git clone https://github.com/archit342000/My-AI.git
cd My-AI
mkdir -p secrets
```

### 2. Configuration (Docker Secrets)
Map your configuration values into the `secrets/` directory. These files are securely injected as Docker Secrets:
```bash
echo "http://host.docker.internal:8080" > secrets/AI_URL
echo "http://host.docker.internal:8080" > secrets/EMBEDDING_URL
echo "your_tavily_api_key_here" > secrets/TAVILY_API_KEY
echo "your_mcp_key_here" > secrets/MCP_API_KEY
echo "your_playwright_key_here" > secrets/PLAYWRIGHT_MCP_API_KEY
echo "/app/backend/data" > secrets/DATA_DIR
echo "optional_password" > secrets/APP_PASSWORD
cat ~/.ssh/id_rsa.pub > secrets/authorized_keys
# Optional: echo "your_key" > secrets/AI_API_KEY
# Optional: echo "your_key" > secrets/EMBEDDING_API_KEY
# Optional: echo "your_hf_token" > secrets/HF_TOKEN
```

### 3. Deploy Stack
```bash
docker compose -f docker/docker-compose.yml up --build -d
```
The application will be accessible at `http://localhost:5000` (or via the Bastion SSH tunnel on port `2222`).

## 🏗️ Architecture Note
My-AI utilizes the **Model Context Protocol (MCP)** to isolate external tool executions. The main Flask app acts as a secure orchestrator, while dedicated containers handle web search, PDF extraction, browser-level scraping, and sandboxed code execution, ensuring high stability and a reduced security surface area.

## 🧑‍💻 Development
*   Start with `AGENTS.md`; rules, tests, lint and release steps are in `docs/`. Run `scripts/check.sh` before pushing.

## 📄 License & Versioning
This project follows [SemVer v2.0.0](https://semver.org/).  
The current version is defined in `backend/version.py` (also reported by `/api/version`).

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `app.py` | Main application entry point and Flask app initialization. | `app`, `rag_manager`, `file_manager` |

## 🧪 Testing
| Test File | Scope |
| :--- | :--- |
| `tests/test_app.py` | Core application initialization, route testing, and WebSocket proxying. |

*   **Run Application Tests:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. ./venv/bin/python -m pytest tests/`

## 🛠️ Usage & Conventions
*   **Patterns:** Follow domain-driven modularity. Each feature area is encapsulated in its own blueprint.
*   **Testing:** New additions must maintain 1:1 test parity and pass without regressions.
