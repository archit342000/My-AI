# LMStudioChat

A modern, full-stack AI chat interface built for local inference with [LM Studio](https://lmstudio.ai/). This application provides a sleek web interface for interacting with local LLMs, featuring persistent chat history, RAG-based memory, and customizable personas.

## Features

*   **Local Inference**: Connects directly to your local LM Studio server.
*   **Persistent Chats**: Chat history is saved locally using a SQLite backend.
*   **Memory Mode (RAG)**: Enables long-term context retention using ChromaDB and embedding models (e.g., Gemma).
*   **Temporary Chats**: Option for ephemeral conversations that aren't saved.
*   **Custom Personas**: Define system prompts to tailor the AI's behavior.
*   **Parameter Tuning**: Adjust temperature, top_p, and other sampling parameters in real-time.

## Prerequisites

*   **Python 3.8+**
*   **LM Studio**: Running locally with the server started.
    *   **Chat Model**: Load any chat model (e.g., Llama 3, Mistral).
    *   **Embedding Model**: Load an embedding model. By default, the app is configured for `text-embedding-embeddinggemma-300m`.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd LMStudioChat
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Start LM Studio Server**:
    *   Open LM Studio.
    *   Go to the "Local Server" tab.
    *   Start the server (default port `1234`).
    *   **Important**: Ensure both a chat model and the embedding model (`text-embedding-embeddinggemma-300m`) are loaded or available.

2.  **Start the Backend**:
    ```bash
    python3 app.py
    ```
    The server will start at `http://localhost:5000`.

3.  **Access the Application**:
    *   Open your browser and navigate to `http://localhost:5000`.

4.  **Configuration**:
    *   Click the "Backend Settings" (plug icon) in the sidebar to configure the LM Studio URL if it's not running on the default `http://localhost:1234`.

## Architecture

*   **Frontend**: Vanilla HTML/CSS/JS (located in `static/`).
*   **Backend**: Flask (Python).
*   **Database**: SQLite (`backend/chats.db`) for chat history.
*   **Vector Store**: ChromaDB (`backend/chroma_db`) for RAG memory.
