import sqlite3
import json
import os

DB_PATH = "./backend/chats.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            title TEXT,
            timestamp REAL,
            memory_mode INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL,
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        )
    ''')
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

def save_chat(chat_id, title, timestamp, memory_mode):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chats (id, title, timestamp, memory_mode)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            timestamp=excluded.timestamp,
            memory_mode=excluded.memory_mode
    ''', (chat_id, title, timestamp, 1 if memory_mode else 0))
    conn.commit()
    conn.close()

def add_message(chat_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure content is string for DB
    if isinstance(content, (list, dict)):
        content = json.dumps(content)

    c.execute("INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, 0)", (chat_id, role, content))
    conn.commit()
    conn.close()

def delete_chat(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
