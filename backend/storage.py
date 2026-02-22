import sqlite3
import json
import os
import time

DB_PATH = "./backend/chats.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            title TEXT,
            timestamp REAL,
            memory_mode INTEGER DEFAULT 0,
            deep_research_mode INTEGER DEFAULT 0,
            is_vision INTEGER DEFAULT 0,
            last_model TEXT
        )
    ''')
    
    # Try to add deep_research_mode in case the table already exists
    try:
        c.execute('ALTER TABLE chats ADD COLUMN deep_research_mode INTEGER DEFAULT 0')
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

    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL,
            model TEXT,
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        )
    ''')
    try:
        c.execute('ALTER TABLE messages ADD COLUMN model TEXT')
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
        try:
            # Try to parse content as JSON if it's structured (e.g. multimodal)
            m['content'] = json.loads(m['content'])
        except:
            pass
        chat_dict['messages'].append(m)

    return chat_dict

def save_chat(chat_id, title, timestamp, memory_mode, deep_research_mode=False, is_vision=False, last_model=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chats (id, title, timestamp, memory_mode, deep_research_mode, is_vision, last_model)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            timestamp=excluded.timestamp,
            memory_mode=excluded.memory_mode,
            deep_research_mode=excluded.deep_research_mode,
            is_vision=excluded.is_vision,
            last_model=excluded.last_model
    ''', (chat_id, title, timestamp, 1 if memory_mode else 0, 1 if deep_research_mode else 0, 1 if is_vision else 0, last_model))
    conn.commit()
    conn.close()

def add_message(chat_id, role, content, model=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure content is string for DB
    if isinstance(content, (list, dict)):
        content = json.dumps(content)

    c.execute("INSERT INTO messages (chat_id, role, content, timestamp, model) VALUES (?, ?, ?, ?, ?)", (chat_id, role, content, time.time(), model))
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
    c.execute("UPDATE chats SET title = ? WHERE id = ?", (new_title, chat_id))
    conn.commit()
    conn.close()

def update_chat_model(chat_id, last_model):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE chats SET last_model = ? WHERE id = ?", (last_model, chat_id))
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
