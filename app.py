from flask import Flask, request, jsonify, Response, send_from_directory
import os
import time
import json
import requests
from backend.rag import MemoryRAG
from backend.storage import init_db, get_all_chats, get_chat, save_chat, add_message, delete_chat

app = Flask(__name__, static_folder='static')

LM_STUDIO_URL = "http://localhost:1234"
EMBEDDING_MODEL = "text-embedding-embeddinggemma-300m"

# Initialize components with config
# Note: We re-initialize rag if config changes, or we modify rag in place
init_db()
rag = MemoryRAG(api_url=LM_STUDIO_URL, embedding_model=EMBEDDING_MODEL)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/chats', methods=['GET'])
def list_chats():
    chats = get_all_chats()
    return jsonify(chats)

@app.route('/api/chats/<chat_id>', methods=['GET'])
def get_chat_details(chat_id):
    chat = get_chat(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    return jsonify(chat)

@app.route('/api/chats/<chat_id>', methods=['DELETE'])
def remove_chat(chat_id):
    delete_chat(chat_id)
    return jsonify({"success": True})

@app.route('/api/config', methods=['POST'])
def update_config():
    global LM_STUDIO_URL, rag
    data = request.json

    updated = False
    if 'url' in data:
        LM_STUDIO_URL = data['url']
        updated = True

    # Potential future update: Allow changing embedding model via config
    # if 'embedding_model' in data: ...

    if updated:
        # Re-initialize RAG with new URL
        rag = MemoryRAG(api_url=LM_STUDIO_URL, embedding_model=EMBEDDING_MODEL)

    return jsonify({"success": True, "url": LM_STUDIO_URL})

@app.route('/api/chat', methods=['POST'])
def chat_completions():
    data = request.json
    messages = data.get('messages', [])
    model = data.get('model', 'local-model')
    chat_id = data.get('chatId')
    memory_mode = data.get('memoryMode', False)
    # Filter out extra params not supported by LM Studio or used for logic
    extra_body = {k: v for k, v in data.items() if k not in ['messages', 'chatId', 'memoryMode', 'stream']}

    # 1. RAG Retrieval
    context = ""
    if memory_mode:
        # Extract the last user message for query
        last_user_msg = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), None)
        if isinstance(last_user_msg, list): # Handle multimodal
             last_user_msg = next((part['text'] for part in last_user_msg if part.get('type') == 'text'), "")

        if last_user_msg:
            context = rag.retrieve_context(last_user_msg)

    # 2. Inject Context
    if context:
        injection = f"\n<memory_context>\n{context}\n</memory_context>"

        # Find index of the last system message to insert after it
        # This ensures we don't overwrite the user's defined system prompt
        last_system_idx = -1
        for i, m in enumerate(messages):
            if m['role'] == 'system':
                last_system_idx = i

        # Insert as a separate system message
        messages.insert(last_system_idx + 1, {"role": "system", "content": injection})

    # 3. Stream Proxy to LM Studio
    def generate():
        try:
            # Prepare payload for LM Studio
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                **extra_body
            }

            resp = requests.post(
                f"{LM_STUDIO_URL}/v1/chat/completions",
                json=payload,
                stream=True
            )

            full_content = ""

            for line in resp.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        if decoded_line == 'data: [DONE]':
                            yield f"data: [DONE]\n\n"
                            break
                        try:
                            chunk = json.loads(decoded_line[6:])
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            full_content += content
                            yield f"data: {json.dumps(chunk)}\n\n"
                        except:
                            yield f"{decoded_line}\n\n"
                    else:
                         yield f"{decoded_line}\n\n"

            # 4. Post-Generation: Persistence
            if chat_id:
                # Save User Message (last one)
                # Note: Frontend might have already optimized this, but backend should be robust.
                # Assuming frontend sends full history, we only save the *new* turn if logic demands,
                # BUT typical pattern is frontend handles persistence or backend handles it.
                # Here, we save the interaction AFTER generation.

                # To avoid duplicating entire history, we assume 'messages' contains the full context.
                # We need to extract the LAST user message to save it.
                last_user_msg_obj = next((m for m in reversed(messages) if m['role'] == 'user'), None)

                if last_user_msg_obj:
                    # Check if chat exists, if not create
                    if not get_chat(chat_id):
                        title = "New Chat"
                        if isinstance(last_user_msg_obj['content'], str):
                             title = last_user_msg_obj['content'][:50]
                        elif isinstance(last_user_msg_obj['content'], list):
                             # Extract text
                             txt = next((x['text'] for x in last_user_msg_obj['content'] if x['type'] == 'text'), "Image Chat")
                             title = txt[:50]

                        save_chat(chat_id, title, time.time(), memory_mode)

                    # Add User Message to DB
                    # We might duplicate if frontend sends it repeatedly.
                    # Ideally, frontend calls /api/chat with *new* message, backend appends to history.
                    # Current prompt implies "Transition to python backend", so backend should manage state.
                    # However, to keep it simple with existing frontend logic (which sends array),
                    # we will persist the *generated* assistant response and the *triggering* user message.

                    # Simplification: Just save the turn.
                    add_message(chat_id, "user", last_user_msg_obj['content'])
                    add_message(chat_id, "assistant", full_content)

                    # Update chat timestamp
                    # We need to re-fetch title if needed or just update timestamp
                    save_chat(chat_id, get_chat(chat_id)['title'], time.time(), memory_mode)

            # 5. Post-Generation: RAG Memory Update
            if memory_mode and chat_id:
                 # Extract user text
                user_text = ""
                last_user_msg_obj = next((m for m in reversed(messages) if m['role'] == 'user'), None)
                if last_user_msg_obj:
                    if isinstance(last_user_msg_obj['content'], str):
                        user_text = last_user_msg_obj['content']
                    elif isinstance(last_user_msg_obj['content'], list):
                        user_text = next((x['text'] for x in last_user_msg_obj['content'] if x['type'] == 'text'), "")

                memory_text = f"User: {user_text}\nAssistant: {full_content}"
                rag.add_memory(memory_text, {"chat_id": chat_id, "timestamp": time.time()})

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
