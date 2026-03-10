# 🌌 My-AI v1.7.1

A premium, full-stack AI chat interface designed for local inference with [LM Studio](https://lmstudio.ai/). This application provides a high-fidelity Luminous Material interface for interacting with local LLMs, featuring persistent state, long-term memory, and an advanced deep research agent.

## ✨ Features

*   **Deep Research Agent**: A multi-pass ($n+1$) autonomous research engine that browses the live web using [Tavily](https://tavily.com/), discovers links, and compiles structured reports.
*   **Intelligent Memory (RAG)**: Long-term semantic memory powered by **ChromaDB**. The AI automatically remembers facts from previous conversations to maintain context.
*   **Multimodal Vision**: Seamlessly attach and analyze images. Compatible with vision-enabled models (e.g., Llama 3.2 Vision, Qwen 2 VL).
*   **Persistent SQLite Backend**: All conversations and metadata are stored in a local SQLite database for instant retrieval and management.
*   **Luminous Design System**:
    *   **Glassmorphism Branding**: Modern, airy, and high-performance UI.
    *   **True Dark Mode**: Smooth theme transitions with system preference detection.
    *   **Responsive Motion**: Motion-first interactions and fluid layouts (Mobile, Tablet, Desktop).
*   **Real-time Logic**: Streaming Markdown rendering with Highlight.js syntax highlighting and interactive "Thought Process" (Reasoning) blocks.

## 🛠️ Prerequisites

*   **Python 3.10+**
*   **LM Studio**: Running with the local server active (default port `1234`).
*   **Models**: 
    *   A tool-calling capable chat model (e.g., Llama 3.1+, Mistral, Qwen).
    *   An embedding model for RAG (e.g., `text-embedding-embeddinggemma-300m`).
    *   (Optional) A vision model for image analysis.
*   **Search API**: A [Tavily API Key](https://tavily.com/) is required for Deep Research mode.

## 🚀 Installation & Setup (Docker / Containerized)

This application is fully containerized and runs with user-level permissions for strict security mapping data to a local `user_data` volume. Configuration values and sensitive keys are passed dynamically as Docker Secrets.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/My-AI.git
    cd My-AI
    ```

2.  **Configure Environment (Docker Secrets)**:
    Create a `./secrets/` directory and map your configuration files. You will also need to add your SSH public key to authenticate with the containerized Bastion Host.
    ```bash
    mkdir -p secrets
    echo "http://host.docker.internal:1234" > secrets/LM_STUDIO_URL
    echo "your_tavily_api_key_here" > secrets/TAVILY_API_KEY
    echo "your_lm_studio_api_key_here" > secrets/LM_STUDIO_API_KEY  # Optional
    echo "/app/backend/data" > secrets/DATA_DIR                     # Default container mapped volume
    echo "your_secret_password" > secrets/APP_PASSWORD              # Optional, enables HTTP Basic Auth
    cat ~/.ssh/id_rsa.pub > secrets/authorized_keys                 # Add your public key for the Bastion Host
    ```
    
    *Optional Settings via `.env` file (Not Secrets)*
    You can create an `.env` file in the root for non-sensitive tweaks:
    ```env
    EMBEDDING_MODEL=text-embedding-embeddinggemma-300m
    TAVILY_BASE_URL=https://api.tavily.com
    ```

## 🎮 Usage

1.  **Start LM Studio**: Ensure your models are loaded and the local server is running on the host machine.
2.  **Build and Launch with Docker Compose**:
    ```bash
    docker compose up --build -d
    ```
3.  **Connect Securely**: The application does not expose ports directly. SSH into the Bastion container from your local machine to establish a secure tunnel and explore at `http://localhost:5000`:
    ```bash
    ssh -N -L 5000:app:5000 -p 2222 appuser@YOUR_SERVER_IP
    ```
    To stop the container, use `docker compose down`.

## 🏗️ Architecture

*   **Frontend**: Vanilla HTML5, CSS3 (Custom Properties), and Modern JS (ES6+). No heavy frameworks.
*   **Backend**: **Flask** (Python) service orchestrating chat loops, research phases, and file storage.
*   **Database**: **SQLite** for metadata; **ChromaDB** for vector-based semantic memory.
*   **Research Engine**: Custom asynchronous planner/reporter architecture utilizing Tavily's Search and Extract APIs.

## 📄 License & Versioning

This project follows [SemVer v2.0.0](https://semver.org/). Current version: `v1.7.1`.
See [CHANGELOG.md](./changelog.md) and [docs/versioning_directives.md](./docs/versioning_directives.md) for a detailed history of updates and versioning rules.
