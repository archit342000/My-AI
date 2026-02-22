# LMStudioChat

A modern, full-stack AI chat interface built for local inference with [LM Studio](https://lmstudio.ai/). This application provides a sleek web interface for interacting with local LLMs, featuring persistent chat history, long-term memory via RAG (Retrieval-Augmented Generation), and customizable personas.

## Features

*   **Local Inference**: Connects directly to your local LM Studio server.
*   **Persistent Chats**: Chat history is saved locally using a SQLite backend.
*   **Long-Term Memory (RAG)**: Automatically stores and retrieves relevant past conversation context to provide the AI with memory.
*   **Custom Personas**: Define system prompts to tailor the AI's behavior.
*   **Modern UI**: Glassmorphism design with dark mode, animations, and real-time parameter tuning.

## Prerequisites

*   **Python 3.10+** (Recommended)
*   **LM Studio**: Running locally with the server started.
*   **Chat Model**: Load any tool-calling capable model (e.g., Llama 3.1, Mistral, Qwen 2.5).
*   **Embedding Model**: Load an embedding model for RAG. Default: `text-embedding-embeddinggemma-300m`.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd LMStudioChat
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

## Usage

1.  **Start LM Studio Server**:
    *   Start the server (default port `1234`).
    *   Ensure your chat and embedding models are loaded.

2.  **Start the Application**:
    ```bash
    python3 app.py
    ```
    - The Flask web server starts at `http://localhost:5000`.

3.  **Access the Application**:
    *   Navigate to `http://localhost:5000` in your browser.

## Architecture

*   **Frontend**: Vanilla HTML/CSS/JS (located in `static/`).
*   **Backend**: Flask handles UI, session management, and chat orchestration.
*   **Memory Engine**: Direct RAG implementation (`backend/rag.py`) for semantic retrieval.
*   **Database**: SQLite (`backend/chats.db`) for chat metadata.
*   **Vector Store**: ChromaDB (`backend/chroma_db`) for semantic memory retrieval.

## Configuration

The app is configured via a `.env` file in the root directory. You can customize the following variables:

### LM Studio Configuration
- `LM_STUDIO_URL`: The URL where your LM Studio server is running (default: `http://localhost:1234`).
- `EMBEDDING_MODEL`: The key/name of the embedding model loaded in LM Studio (default: `text-embedding-embeddinggemma-300m`).

### Database and Storage
- `CHROMA_PATH`: The directory where ChromaDB stores its vector embeddings (default: `./backend/chroma_db`).
