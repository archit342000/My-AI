# 🌌 My-AI v2.4.0

A high-performance local AI orchestration layer and premium chat interface natively powered by [llama.cpp](https://github.com/ggerganov/llama.cpp). My-AI combines autonomous research capabilities, long-term semantic memory, and multimodal vision into a single, unified workspace running entirely on your local hardware.

## 🛠️ Technical Specifications

*   **Inference Engine**: [llama.cpp](https://github.com/ggerganov/llama.cpp) (Server Mode)
*   **Vector Database**: **ChromaDB** for RAG-based long-term memory.
*   **Persistent Storage**: **SQLite** for conversation metadata and history.
*   **Research Infrastructure**: 
    *   **Tavily API** for high-precision web search and link discovery.
    *   **MCP Architecture**: Decoupled worker containers for search (`tavily_mcp`) and scraping (`playwright_mcp`).
*   **Backend**: Python 3.12 (Flask) with asynchronous task management.
*   **Frontend**: Strictly Vanilla HTML5, CSS3, and ES6+ Javascript.

## ✨ Core Logic & Features

*   **Deep Research Agent**: A multi-pass autonomous engine that scouts context, designs a research plan, executes targeted searches, and performs a self-audit before synthesizing the final report.
*   **Autonomous Scraping**: Utilizes a headless Playwright browser to navigate complex JS-heavy websites and extract clean markdown content.
*   **Intelligent RAG**: Automatically embeds and retrieves facts from previous conversations to maintain long-term context without manual prompting.
*   **Multimodal VLM Support**: Native handling of vision payloads for image analysis, OCR, and scene description.
*   **Thought Streaming**: Interactive rendering of model "chain-of-thought" blocks with real-time markdown and syntax highlighting.

## 📋 Prerequisites

*   **llama.cpp Server**: Must be running and accessible (default port `8080`).
*   **Recommended Models**:
    *   **Reasoning/Chat**: `NVIDIA-Nemotron-3-Nano-30B` or `Qwen 3.5`.
    *   **Coding**: `Qwen 3 Coder Next`.
    *   **Vision**: `Qwen 3.5 VL`.
    *   **Embedding**: `embeddinggemma-300M-Q8_0`.
*   **Tavily API**: Required for web search and deep research functionality.

## 🚀 Installation & Setup

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
echo "your_tavily_api_key_here" > secrets/TAVILY_API_KEY
echo "your_mcp_key_here" > secrets/MCP_API_KEY
echo "your_playwright_key_here" > secrets/PLAYWRIGHT_MCP_API_KEY
echo "/app/backend/data" > secrets/DATA_DIR
echo "optional_password" > secrets/APP_PASSWORD
cat ~/.ssh/id_rsa.pub > secrets/authorized_keys
# Optional: echo "your_key" > secrets/AI_API_KEY
```

### 3. Deploy Stack
```bash
docker compose up --build -d
```
The application will be accessible at `http://localhost:5000` (or via the Bastion SSH tunnel on port `2222`).

## 🏗️ Architecture Note
My-AI utilizes the **Model Context Protocol (MCP)** to isolate external tool executions. The main Flask app acts as a secure orchestrator, while dedicated containers handle web search, PDF extraction, and browser-level scraping, ensuring high stability and a reduced security surface area.

## 📄 License & Versioning

This project follows [SemVer v2.0.0](https://semver.org/). Current version: `v2.4.0`.
See [CHANGELOG.md](./changelog.md) and [docs/versioning_directives.md](./docs/versioning_directives.md) for a detailed history of updates and versioning rules.
