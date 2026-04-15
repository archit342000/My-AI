import sqlite3
import json
import os
import time
import random
import warnings
from backend.config import DATA_DIR

import threading
from contextlib import contextmanager

# Import new unified DB layer
from backend.db_wrapper import db

DB_PATH = os.path.join(DATA_DIR, "chats.db")

def make_connection() -> sqlite3.Connection:
    """
    Open a SQLite connection with all WAL-mode PRAGMAs applied.
    This MUST be the only way to open DB connections in this module.

    Why these PRAGMAs:
    - journal_mode=WAL : writers don't block readers; readers don't block writers.
    - synchronous=NORMAL : safe with WAL (no torn frames), much faster than FULL.
    - wal_autocheckpoint=1000 : checkpoint WAL back to main DB every 1000 pages.
    - busy_timeout=5000 : wait up to 5 s for a lock instead of immediately
                          raising OperationalError: database is locked.
    - foreign_keys=ON : enforce FK constraints (connection-level, not persistent).
    """
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA wal_autocheckpoint=1000")
    c.execute("PRAGMA busy_timeout=5000")
    c.execute("PRAGMA foreign_keys=ON")
    return conn

class TableLockManager:
    """
    Manages per-table locking with write-priority and re-entrancy.
    Reads wait if a write is ongoing OR if a write is queued.
    """
    def __init__(self):
        self.condition = threading.Condition()
        # table_name -> {
        #   'active_readers': int, 
        #   'active_writer': threading.Thread or None, 
        #   'queued_writers': int,
        #   'reader_threads': {thread_id: count},
        #   'write_recursion': int
        # }
        self.states = {}

    def _get_state(self, table_name):
        if table_name not in self.states:
            self.states[table_name] = {
                'active_readers': 0, 
                'active_writer': None, 
                'queued_writers': 0,
                'reader_threads': {},
                'write_recursion': 0
            }
        return self.states[table_name]

    @contextmanager
    def read_lock(self, table_name):
        current_thread = threading.get_ident()
        with self.condition:
            state = self._get_state(table_name)
            
            # Re-entrant read: if we already have a read lock or a write lock
            if state['reader_threads'].get(current_thread, 0) > 0 or state['active_writer'] == current_thread:
                state['active_readers'] += 1
                state['reader_threads'][current_thread] = state['reader_threads'].get(current_thread, 0) + 1
                try:
                    yield
                finally:
                    with self.condition:
                        state['active_readers'] -= 1
                        state['reader_threads'][current_thread] -= 1
                        if state['active_readers'] == 0:
                            self.condition.notify_all()
                return

            # Normal read: Wait if there is an active writer or any writers waiting
            while state['active_writer'] is not None or state['queued_writers'] > 0:
                self.condition.wait()
            
            state['active_readers'] += 1
            state['reader_threads'][current_thread] = state['reader_threads'].get(current_thread, 0) + 1
        
        try:
            yield
        finally:
            with self.condition:
                state['active_readers'] -= 1
                state['reader_threads'][current_thread] -= 1
                if state['active_readers'] == 0:
                    self.condition.notify_all()

    @contextmanager
    def write_lock(self, table_name):
        current_thread = threading.get_ident()
        with self.condition:
            state = self._get_state(table_name)
            
            # Re-entrant write
            if state['active_writer'] == current_thread:
                state['write_recursion'] += 1
                try:
                    yield
                finally:
                    with self.condition:
                        state['write_recursion'] -= 1
                return

            state['queued_writers'] += 1
            # Wait if there is any active writer OR any active readers
            while state['active_writer'] is not None or state['active_readers'] > 0:
                self.condition.wait()
            
            state['queued_writers'] -= 1
            state['active_writer'] = current_thread
            state['write_recursion'] = 1
        
        try:
            yield
        finally:
            with self.condition:
                state['active_writer'] = None
                state['write_recursion'] = 0
                self.condition.notify_all()

# Global lock manager instance
lock_manager = TableLockManager()

def execute_with_retry(func, max_retries: int = 5, backoff_base: float = 0.1, jitter: bool = True, *args, **kwargs):
    """
    Execute a database function with retry on 'database is locked' errors.

    Args:
        func: The function to execute
        max_retries: Maximum retry attempts
        backoff_base: Base backoff time in seconds
        jitter: Whether to add random jitter to prevent thundering herd
        *args, **kwargs: Arguments to pass to func

    Returns:
        Result from func if successful

    Raises:
        Exception: From func if all retries exhausted
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            last_error = e
            if "database is locked" in str(e) and attempt < max_retries - 1:
                # Calculate backoff with jitter
                delay = backoff_base * (2 ** attempt)
                if jitter:
                    delay += random.uniform(0.01, 0.2)
                time.sleep(delay)
                continue
            raise
        except Exception as e:
            raise e
    if last_error:
        raise last_error

def init_db():
    def _init():
        conn = make_connection()
        c = conn.cursor()
        # PRAGMAs (WAL, synchronous, busy_timeout, etc.) are applied inside make_connection().
        
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
                search_depth_mode TEXT DEFAULT 'regular',
                research_completed INTEGER DEFAULT 0,
                had_research INTEGER DEFAULT 0,
                canvas_mode INTEGER DEFAULT 0,
                enable_thinking INTEGER DEFAULT 1,
                temperature REAL DEFAULT 1.0,
                top_p REAL DEFAULT 1.0,
                top_k INTEGER DEFAULT 40,
                min_p REAL DEFAULT 0.05,
                presence_penalty REAL DEFAULT 0.0,
                frequency_penalty REAL DEFAULT 0.0
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
        try:
            c.execute("ALTER TABLE chats ADD COLUMN research_completed INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE chats ADD COLUMN had_research INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE chats ADD COLUMN canvas_mode INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE chats ADD COLUMN enable_thinking INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE chats ADD COLUMN temperature REAL DEFAULT 1.0")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE chats ADD COLUMN top_p REAL DEFAULT 1.0")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE chats ADD COLUMN top_k INTEGER DEFAULT 40")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE chats ADD COLUMN min_p REAL DEFAULT 0.05")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE chats ADD COLUMN presence_penalty REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE chats ADD COLUMN frequency_penalty REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass

        # Add canvas_type column if it doesn't exist
        try:
            c.execute("ALTER TABLE canvases ADD COLUMN canvas_type TEXT DEFAULT 'custom'")
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
        
        # Add tags column if it doesn't exist
        try:
            c.execute('ALTER TABLE canvases ADD COLUMN tags TEXT')
        except sqlite3.OperationalError:
            pass

        # Ensure canvases table exists with composite primary key and current_version
        c.execute('''
            CREATE TABLE IF NOT EXISTS canvases (
                id TEXT,
                chat_id TEXT,
                title TEXT,
                filename TEXT,
                timestamp REAL,
                folder TEXT,
                tags TEXT,
                canvas_type TEXT DEFAULT 'custom',
                current_version INTEGER,
                PRIMARY KEY (id, chat_id),
                FOREIGN KEY(chat_id) REFERENCES chats(id)
            )
        ''')

        # Add current_version column if it doesn't exist (for existing users)
        try:
            c.execute('ALTER TABLE canvases ADD COLUMN current_version INTEGER')
        except sqlite3.OperationalError:
            pass

        # Migration for composite primary key (id, chat_id)
        # Check if we need to migrate: if 'id' is still the ONLY primary key
        c.execute("PRAGMA table_info(canvases)")
        columns = c.fetchall()
        # PK is the 6th element (index 5) in PRAGMA table_info row
        pk_count = sum(1 for col in columns if col[5] > 0)
        
        # If pk_count is 1, it means 'id' is the only PK. We need to migrate to (id, chat_id).
        # If pk_count is 0 (unlikely for existing) or > 1, migration already happened or is in progress.
        if pk_count == 1:
            print("[MIGRATION] Migrating 'canvases' table to composite primary key (id, chat_id)...")
            # 1. Create temporary table
            c.execute('''
                CREATE TABLE canvases_new (
                    id TEXT,
                    chat_id TEXT,
                    title TEXT,
                    filename TEXT,
                    timestamp REAL,
                    folder TEXT,
                    tags TEXT,
                    canvas_type TEXT DEFAULT 'custom',
                    current_version INTEGER,
                    PRIMARY KEY (id, chat_id),
                    FOREIGN KEY(chat_id) REFERENCES chats(id)
                )
            ''')
            # 2. Copy data
            c.execute('''
                INSERT OR REPLACE INTO canvases_new (id, chat_id, title, filename, timestamp, folder, tags, canvas_type, current_version)
                SELECT id, chat_id, title, filename, timestamp, folder, tags, canvas_type, current_version FROM canvases
            ''')
            # 3. Drop old table and rename
            c.execute('DROP TABLE canvases')
            c.execute('ALTER TABLE canvases_new RENAME TO canvases')
            print("[MIGRATION] 'canvases' migration completed.")

        # Canvas versioning table with composite key (canvas_id, chat_id)
        # Foreign key references the canvases composite primary key (id, chat_id)
        c.execute('''
            CREATE TABLE IF NOT EXISTS canvas_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canvas_id TEXT,
                chat_id TEXT,
                version_number INTEGER,
                content TEXT,
                author TEXT,
                timestamp REAL,
                comment TEXT,
                FOREIGN KEY(canvas_id, chat_id) REFERENCES canvases(id, chat_id) ON DELETE CASCADE,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')

        # Canvas permissions table for shared canvases
        # Foreign key references the canvases composite primary key (id, chat_id)
        c.execute('''
            CREATE TABLE IF NOT EXISTS canvas_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canvas_id TEXT,
                chat_id TEXT,
                user_id TEXT,
                permission TEXT DEFAULT 'write',
                timestamp REAL,
                FOREIGN KEY(canvas_id, chat_id) REFERENCES canvases(id, chat_id) ON DELETE CASCADE,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')

        # Migration for canvas_versions: add chat_id if it doesn't exist (for existing DBs)
        c.execute("PRAGMA table_info(canvas_versions)")
        columns = c.fetchall()
        has_chat_id = any(col[1] == 'chat_id' for col in columns)

        if not has_chat_id:
            print("[MIGRATION] Adding 'chat_id' column to canvas_versions...")
            c.execute('ALTER TABLE canvas_versions ADD COLUMN chat_id TEXT')
            # Backfill chat_id from canvases table
            c.execute('''
                UPDATE canvas_versions SET chat_id = (
                    SELECT chat_id FROM canvases WHERE canvases.id = canvas_versions.canvas_id LIMIT 1
                )
            ''')
            print("[MIGRATION] 'canvas_versions' migration completed.")

        # Composite FK list for table 'canvases' on (id, chat_id) columns should have 2 rows for the same FK group.
        # Index 2 is table name, Index 1 is sequence, Index 3 is 'from' column.
        c.execute("PRAGMA foreign_key_list(canvas_versions)")
        fk_list = c.fetchall()
        canvases_fk_cols = [fk for fk in fk_list if fk[2] == 'canvases']
        has_composite_fk = any(fk[1] >= 1 for fk in canvases_fk_cols)

        # If we need to add the composite foreign key, recreate the table
        if not has_chat_id or not has_composite_fk:
            print("[MIGRATION] Recreating canvas_versions with composite foreign key...")
            # Disable foreign key checks during migration to handle orphaned records
            c.execute("PRAGMA foreign_keys = OFF")

            c.execute('''
                CREATE TABLE IF NOT EXISTS canvas_versions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canvas_id TEXT,
                    chat_id TEXT,
                    version_number INTEGER,
                    content TEXT,
                    author TEXT,
                    timestamp REAL,
                    comment TEXT,
                    FOREIGN KEY(canvas_id, chat_id) REFERENCES canvases(id, chat_id) ON DELETE CASCADE,
                    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                )
            ''')
            # Only copy records that have valid references
            c.execute('''
                INSERT OR REPLACE INTO canvas_versions_new
                    (id, canvas_id, chat_id, version_number, content, author, timestamp, comment)
                SELECT id, canvas_id, chat_id, version_number, content, author, timestamp, comment
                FROM canvas_versions
                WHERE EXISTS (SELECT 1 FROM canvases WHERE canvases.id = canvas_versions.canvas_id AND canvases.chat_id = canvas_versions.chat_id)
                  AND EXISTS (SELECT 1 FROM chats WHERE chats.id = canvas_versions.chat_id)
            ''')
            c.execute('DROP TABLE canvas_versions')
            c.execute('ALTER TABLE canvas_versions_new RENAME TO canvas_versions')

            # Re-enable foreign keys
            c.execute("PRAGMA foreign_keys = ON")
            print("[MIGRATION] 'canvas_versions' foreign key migration completed.")

        # Migration for canvas_permissions: add chat_id if it doesn't exist
        c.execute("PRAGMA table_info(canvas_permissions)")
        columns = c.fetchall()
        has_chat_id = any(col[1] == 'chat_id' for col in columns)

        if not has_chat_id:
            print("[MIGRATION] Adding 'chat_id' column to canvas_permissions...")
            c.execute('ALTER TABLE canvas_permissions ADD COLUMN chat_id TEXT')
            # Backfill chat_id
            c.execute('''
                UPDATE canvas_permissions SET chat_id = (
                    SELECT chat_id FROM canvases WHERE canvases.id = canvas_permissions.canvas_id LIMIT 1
                )
            ''')
            print("[MIGRATION] 'canvas_permissions' migration completed.")

        # Add composite foreign key (canvas_id, chat_id) -> canvases(id, chat_id)
        c.execute("PRAGMA foreign_key_list(canvas_permissions)")
        fk_list = c.fetchall()
        
        canvases_fk_cols = [fk for fk in fk_list if fk[2] == 'canvases']
        has_composite_fk = any(fk[1] >= 1 for fk in canvases_fk_cols)

        if not has_chat_id or not has_composite_fk:
            print("[MIGRATION] Recreating canvas_permissions with composite foreign key...")
            # Disable foreign key checks during migration to handle orphaned records
            c.execute("PRAGMA foreign_keys = OFF")

            c.execute('''
                CREATE TABLE IF NOT EXISTS canvas_permissions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canvas_id TEXT,
                    chat_id TEXT,
                    user_id TEXT,
                    permission TEXT DEFAULT 'write',
                    timestamp REAL,
                    FOREIGN KEY(canvas_id, chat_id) REFERENCES canvases(id, chat_id) ON DELETE CASCADE,
                    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                )
            ''')
            # Only copy records that have valid references
            c.execute('''
                INSERT OR REPLACE INTO canvas_permissions_new
                    (id, canvas_id, chat_id, user_id, permission, timestamp)
                SELECT id, canvas_id, chat_id, user_id, permission, timestamp
                FROM canvas_permissions
                WHERE EXISTS (SELECT 1 FROM canvases WHERE canvases.id = canvas_permissions.canvas_id AND canvases.chat_id = canvas_permissions.chat_id)
                  AND EXISTS (SELECT 1 FROM chats WHERE chats.id = canvas_permissions.chat_id)
            ''')
            c.execute('DROP TABLE canvas_permissions')
            c.execute('ALTER TABLE canvas_permissions_new RENAME TO canvas_permissions')

            # Re-enable foreign keys
            c.execute("PRAGMA foreign_keys = ON")
            print("[MIGRATION] 'canvas_permissions' foreign key migration completed.")

        try:
            c.execute('CREATE INDEX IF NOT EXISTS idx_canvases_chat_id ON canvases(chat_id)')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('CREATE INDEX IF NOT EXISTS idx_canvases_title ON canvases(title)')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('CREATE INDEX IF NOT EXISTS idx_canvas_versions_canvas_id ON canvas_versions(canvas_id)')
        except sqlite3.OperationalError:
            pass

        # Canvas Counters table for atomic ID generation
        c.execute('''
            CREATE TABLE IF NOT EXISTS canvas_counters (
                chat_id TEXT PRIMARY KEY,
                counter INTEGER DEFAULT 0
            )
        ''')
        try:
            c.execute('CREATE INDEX IF NOT EXISTS idx_canvas_permissions_canvas_id ON canvas_permissions(canvas_id)')
        except sqlite3.OperationalError:
            pass

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

        # FTS5 full-text search table for canvases (standalone mode - content stored separately)
        c.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS canvases_search USING fts5(
                id,
                title,
                content
            )
        ''')

        # Files table for file upload support
        c.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                content_text TEXT,
                processing_status TEXT DEFAULT 'pending',
                created_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY(chat_id) REFERENCES chats(id)
            )
        ''')

        # Migration: Add processing_status column if missing (for databases created before this change)
        try:
            c.execute('ALTER TABLE files ADD COLUMN processing_status TEXT DEFAULT \'pending\'')
            # Update existing rows to have 'pending' status (SQLite ALTER doesn't auto-fill existing rows)
            c.execute("UPDATE files SET processing_status = 'pending' WHERE processing_status IS NULL")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Memories table for global user memory (no RAG needed - direct DB access)
        c.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tag TEXT NOT NULL,
                timestamp REAL DEFAULT (strftime('%s', 'now'))
            )
        ''')
        # Index for quick filtering by tag
        c.execute('CREATE INDEX IF NOT EXISTS idx_memories_tag ON memories(tag)')

        conn.commit()
        conn.close()
    
    # We use a global write lock for schema init to be safe
    with lock_manager.write_lock("all"):
        execute_with_retry(_init)

def get_all_chats():
    """
    DEPRECATED: Use db.get_all_chats() instead.
    This function will be removed in a future version.
    """
    raise RuntimeError("storage.py is deprecated. Use db.get_all_chats() instead")


def get_all_chats_with_retry(max_retries: int = 3):
    """DEPRECATED: Use db.get_all_chats() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.get_all_chats() instead")

def get_chat(chat_id):
    """
    DEPRECATED: Use db.get_chat() or db.get_chat_full() instead.
    This function will be removed in a future version.
    """
    raise RuntimeError("storage.py is deprecated. Use db.get_chat() or db.get_chat_full() instead")

def save_chat(chat_id, title, timestamp, memory_mode, research_mode=False, is_vision=False, last_model=None, vision_model=None, max_tokens=16384, folder=None, search_depth_mode='regular', research_completed=0, canvas_mode=False):
    """
    DEPRECATED: Use db.save_chat() or db.update_chat() instead.
    This function will be removed in a future version.
    """
    raise RuntimeError("storage.py is deprecated. Use db.save_chat() or db.update_chat() instead")

def add_message(chat_id, role, content, model=None, tool_calls=None, tool_call_id=None, name=None):
    """DEPRECATED: Use db.add_message() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.add_message() instead")

def clear_messages(chat_id):
    """
    DEPRECATED: Use db.clear_messages() instead.
    This function will be removed in a future version.
    """
    raise RuntimeError("storage.py is deprecated. Use db.clear_messages() instead")

def delete_messages_from(chat_id, from_id):
    """
    DEPRECATED: Use db.delete_messages_from() instead.
    """
    raise RuntimeError("storage.py is deprecated. Use db.delete_messages_from() instead")

def update_message_content(message_id, content):
    """
    DEPRECATED: Use db.update_message_content() instead.
    """
    raise RuntimeError("storage.py is deprecated. Use db.update_message_content() instead")

def delete_last_turn(chat_id):
    """
    DEPRECATED: Use db.delete_last_turn() instead.
    """
    raise RuntimeError("storage.py is deprecated. Use db.delete_last_turn() instead")

def rename_chat(chat_id, new_title):
    """
    DEPRECATED: Use db.rename_chat() instead.
    """
    raise RuntimeError("storage.py is deprecated. Use db.rename_chat() instead")

def update_chat_model(chat_id, last_model):
    """DEPRECATED: Use db.update_chat_model() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.update_chat_model() instead")

def update_chat_vision_model(chat_id, vision_model):
    """DEPRECATED: Use db.update_chat_vision_model() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.update_chat_vision_model() instead")

def update_chat_max_tokens(chat_id, max_tokens):
    """DEPRECATED: Use db.update_chat_max_tokens() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.update_chat_max_tokens() instead")

def update_chat_folder(chat_id, folder):
    """DEPRECATED: Use db.update_chat_folder() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.update_chat_folder() instead")

def update_chat_canvas_mode(chat_id, canvas_mode):
    """DEPRECATED: Use db.update_chat_canvas_mode() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.update_chat_canvas_mode() instead")

def mark_research_completed(chat_id):
    """DEPRECATED: Use db.mark_research_completed() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.mark_research_completed() instead")

def delete_chat_canvas_files(chat_id, cursor):
    """DEPRECATED: Use db.delete_chat_canvas_files() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.delete_chat_canvas_files() instead")

def delete_chat(chat_id):
    """DEPRECATED: Use db.delete_chat() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.delete_chat() instead")

def delete_all_chats():
    """DEPRECATED: Use db.delete_all_chats() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.delete_all_chats() instead")
    
    with lock_manager.write_lock("chats"):
        with lock_manager.write_lock("messages"):
            with lock_manager.write_lock("canvases"):
                with lock_manager.write_lock("canvas_versions"):
                    with lock_manager.write_lock("canvas_counters"):
                        execute_with_retry(_delete_all, max_retries=3)

def save_canvas_meta(canvas_id, chat_id, title, filename, canvas_type="custom", folder=None, tags=None):
    """DEPRECATED: Use db.save_canvas() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.save_canvas() instead")

def get_chat_canvases(chat_id):
    """DEPRECATED: Use db.get_chat_canvases() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.get_chat_canvases() instead")

def delete_canvas_meta(canvas_id, chat_id):
    """DEPRECATED: Use db.delete_canvas_meta() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.delete_canvas_meta() instead")

def get_canvas_meta(canvas_id, chat_id):
    """DEPRECATED: Use db.get_canvas_meta() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.get_canvas_meta() instead")

def generate_canvas_filename(chat_id, canvas_id):
    """DEPRECATED: Use db.generate_canvas_filename() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.generate_canvas_filename() instead")

def get_canvas_content_by_id(canvas_id, chat_id):
    """DEPRECATED: Use db.get_canvas_content_by_id() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.get_canvas_content_by_id() instead")


def delete_canvas_versions_after(canvas_id: str, chat_id: str, up_to_version: int) -> int:
    """DEPRECATED: Use db.delete_canvas_versions_after() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.delete_canvas_versions_after() instead")


def sync_canvas_search_index(canvas_id: str, chat_id: str, max_retries: int = 3) -> bool:
    """DEPRECATED: Use db.sync_canvas_search_index() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.sync_canvas_search_index() instead")


def rebuild_canvas_search_index() -> int:
    """DEPRECATED: Use db.rebuild_canvas_search_index() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.rebuild_canvas_search_index() instead")


def fix_fts5_table() -> bool:
    """DEPRECATED: Use db.fix_fts5_table() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.fix_fts5_table() instead")


# =============================================================================
# ALIASES FOR DOCUMENTED FUNCTION NAMES
# =============================================================================
# These aliases provide the documented function names for backward compatibility
# and documentation alignment.
#
# Documented names: storage.write(), storage.read(), storage.invalidate()
# Actual names: save_chat(), get_chat(), cleanup_chat()
# =============================================================================

# Aliases for documented function names (pointing to actual implementations)
write = save_chat      # storage.write() -> save_chat()
read = get_chat        # storage.read() -> get_chat()

def invalidate(chat_id):
    """DEPRECATED: Use db.invalidate() or cache_system.cleanup_chat() instead."""
    raise RuntimeError("storage.py is deprecated. Use db.invalidate() or cache_system.cleanup_chat() instead")

# Note: The following functions have been migrated to db_wrapper.py
# and should no longer be imported from storage.py:
# - get_next_canvas_counter
# - reset_canvas_counter
# - get_canvas_versions
# - save_canvas_version
# - get_canvas_version_content
# - get_canvas_current_version
# - get_all_chats_retry

# Import these from backend.db_wrapper instead:
# from backend.db_wrapper import db
