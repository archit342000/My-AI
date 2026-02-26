# 🌌 My-AI v1.0.3

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
    *   An embedding model for RAG (e.g., `text-embedding-nomic-embed-text-v1.5`).
    *   (Optional) A vision model for image analysis.
*   **Search API**: A [Tavily API Key](https://tavily.com/) is required for Deep Research mode.

## 🚀 Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd My-AI
    ```

2.  **Set up Virtual Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment**:
    Create a `.env` file in the root directory:
    ```env
    TAVILY_API_KEY=your_tavily_api_key_here
    LM_STUDIO_URL=http://localhost:1234
    EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
    ```

## 🎮 Usage

1.  **Start LM Studio**: Ensure your models are loaded and the server is running.
2.  **Launch the App**:
    ```bash
    python3 app.py
    ```
3.  **Explore**: Access the dashboard at `http://localhost:5000`.

## 🏗️ Architecture

*   **Frontend**: Vanilla HTML5, CSS3 (Custom Properties), and Modern JS (ES6+). No heavy frameworks.
*   **Backend**: **Flask** (Python) service orchestrating chat loops, research phases, and file storage.
*   **Database**: **SQLite** for metadata; **ChromaDB** for vector-based semantic memory.
*   **Research Engine**: Custom asynchronous planner/reporter architecture utilizing Tavily's Search and Extract APIs.

## 📄 License & Versioning

This project follows [SemVer v2.0.0](https://semver.org/). Current version: `v1.0.3`.
See [CHANGELOG.md](./changelog.md) for a detailed history of updates.
