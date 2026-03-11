import sqlite3
import json
import os
import time
from backend.config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "chats.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            title TEXT,
            timestamp REAL,
            memory_mode INTEGER DEFAULT 0,
            research_mode INTEGER DEFAULT 0,
            is_vision INTEGER DEFAULT 0,
            last_model TEXT,
            vision_model TEXT,
            max_tokens INTEGER DEFAULT 16384,
            is_custom_title INTEGER DEFAULT 0,
            folder TEXT,
            search_depth_mode TEXT DEFAULT 'regular'
        )
    ''')
    
    try:
        c.execute('ALTER TABLE chats ADD COLUMN is_custom_title INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute('ALTER TABLE chats ADD COLUMN timestamp REAL')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE chats ADD COLUMN memory_mode INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    # Try to add research_mode in case the table already exists
    try:
        c.execute('ALTER TABLE chats ADD COLUMN research_mode INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute('ALTER TABLE chats ADD COLUMN is_vision INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE chats ADD COLUMN last_model TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE chats ADD COLUMN vision_model TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE chats ADD COLUMN max_tokens INTEGER DEFAULT 16384')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE chats ADD COLUMN folder TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE chats ADD COLUMN search_depth_mode TEXT DEFAULT 'regular'")
    except sqlite3.OperationalError:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL,
            model TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            name TEXT,
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        )
    ''')
    try:
        c.execute('ALTER TABLE messages ADD COLUMN model TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE messages ADD COLUMN tool_calls TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE messages ADD COLUMN tool_call_id TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE messages ADD COLUMN name TEXT')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def get_all_chats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM chats ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_chat(chat_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
    chat = c.fetchone()

    if not chat:
        conn.close()
        return None

    c.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    messages = c.fetchall()
    conn.close()

    chat_dict = dict(chat)
    chat_dict['messages'] = []
    for msg in messages:
        m = dict(msg)
        # AGENTS.md compliance: ensure content is never None and parse JSON if structured
        raw_content = m.get('content')
        if raw_content is None:
            m['content'] = ""
        else:
            try:
                # Restore structured content (e.g., multimodal [text, image] lists)
                m['content'] = json.loads(raw_content)
            except (json.JSONDecodeError, TypeError):
                m['content'] = raw_content
            
        if m.get('tool_calls'):
            try:
                m['tool_calls'] = json.loads(m['tool_calls'])
            except:
                pass
            
        # Ensure tool metadata fields are strings, not None
        if m.get('tool_call_id') is None:
            m['tool_call_id'] = ""
        if m.get('name') is None:
            m['name'] = ""
            
        chat_dict['messages'].append(m)

    return chat_dict

def save_chat(chat_id, title, timestamp, memory_mode, research_mode=False, is_vision=False, last_model=None, vision_model=None, max_tokens=16384, folder=None, search_depth_mode='regular'):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chats (id, title, timestamp, memory_mode, research_mode, is_vision, last_model, vision_model, max_tokens, is_custom_title, folder, search_depth_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=CASE WHEN chats.is_custom_title = 1 THEN chats.title ELSE excluded.title END,
            timestamp=excluded.timestamp,
            memory_mode=excluded.memory_mode,
            research_mode=excluded.research_mode,
            is_vision=excluded.is_vision,
            last_model=excluded.last_model,
            vision_model=excluded.vision_model,
            max_tokens=excluded.max_tokens,
            folder=COALESCE(excluded.folder, chats.folder),
            search_depth_mode=excluded.search_depth_mode
    ''', (chat_id, title, timestamp, 1 if memory_mode else 0, 1 if research_mode else 0, 1 if is_vision else 0, last_model, vision_model, max_tokens, folder, search_depth_mode))
    conn.commit()
    conn.close()

def add_message(chat_id, role, content, model=None, tool_calls=None, tool_call_id=None, name=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure content is string for DB
    if content is not None and not isinstance(content, str):
        content = json.dumps(content)
        
    if tool_calls is not None and not isinstance(tool_calls, str):
        tool_calls = json.dumps(tool_calls)

    c.execute(
        "INSERT INTO messages (chat_id, role, content, timestamp, model, tool_calls, tool_call_id, name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
        (chat_id, role, content, time.time(), model, tool_calls, tool_call_id, name)
    )
    conn.commit()
    conn.close()

def clear_messages(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def delete_last_turn(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM messages WHERE chat_id = ? AND role = 'user' ORDER BY id DESC LIMIT 1", (chat_id,))
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM messages WHERE chat_id = ? AND id >= ?", (chat_id, row[0]))
        conn.commit()
    conn.close()

def rename_chat(chat_id, new_title):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE chats SET title = ?, is_custom_title = 1 WHERE id = ?", (new_title, chat_id))
    conn.commit()
    conn.close()

def update_chat_model(chat_id, last_model):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE chats SET last_model = ? WHERE id = ?", (last_model, chat_id))
    conn.commit()
    conn.close()

def update_chat_vision_model(chat_id, vision_model):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE chats SET vision_model = ? WHERE id = ?", (vision_model, chat_id))
    conn.commit()
    conn.close()

def update_chat_max_tokens(chat_id, max_tokens):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE chats SET max_tokens = ? WHERE id = ?", (max_tokens, chat_id))
    conn.commit()
    conn.close()

def update_chat_folder(chat_id, folder):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE chats SET folder = ? WHERE id = ?", (folder, chat_id))
    conn.commit()
    conn.close()

def delete_chat(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()

def delete_all_chats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages")
    c.execute("DELETE FROM chats")
    conn.commit()
    conn.close()
