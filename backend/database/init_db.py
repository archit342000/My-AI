import json
import sqlite3
import os
import logging
from backend.database.db_layer import make_connection, DB_PATH

logger = logging.getLogger(__name__)

def _create_indexes(c: sqlite3.Cursor) -> None:
    """
    Create every index of the schema. This is the only place indexes are defined.

    All statements are `IF NOT EXISTS`, so it is safe to call repeatedly. `init_db()` calls it once
    after the tables exist and again after the migrations that rebuild tables (steps 8 and 11):
    dropping a rebuilt table drops its indexes, which would otherwise be missing until the next start.
    A rebuild that fails after the rename leaves `<table>_old` holding the index names, so that table's
    indexes stay missing (not repaired here).

    Args:
        c: Cursor on the connection `init_db()` is migrating.
    """
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_file_systems_chat_id ON file_systems(chat_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_file_systems_title ON file_systems(title)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_file_system_versions_file_system_id ON file_system_versions(file_system_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_file_system_permissions_file_system_id ON file_system_permissions(file_system_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_memories_tag ON memories(tag)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_sub_agent_chat_parent ON sub_agent_messages(chat_id, parent_message_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_sub_agent_sequence ON sub_agent_messages(chat_id, parent_message_id, sequence_order)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_collections_chat_parent ON collections(chat_id, parent_message_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_collections_parent_type ON collections(chat_id, parent_message_id, parent_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pending_cb_chat ON pending_callbacks(chat_id, status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_exec_history_chat ON code_execution_history(chat_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_exec_history_created ON code_execution_history(created_at)')


def init_db():
    """
    Initialize the database schema and perform necessary migrations.
    This ensures all tables and columns exist as expected.
    """
    logger.info(f"Initializing database at {DB_PATH}")
    
    conn = make_connection()
    try:
        c = conn.cursor()
        
        # 0. Pre-Schema Data Migration for renaming canvases tables to file_systems
        try:
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='canvases'")
            if c.fetchone():
                c.execute("ALTER TABLE canvases RENAME TO file_systems")
                c.execute("ALTER TABLE canvas_versions RENAME TO file_system_versions")
                c.execute("ALTER TABLE canvas_permissions RENAME TO file_system_permissions")
                c.execute("ALTER TABLE canvas_counters RENAME TO file_system_counters")
                
                # Also rename the legacy columns inside these tables
                try:
                    c.execute("ALTER TABLE file_system_versions RENAME COLUMN canvas_id TO file_system_id")
                except sqlite3.OperationalError: pass
                try:
                    c.execute("ALTER TABLE file_system_permissions RENAME COLUMN canvas_id TO file_system_id")
                except sqlite3.OperationalError: pass
                try:
                    c.execute("ALTER TABLE file_system_counters RENAME COLUMN chat_id TO owner_id")
                except sqlite3.OperationalError: pass
                
                logger.info("MIGRATION: Renamed DB tables and columns from canvas to file_system.")
        except Exception as e:
            logger.error(f"Error renaming DB tables from canvas to file_system: {e}")
        
        # 1. Create Core Tables
        c.execute('''
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT,
                timestamp REAL,
                icon TEXT DEFAULT NULL
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS personas (
                id TEXT PRIMARY KEY,
                name TEXT,
                content TEXT,
                is_default INTEGER DEFAULT 0,
                timestamp REAL,
                research_mode INTEGER DEFAULT 0,
                file_system_mode INTEGER DEFAULT 0,
                browsing_mode INTEGER DEFAULT 0,
                git_mode INTEGER DEFAULT 0,
                code_execution_mode INTEGER DEFAULT 1
            )
        ''')

        c.execute("PRAGMA table_info(personas)")
        persona_cols = [col[1] for col in c.fetchall()]
        if 'research_mode' not in persona_cols:
            logger.info("MIGRATION: Adding 'research_mode' column to 'personas' table.")
            try:
                c.execute("ALTER TABLE personas ADD COLUMN research_mode INTEGER DEFAULT 0")
            except Exception as e:
                logger.error(f"Error adding research_mode column to personas: {e}")
        if 'file_system_mode' not in persona_cols:
            logger.info("MIGRATION: Adding 'file_system_mode' column to 'personas' table.")
            try:
                c.execute("ALTER TABLE personas ADD COLUMN file_system_mode INTEGER DEFAULT 0")
            except Exception as e:
                logger.error(f"Error adding file_system_mode column to personas: {e}")
        if 'browsing_mode' not in persona_cols:
            logger.info("MIGRATION: Adding 'browsing_mode' column to 'personas' table.")
            try:
                c.execute("ALTER TABLE personas ADD COLUMN browsing_mode INTEGER DEFAULT 0")
            except Exception as e:
                logger.error(f"Error adding browsing_mode column to personas: {e}")
        if 'git_mode' not in persona_cols:
            logger.info("MIGRATION: Adding 'git_mode' column to 'personas' table.")
            try:
                c.execute("ALTER TABLE personas ADD COLUMN git_mode INTEGER DEFAULT 0")
            except Exception as e:
                logger.error(f"Error adding git_mode column to personas: {e}")
        if 'code_execution_mode' not in persona_cols:
            logger.info("MIGRATION: Adding 'code_execution_mode' column to 'personas' table.")
            try:
                c.execute("ALTER TABLE personas ADD COLUMN code_execution_mode INTEGER DEFAULT 1")
            except Exception as e:
                logger.error(f"Error adding code_execution_mode column to personas: {e}")

        c.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT,
                timestamp REAL,
                user_preferences INTEGER DEFAULT 0,
                research_mode INTEGER DEFAULT 0,
                is_vision INTEGER DEFAULT 0,
                last_model TEXT,
                vision_model TEXT,
                max_tokens INTEGER DEFAULT 16384,
                thinking_budget_tokens INTEGER DEFAULT 2000,
                is_custom_title INTEGER DEFAULT 0,
                folder TEXT,
                workspace_id TEXT,
                persona_id TEXT,
                research_completed INTEGER DEFAULT 0,
                had_research INTEGER DEFAULT 0,
                file_system_mode INTEGER DEFAULT 0,
                enable_thinking INTEGER DEFAULT 1,
                temperature REAL DEFAULT 1.0,
                top_p REAL DEFAULT 1.0,
                top_k INTEGER DEFAULT 40,
                min_p REAL DEFAULT 0.05,
                presence_penalty REAL DEFAULT 0.0,
                frequency_penalty REAL DEFAULT 0.0,
                last_user_id INTEGER,
                last_assistant_id INTEGER,
                message_order_map TEXT,
                research_state TEXT DEFAULT 'none',
                resume_suppressed INTEGER DEFAULT 0,
                thinking_profile TEXT DEFAULT 'general',
                browsing_session_id TEXT,
                browsing_mode INTEGER DEFAULT 0,
                git_mode INTEGER DEFAULT 0,
                code_execution_mode INTEGER DEFAULT 1,
                persona_snapshot TEXT,
                history_compression TEXT,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL
            )
        ''')
        
        c.execute("PRAGMA table_info(chats)")
        columns = [column[1] for column in c.fetchall()]
        if 'persona_id' not in columns:
            logger.info("MIGRATION: Adding 'persona_id' column to 'chats' table.")
            try:
                c.execute("ALTER TABLE chats ADD COLUMN persona_id TEXT")
            except Exception as e:
                logger.error(f"Error adding persona_id column: {e}")
        if 'git_mode' not in columns:
            logger.info("MIGRATION: Adding 'git_mode' column to 'chats' table.")
            try:
                c.execute("ALTER TABLE chats ADD COLUMN git_mode INTEGER DEFAULT 0")
            except Exception as e:
                logger.error(f"Error adding git_mode column: {e}")

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
                parent_id INTEGER,
                parent_type TEXT DEFAULT 'main',
                reasoning_content TEXT,
                attachments TEXT,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS file_systems (
                id TEXT,
                chat_id TEXT,
                workspace_id TEXT,
                title TEXT,
                filename TEXT,
                timestamp REAL,
                folder TEXT,
                tags TEXT,
                file_system_type TEXT DEFAULT 'custom',
                current_version INTEGER,
                language TEXT DEFAULT 'markdown',
                navigation_history TEXT DEFAULT '[]',
                navigation_index INTEGER DEFAULT -1,
                CHECK ((chat_id IS NOT NULL AND workspace_id IS NULL) OR (chat_id IS NULL AND workspace_id IS NOT NULL)),
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                UNIQUE(id, chat_id, workspace_id)
            )
        ''')
        
        # Migration: Add language column for existing databases
        try:
            c.execute("ALTER TABLE file_systems ADD COLUMN language TEXT DEFAULT 'markdown'")
        except sqlite3.OperationalError:
            pass # Column already exists

        c.execute('''
            CREATE TABLE IF NOT EXISTS file_system_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_system_id TEXT,
                chat_id TEXT,
                workspace_id TEXT,
                version_number INTEGER,
                content TEXT,
                author TEXT,
                timestamp REAL,
                comment TEXT,
                FOREIGN KEY(file_system_id, chat_id, workspace_id) REFERENCES file_systems(id, chat_id, workspace_id) ON DELETE CASCADE
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS file_system_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_system_id TEXT,
                chat_id TEXT,
                workspace_id TEXT,
                user_id TEXT,
                permission TEXT DEFAULT 'write',
                timestamp REAL,
                FOREIGN KEY(file_system_id, chat_id, workspace_id) REFERENCES file_systems(id, chat_id, workspace_id) ON DELETE CASCADE
            )
        ''')

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
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tag TEXT NOT NULL,
                timestamp REAL DEFAULT (strftime('%s', 'now'))
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS sub_agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                parent_message_id TEXT NOT NULL,
                parent_type TEXT DEFAULT 'main',
                agent_name TEXT NOT NULL,
                sequence_order INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                tool_calls TEXT,
                tool_call_id TEXT,
                name TEXT,
                model TEXT,
                reasoning_content TEXT,
                timestamp REAL,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                parent_message_id TEXT NOT NULL,
                parent_type TEXT NOT NULL DEFAULT 'main',
                collection_type TEXT NOT NULL,
                items TEXT NOT NULL,
                timestamp REAL,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')
        # Pending Callbacks (crash-resilient clarification persistence)
        c.execute('''
            CREATE TABLE IF NOT EXISTS pending_callbacks (
                callback_id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                parent_message_id INTEGER,
                parent_type TEXT DEFAULT 'main',
                tool_name TEXT NOT NULL,
                question TEXT,
                options TEXT,
                status TEXT DEFAULT 'pending',
                response TEXT,
                created_at REAL,
                resolved_at REAL,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')

        # Skills table for the Skill Store
        c.execute('''
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                instructions TEXT,
                timestamp REAL
            )
        ''')

        # System Settings table for persistent global configuration
        c.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        ''')

        # Clipboard table for out-of-band text sharing between agents
        c.execute('''
            CREATE TABLE IF NOT EXISTS clipboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                UNIQUE(chat_id, key)
            )
        ''')

        # Code execution history table for sandboxed execution auditing
        c.execute('''
            CREATE TABLE IF NOT EXISTS code_execution_history (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                message_id TEXT,
                tool_call_id TEXT,
                language TEXT NOT NULL,
                code TEXT NOT NULL,
                stdin TEXT,
                files_json TEXT,
                stdout TEXT,
                stderr TEXT,
                exit_code INTEGER,
                execution_time_ms INTEGER,
                timed_out INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')

        # FTS5 search table
        try:
            c.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS file_systems_search USING fts5(
                    id,
                    title,
                    content
                )
            ''')
        except sqlite3.OperationalError:
            logger.warning("FTS5 not supported, file_systems search disabled.")

        # 2. Perform Migrations (Column Additions)
        # This is a condensed version of the migrations in legacy storage.py
        
        # Migration: Rename memory_mode to user_preferences if it exists
        try:
            c.execute("ALTER TABLE chats RENAME COLUMN memory_mode TO user_preferences")
        except sqlite3.OperationalError:
            pass # Column already renamed or doesn't exist

        # Migration: Migrate canvas_mode to file_system_mode safely
        try:
            c.execute("SELECT canvas_mode FROM chats LIMIT 1")
            # If we reach here, canvas_mode exists
            try:
                c.execute("SELECT file_system_mode FROM chats LIMIT 1")
                # Both exist: file_system_mode was already added. Copy data over.
                c.execute("UPDATE chats SET file_system_mode = canvas_mode")
                try:
                    c.execute("ALTER TABLE chats DROP COLUMN canvas_mode")
                except sqlite3.OperationalError:
                    pass
            except sqlite3.OperationalError:
                # file_system_mode doesn't exist yet, safe to rename
                c.execute("ALTER TABLE chats RENAME COLUMN canvas_mode TO file_system_mode")
        except sqlite3.OperationalError:
            pass # canvas_mode doesn't exist

        chat_columns = [
            ('is_custom_title', 'INTEGER DEFAULT 0'),
            ('user_preferences', 'INTEGER DEFAULT 0'),
            ('research_mode', 'INTEGER DEFAULT 0'),
            ('is_vision', 'INTEGER DEFAULT 0'),
            ('last_model', 'TEXT'),
            ('vision_model', 'TEXT'),
            ('max_tokens', 'INTEGER DEFAULT 16384'),
            ('thinking_budget_tokens', 'INTEGER DEFAULT 2000'),
            ('folder', 'TEXT'),
            ('research_completed', 'INTEGER DEFAULT 0'),
            ('had_research', 'INTEGER DEFAULT 0'),
            ('file_system_mode', 'INTEGER DEFAULT 0'),
            ('enable_thinking', 'INTEGER DEFAULT 1'),
            ('temperature', 'REAL DEFAULT 1.0'),
            ('top_p', 'REAL DEFAULT 1.0'),
            ('top_k', 'INTEGER DEFAULT 40'),
            ('min_p', 'REAL DEFAULT 0.05'),
            ('presence_penalty', 'REAL DEFAULT 0.0'),
            ('frequency_penalty', 'REAL DEFAULT 0.0'),
            ('last_user_id', 'INTEGER'),
            ('last_assistant_id', 'INTEGER'),
            ('message_order_map', 'TEXT'),
            ('research_state', "TEXT DEFAULT 'none'"),
            ('resume_suppressed', 'INTEGER DEFAULT 0'),
            ('thinking_profile', "TEXT DEFAULT 'general'"),
            ('browsing_session_id', 'TEXT'),
            ('browsing_mode', 'INTEGER DEFAULT 0'),
            ('git_mode', 'INTEGER DEFAULT 0'),
            ('code_execution_mode', 'INTEGER DEFAULT 1'),
            ('persona_snapshot', 'TEXT'),
            ('history_compression', 'TEXT')
        ]
        for col_name, col_def in chat_columns:
            try:
                c.execute(f"ALTER TABLE chats ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass

        # FileSystem Migrations
        try:
            c.execute("ALTER TABLE file_systems ADD COLUMN file_system_type TEXT DEFAULT 'custom'")
        except sqlite3.OperationalError: pass
        try:
            c.execute("ALTER TABLE file_systems ADD COLUMN tags TEXT")
        except sqlite3.OperationalError: pass
        try:
            c.execute("ALTER TABLE file_systems ADD COLUMN current_version INTEGER")
        except sqlite3.OperationalError: pass
        try:
            c.execute("ALTER TABLE file_systems ADD COLUMN navigation_history TEXT DEFAULT '[]'")
        except sqlite3.OperationalError: pass
        try:
            c.execute("ALTER TABLE file_systems ADD COLUMN navigation_index INTEGER DEFAULT -1")
        except sqlite3.OperationalError: pass

        # Files Migrations
        try:
            c.execute("ALTER TABLE files ADD COLUMN processing_status TEXT DEFAULT 'pending'")
        except sqlite3.OperationalError: pass

        # Message Migrations
        message_cols = [
            ('model', 'TEXT'),
            ('tool_calls', 'TEXT'),
            ('tool_call_id', 'TEXT'),
            ('name', 'TEXT'),
            ('parent_id', 'INTEGER'),
            ('parent_type', "TEXT DEFAULT 'main'"),
            ('reasoning_content', 'TEXT')
        ]
        for col_name, col_def in message_cols:
            try:
                c.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass

        # Sub-agent Message Migrations
        sub_agent_cols = [
            ('tool_calls', 'TEXT'),
            ('tool_call_id', 'TEXT'),
            ('name', 'TEXT'),
            ('parent_type', "TEXT DEFAULT 'main'"),
            ('reasoning_content', 'TEXT')
        ]
        for col_name, col_def in sub_agent_cols:
            try:
                c.execute(f"ALTER TABLE sub_agent_messages ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass

        # 3. Create Indexes
        _create_indexes(c)

        # 4. Data Modernization (Migrate legacy chats to turn-anchored structure)
        try:
            import json
            c.execute("SELECT id, message_order_map FROM chats")
            all_chats = c.fetchall()
            
            for chat_id, raw_map in all_chats:
                needs_repair = False
                modernized_map = []
                
                if not raw_map:
                    needs_repair = True
                else:
                    try:
                        entry_list = json.loads(raw_map)
                        if not isinstance(entry_list, list):
                            needs_repair = True
                        else:
                            for entry in entry_list:
                                if isinstance(entry, int):
                                    modernized_map.append({'type': 'message', 'id': entry})
                                    needs_repair = True
                                else:
                                    modernized_map.append(entry)
                    except:
                        needs_repair = True

                if needs_repair:
                    # Perform Full Turn-Anchored Repair (from _heal_legacy_chat)
                    c.execute("SELECT id, role FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
                    messages = c.fetchall()
                    
                    rebuilt_map = []
                    active_anchor = None
                    last_u, last_a = None, None
                    
                    for mid, role in messages:
                        rebuilt_map.append({'type': 'message', 'id': mid})
                        if role == 'user':
                            active_anchor = mid
                            last_u = mid
                        elif role in ('assistant', 'tool'):
                            if active_anchor:
                                c.execute("UPDATE messages SET parent_id = ? WHERE id = ?", (active_anchor, mid))
                            if role == 'assistant':
                                last_a = mid
                    
                    # Merge existing modern entries if map was only partially legacy
                    final_map = modernized_map if modernized_map else rebuilt_map
                    
                    c.execute('''
                        UPDATE chats SET 
                            message_order_map = ?, 
                            last_user_id = ?, 
                            last_assistant_id = ? 
                        WHERE id = ?
                    ''', (json.dumps(final_map), last_u, last_a, chat_id))
                    
            logger.info("Chat history modernization complete.")
        except Exception as mig_e:
            logger.error(f"Chat modernization failed: {mig_e}")

        # 5. Data Migration for Reasoning Content
        try:
            import re
            for table in ['messages', 'sub_agent_messages']:
                c.execute(f"SELECT id, content FROM {table} WHERE content LIKE '%<think>%' AND (reasoning_content IS NULL OR reasoning_content = '')")
                rows = c.fetchall()
                for row_id, content in rows:
                    if not content:
                        continue
                    
                    think_match = re.search(r'<think>(.*?)</think>', content, flags=re.DOTALL)
                    if think_match:
                        reasoning = think_match.group(1).strip()
                        new_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                        c.execute(f"UPDATE {table} SET content = ?, reasoning_content = ? WHERE id = ?", (new_content, reasoning, row_id))
            logger.info("Reasoning content migration complete.")
        except Exception as e:
            logger.error(f"Error migrating reasoning content: {e}")

        # 6. Data Migration for parent_type (Backfill)
        try:
            # For sub_agent_messages, backfill parent_type from agent_name
            c.execute("UPDATE sub_agent_messages SET parent_type = agent_name WHERE parent_type IS NULL OR parent_type = ''")
            # For messages, ensure parent_type is 'main' if null
            c.execute("UPDATE messages SET parent_type = 'main' WHERE parent_type IS NULL OR parent_type = ''")
            logger.info("parent_type backfill complete.")
        except Exception as e:
            logger.error(f"Error backfilling parent_type: {e}")

        # 7. Data Migration for True File System (Physical Path = Filename)
        try:
            from backend.file_system.utils import FILE_SYSTEMS_DIR, resolve_owner_and_physical_path, ensure_physical_dir_exists, sanitize_path
            c.execute("SELECT id, chat_id, title, filename, folder FROM file_systems")
            file_systems_rows = c.fetchall()
            for c_id, chat_id, title, old_filename, folder in file_systems_rows:
                if not old_filename: continue
                
                # Determine new standardized relative path (folder/title)
                # If folder is empty, just use title.
                path_parts = []
                if folder:
                    path_parts.append(folder)
                path_parts.append(title or f"file_system_{c_id}.md")
                
                new_relative_path = sanitize_path('/'.join(path_parts))
                
                # If already matches, skip
                if old_filename == new_relative_path:
                    continue

                # Potential source locations
                old_root_path = os.path.join(FILE_SYSTEMS_DIR, old_filename)
                
                _, _, old_nested_path = resolve_owner_and_physical_path(chat_id, old_filename)
                _, _, target_path = resolve_owner_and_physical_path(chat_id, new_relative_path)
                
                source_path = None
                if os.path.exists(old_root_path):
                    source_path = old_root_path
                elif os.path.exists(old_nested_path):
                    source_path = old_nested_path
                
                if source_path:
                    ensure_physical_dir_exists(target_path, is_file_path=True)
                    if source_path != target_path:
                        try:
                            # Handle collision at target
                            final_path = target_path
                            final_rel_path = new_relative_path
                            counter = 1
                            while os.path.exists(final_path) and final_path != source_path:
                                base, ext = os.path.splitext(new_relative_path)
                                final_rel_path = f"{base}_{counter}{ext}"
                                _, _, final_path = resolve_owner_and_physical_path(chat_id, final_rel_path)
                                counter += 1
                            
                            os.rename(source_path, final_path)
                            c.execute("UPDATE file_systems SET filename = ? WHERE id = ? AND chat_id = ?", (final_rel_path, c_id, chat_id))
                        except OSError as e:
                            logger.error(f"Failed to migrate file_system {c_id} to path {new_relative_path}: {e}")
                else:
                    # Update DB even if file is missing
                    c.execute("UPDATE file_systems SET filename = ? WHERE id = ? AND chat_id = ?", (new_relative_path, c_id, chat_id))

            logger.info("True File System migration complete.")
        except Exception as e:
            logger.error(f"Error migrating to True File System: {e}")

        # 8. Data Migration for Workspaces (Schema Evolution)
        try:
            import uuid
            # Ensure workspace_id column exists on chats
            try:
                c.execute("ALTER TABLE chats ADD COLUMN workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL")
            except sqlite3.OperationalError:
                pass # Already exists
            
            # Ensure workspace_id column exists on file_systems and dependent tables
            for tbl in ["file_systems", "file_system_versions", "file_system_permissions"]:
                try:
                    c.execute(f"ALTER TABLE {tbl} ADD COLUMN workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE")
                except sqlite3.OperationalError:
                    pass # Already exists
            
            # Ensure icon column exists on workspaces
            c.execute("PRAGMA table_info(workspaces)")
            workspace_cols = [col[1] for col in c.fetchall()]
            if 'icon' not in workspace_cols:
                logger.info("MIGRATION: Adding 'icon' column to 'workspaces' table.")
                try:
                    c.execute("ALTER TABLE workspaces ADD COLUMN icon TEXT DEFAULT NULL")
                except Exception as e:
                    logger.error(f"Error adding icon column to workspaces: {e}")
            
            # RECREATION MIGRATION: Ensure file_systems has the correct UNIQUE constraint
            # This is necessary because ALTER TABLE cannot modify constraints in SQLite
            c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='file_systems'")
            file_system_sql = c.fetchone()[0]
            if "UNIQUE(id, chat_id, workspace_id)" not in file_system_sql:
                logger.info("MIGRATION: Recreating 'file_systems' table to update UNIQUE constraint...")
                c.execute("ALTER TABLE file_systems RENAME TO file_systems_old")
                c.execute('''
                    CREATE TABLE file_systems (
                        id TEXT,
                        chat_id TEXT,
                        workspace_id TEXT,
                        title TEXT,
                        filename TEXT,
                        timestamp REAL,
                        folder TEXT,
                        tags TEXT,
                        file_system_type TEXT DEFAULT 'custom',
                        current_version INTEGER,
                        language TEXT DEFAULT 'markdown',
                        navigation_history TEXT DEFAULT '[]',
                        navigation_index INTEGER DEFAULT -1,
                        CHECK ((chat_id IS NOT NULL AND workspace_id IS NULL) OR (chat_id IS NULL AND workspace_id IS NOT NULL)),
                        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                        UNIQUE(id, chat_id, workspace_id)
                    )
                ''')
                # Copy data, mapping columns correctly. Use COALESCE for any missing data if needed.
                c.execute('''
                    INSERT INTO file_systems (
                        id, chat_id, workspace_id, title, filename, timestamp, folder, tags, 
                        file_system_type, current_version, language, navigation_history, navigation_index
                    )
                    SELECT 
                        id, chat_id, workspace_id, title, filename, timestamp, folder, tags,
                        COALESCE(file_system_type, 'custom'), current_version, COALESCE(language, 'markdown'),
                        COALESCE(navigation_history, '[]'), COALESCE(navigation_index, -1)
                    FROM file_systems_old
                ''')
                # NOTE: file_systems_old drop is deferred to AFTER dependent tables are rebuilt
                # (see below) to avoid leaving file_system_versions with a broken FK reference
                # during the migration window.
                
                # RECREATION MIGRATION: Also recreate dependent tables to update their foreign keys
                # This is necessary because renaming 'file_systems' to 'file_systems_old' broke these FKs
                for tbl in ["file_system_versions", "file_system_permissions"]:
                    logger.info(f"MIGRATION: Recreating '{tbl}' table to update foreign keys...")
                    c.execute(f"ALTER TABLE {tbl} RENAME TO {tbl}_old")
                    
                    if tbl == "file_system_versions":
                        c.execute('''
                            CREATE TABLE file_system_versions (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                file_system_id TEXT,
                                chat_id TEXT,
                                workspace_id TEXT,
                                version_number INTEGER,
                                content TEXT,
                                author TEXT,
                                timestamp REAL,
                                comment TEXT,
                                FOREIGN KEY(file_system_id, chat_id, workspace_id) REFERENCES file_systems(id, chat_id, workspace_id) ON DELETE CASCADE
                            )
                        ''')
                        c.execute('''
                            INSERT INTO file_system_versions (id, file_system_id, chat_id, workspace_id, version_number, content, author, timestamp, comment)
                            SELECT id, file_system_id, chat_id, workspace_id, version_number, content, author, timestamp, comment FROM file_system_versions_old
                        ''')
                    else: # file_system_permissions
                        c.execute('''
                            CREATE TABLE file_system_permissions (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                file_system_id TEXT,
                                chat_id TEXT,
                                workspace_id TEXT,
                                user_id TEXT,
                                permission TEXT DEFAULT 'write',
                                timestamp REAL,
                                FOREIGN KEY(file_system_id, chat_id, workspace_id) REFERENCES file_systems(id, chat_id, workspace_id) ON DELETE CASCADE
                            )
                        ''')
                        c.execute('''
                            INSERT INTO file_system_permissions (id, file_system_id, chat_id, workspace_id, user_id, permission, timestamp)
                            SELECT id, file_system_id, chat_id, workspace_id, user_id, permission, timestamp FROM file_system_permissions_old
                        ''')
                    
                    try:
                        c.execute(f"DROP TABLE {tbl}_old")
                    except Exception as drop_e:
                        logger.error(f"Failed to drop {tbl}_old: {drop_e}")
                        raise
                
                # Now safe to drop file_systems_old — all dependent tables have been rebuilt
                # and their FKs now point to the new `file_systems` table, not `file_systems_old`.
                try:
                    c.execute("DROP TABLE IF EXISTS file_systems_old")
                except Exception as drop_e:
                    logger.error(f"Failed to drop file_systems_old: {drop_e}")
                    raise
                
                logger.info("MIGRATION: 'file_systems' and dependent tables recreation successful.")
                    
            # Migrate old `chats.folder` values into actual workspaces
            c.execute("SELECT id, folder FROM chats WHERE folder IS NOT NULL AND folder != '' AND workspace_id IS NULL")
            chats_with_folders = c.fetchall()
            
            if chats_with_folders:
                # Group by folder name to ensure unique workspaces
                folder_map = {}
                for chat_id, folder_name in chats_with_folders:
                    if folder_name not in folder_map:
                        folder_map[folder_name] = []
                    folder_map[folder_name].append(chat_id)
                
                import time
                for folder_name, chat_ids in folder_map.items():
                    workspace_id = f"ws_{uuid.uuid4().hex}"
                    c.execute("INSERT INTO workspaces (id, name, timestamp) VALUES (?, ?, ?)", (workspace_id, folder_name, time.time()))
                    for cid in chat_ids:
                        c.execute("UPDATE chats SET workspace_id = ?, folder = NULL WHERE id = ?", (workspace_id, cid))
                
                logger.info(f"Migrated {len(folder_map)} legacy chat folders to native Workspaces.")
                
            # REPAIR MIGRATION: Fix file_system_versions with broken FK to dropped file_systems_old
            # This can happen if a previous migration run was interrupted after DROP file_systems_old
            # but before file_system_versions was recreated. Detected by checking the stored DDL.
            try:
                c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='file_system_versions'")
                cv_row = c.fetchone()
                if cv_row and 'file_systems_old' in cv_row[0]:
                    logger.info("REPAIR MIGRATION: file_system_versions references dropped file_systems_old — recreating...")
                    # Check if a stale file_system_versions_old backup exists from a crashed migration
                    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_system_versions_old'")
                    if c.fetchone():
                        c.execute("DROP TABLE file_system_versions_old")
                    c.execute("ALTER TABLE file_system_versions RENAME TO file_system_versions_old")
                    c.execute('''
                        CREATE TABLE file_system_versions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            file_system_id TEXT,
                            chat_id TEXT,
                            workspace_id TEXT,
                            version_number INTEGER,
                            content TEXT,
                            author TEXT,
                            timestamp REAL,
                            comment TEXT,
                            FOREIGN KEY(file_system_id, chat_id, workspace_id) REFERENCES file_systems(id, chat_id, workspace_id) ON DELETE CASCADE
                        )
                    ''')
                    c.execute('''
                        INSERT INTO file_system_versions (id, file_system_id, chat_id, workspace_id, version_number, content, author, timestamp, comment)
                        SELECT id, file_system_id, chat_id, workspace_id, version_number, content, author, timestamp, comment FROM file_system_versions_old
                    ''')
                    c.execute("DROP TABLE file_system_versions_old")
                    logger.info("REPAIR MIGRATION: file_system_versions successfully repaired.")
            except Exception as e:
                logger.error(f"REPAIR MIGRATION: file_system_versions repair failed: {e}")

            # REPAIR MIGRATION: Fix file_system_permissions with broken FK to dropped file_systems_old
            try:
                c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='file_system_permissions'")
                cp_row = c.fetchone()
                if cp_row and 'file_systems_old' in cp_row[0]:
                    logger.info("REPAIR MIGRATION: file_system_permissions references dropped file_systems_old — recreating...")
                    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_system_permissions_old'")
                    if c.fetchone():
                        c.execute("DROP TABLE file_system_permissions_old")
                    c.execute("ALTER TABLE file_system_permissions RENAME TO file_system_permissions_old")
                    c.execute('''
                        CREATE TABLE file_system_permissions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            file_system_id TEXT,
                            chat_id TEXT,
                            workspace_id TEXT,
                            user_id TEXT,
                            permission TEXT DEFAULT 'write',
                            timestamp REAL,
                            FOREIGN KEY(file_system_id, chat_id, workspace_id) REFERENCES file_systems(id, chat_id, workspace_id) ON DELETE CASCADE
                        )
                    ''')
                    c.execute('''
                        INSERT INTO file_system_permissions (id, file_system_id, chat_id, workspace_id, user_id, permission, timestamp)
                        SELECT id, file_system_id, chat_id, workspace_id, user_id, permission, timestamp FROM file_system_permissions_old
                    ''')
                    c.execute("DROP TABLE file_system_permissions_old")
                    logger.info("REPAIR MIGRATION: file_system_permissions successfully repaired.")
            except Exception as e:
                logger.error(f"REPAIR MIGRATION: file_system_permissions repair failed: {e}")

            # Rename file_system_counters `chat_id` column to `owner_id`
            try:
                c.execute("ALTER TABLE file_system_counters RENAME COLUMN chat_id TO owner_id")
            except sqlite3.OperationalError:
                pass # Already renamed
                
        except Exception as e:
            logger.error(f"Error migrating workspaces schema: {e}")

        # 9. Data Migration for Rebranding canvas_agent to file_system_agent
        try:
            c.execute("UPDATE messages SET parent_type = 'file_system_agent' WHERE parent_type = 'canvas_agent'")
            c.execute("UPDATE sub_agent_messages SET agent_name = 'file_system_agent' WHERE agent_name = 'canvas_agent'")
            c.execute("UPDATE sub_agent_messages SET parent_type = 'file_system_agent' WHERE parent_type = 'canvas_agent'")
            c.execute("UPDATE collections SET parent_type = 'file_system_agent' WHERE parent_type = 'canvas_agent'")
            c.execute("UPDATE pending_callbacks SET parent_type = 'file_system_agent' WHERE parent_type = 'canvas_agent'")
            logger.info("MIGRATION: Rebranded canvas_agent to file_system_agent successfully.")
        except Exception as e:
            logger.error(f"Error migrating canvas_agent to file_system_agent: {e}")

        # 10. Data Migration for renaming canvases tables to file_systems
        try:
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='canvases'")
            if c.fetchone():
                c.execute("ALTER TABLE canvases RENAME TO file_systems")
                c.execute("ALTER TABLE canvas_versions RENAME TO file_system_versions")
                c.execute("ALTER TABLE canvas_permissions RENAME TO file_system_permissions")
                c.execute("ALTER TABLE canvas_counters RENAME TO file_system_counters")
                
                # Also rename the legacy columns inside these tables
                try:
                    c.execute("ALTER TABLE file_system_versions RENAME COLUMN canvas_id TO file_system_id")
                    c.execute("ALTER TABLE file_system_permissions RENAME COLUMN canvas_id TO file_system_id")
                    c.execute("ALTER TABLE file_system_counters RENAME COLUMN chat_id TO owner_id")
                except sqlite3.OperationalError:
                    pass # Column might already be renamed
                
                logger.info("MIGRATION: Renamed DB tables and columns from canvas to file_system.")
        except Exception as e:
            logger.error(f"Error renaming DB tables from canvas to file_system: {e}")

        # Remember whether messages already had 'attachments' before migration 11 (which may recreate
        # the table), so the backfill in 11b runs once, when the column is first introduced.
        c.execute("PRAGMA table_info(messages)")
        messages_had_attachments = "attachments" in [r[1] for r in c.fetchall()]

        # 11. Data Migration for adding ON DELETE CASCADE to all dependent tables
        try:
            dependent_tables = {
                'messages': '''
                    CREATE TABLE messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        role TEXT,
                        content TEXT,
                        timestamp REAL,
                        model TEXT,
                        tool_calls TEXT,
                        tool_call_id TEXT,
                        name TEXT,
                        parent_id INTEGER,
                        parent_type TEXT DEFAULT 'main',
                        reasoning_content TEXT,
                        attachments TEXT,
                        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                    )
                ''',
                'files': '''
                    CREATE TABLE files (
                        id TEXT PRIMARY KEY,
                        chat_id TEXT NOT NULL,
                        original_filename TEXT NOT NULL,
                        stored_filename TEXT NOT NULL,
                        mime_type TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        content_text TEXT,
                        processing_status TEXT DEFAULT 'pending',
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                    )
                ''',
                'sub_agent_messages': '''
                    CREATE TABLE sub_agent_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        parent_message_id TEXT NOT NULL,
                        parent_type TEXT DEFAULT 'main',
                        agent_name TEXT NOT NULL,
                        sequence_order INTEGER NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT,
                        tool_calls TEXT,
                        tool_call_id TEXT,
                        name TEXT,
                        model TEXT,
                        reasoning_content TEXT,
                        timestamp REAL,
                        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                    )
                ''',
                'collections': '''
                    CREATE TABLE collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        parent_message_id TEXT NOT NULL,
                        parent_type TEXT NOT NULL DEFAULT 'main',
                        collection_type TEXT NOT NULL,
                        items TEXT NOT NULL,
                        timestamp REAL,
                        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                    )
                ''',
                'pending_callbacks': '''
                    CREATE TABLE pending_callbacks (
                        callback_id TEXT PRIMARY KEY,
                        chat_id TEXT NOT NULL,
                        parent_message_id INTEGER,
                        parent_type TEXT DEFAULT 'main',
                        tool_name TEXT NOT NULL,
                        question TEXT,
                        options TEXT,
                        status TEXT DEFAULT 'pending',
                        response TEXT,
                        created_at REAL,
                        resolved_at REAL,
                        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                    )
                '''
            }

            for table_name, create_sql in dependent_tables.items():
                c.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                row = c.fetchone()
                if row:
                    current_sql = row[0]
                    if "ON DELETE CASCADE" not in current_sql:
                        logger.info(f"MIGRATION: Recreating '{table_name}' table to add ON DELETE CASCADE...")
                        c.execute(f"ALTER TABLE {table_name} RENAME TO {table_name}_old")
                        c.execute(create_sql)
                        
                        # Get columns for INSERT (ensure matching order)
                        c.execute(f"PRAGMA table_info({table_name}_old)")
                        cols = [f'"{r[1]}"' for r in c.fetchall()]
                        cols_str = ", ".join(cols)
                        
                        c.execute(f"INSERT INTO {table_name} ({cols_str}) SELECT {cols_str} FROM {table_name}_old")
                        c.execute(f"DROP TABLE {table_name}_old")

            logger.info("MIGRATION: All dependent tables updated with ON DELETE CASCADE.")
        except Exception as e:
            logger.error(f"Error updating tables with ON DELETE CASCADE: {e}")

        # Rebuilt tables (steps 8 and 11) lost their indexes with the dropped copies: restore them now.
        # Runs even when a rebuild above failed, but a failed copy leaves `<table>_old` owning the index
        # names, so that one table stays without them (known gap, see `_create_indexes`).
        _create_indexes(c)

        # 11b. Store file references on the user message (messages.attachments) and backfill
        # them from the existing 'files' collections so old chats show their attachments too.
        c.execute("PRAGMA table_info(messages)")
        if "attachments" not in [r[1] for r in c.fetchall()]:
            c.execute("ALTER TABLE messages ADD COLUMN attachments TEXT DEFAULT NULL")
            logger.info("MIGRATION: Added 'attachments' column to messages.")

        if not messages_had_attachments:
            c.execute('''
                SELECT m.id, (
                    SELECT col.items FROM collections col
                    WHERE col.parent_message_id = CAST(m.id AS TEXT)
                      AND col.parent_type = 'main' AND col.collection_type = 'files'
                    ORDER BY col.id LIMIT 1
                )
                FROM messages m
                WHERE m.role = 'user' AND m.attachments IS NULL
            ''')
            backfilled = 0
            for msg_id, items_json in c.fetchall():
                if not items_json:
                    continue
                try:
                    items = json.loads(items_json)
                except ValueError:
                    logger.warning(f"MIGRATION: Skipped attachments backfill for message {msg_id}: files collection is not valid JSON.")
                    continue
                if not isinstance(items, list):
                    logger.warning(f"MIGRATION: Skipped attachments backfill for message {msg_id}: files collection is not a list.")
                    continue
                attachments = [
                    {k: item[k] for k in ("file_id", "name", "size", "mime_type") if k in item}
                    for item in items if isinstance(item, dict)
                ]
                if attachments:
                    c.execute("UPDATE messages SET attachments = ? WHERE id = ?", (json.dumps(attachments), msg_id))
                    backfilled += 1
            if backfilled:
                logger.info(f"MIGRATION: Backfilled attachments for {backfilled} user messages from file collections.")

        # 12. Data Migration for Rebranding file_agent to document_agent
        try:
            c.execute("UPDATE messages SET parent_type = 'document_agent' WHERE parent_type = 'file_agent'")
            c.execute("UPDATE sub_agent_messages SET agent_name = 'document_agent' WHERE agent_name = 'file_agent'")
            c.execute("UPDATE sub_agent_messages SET parent_type = 'document_agent' WHERE parent_type = 'file_agent'")
            c.execute("UPDATE collections SET parent_type = 'document_agent' WHERE parent_type = 'file_agent'")
            c.execute("UPDATE pending_callbacks SET parent_type = 'document_agent' WHERE parent_type = 'file_agent'")
            logger.info("MIGRATION: Rebranded file_agent to document_agent successfully.")
        except Exception as e:
            logger.error(f"Error migrating file_agent to document_agent: {e}")

        # 13. Data Migration for Flattening manage_user_preferences tool calls
        try:
            import json
            # Migrate 'messages' table
            c.execute("SELECT id, chat_id, tool_calls, timestamp, model, parent_id, parent_type FROM messages WHERE tool_calls LIKE '%\"manage_user_preferences\"%'")
            rows = c.fetchall()
            for row in rows:
                msg_id, chat_id, tool_calls_str, timestamp, model, parent_id, parent_type = row
                try:
                    tool_calls = json.loads(tool_calls_str)
                    new_tool_calls = []
                    split_mappings = []  # List of tuples: (original_tc_id, new_tc_id, new_tool_name, description)
                    
                    for tc in tool_calls:
                        if tc.get("function", {}).get("name") == "manage_user_preferences":
                            orig_id = tc.get("id", "call_pref")
                            try:
                                args = json.loads(tc["function"]["arguments"])
                            except Exception:
                                args = {}
                                
                            additions = args.get("additions") or []
                            edits = args.get("edits") or []
                            deletions = args.get("deletions") or []
                            
                            sub_calls_count = 0
                            for idx, add in enumerate(additions):
                                new_id = f"{orig_id}_add_{idx}"
                                new_tool_calls.append({
                                    "id": new_id,
                                    "type": "function",
                                    "function": {
                                        "name": "add_user_preference",
                                        "arguments": json.dumps({"content": add.get("content", ""), "tag": add.get("tag", "preference")})
                                    }
                                })
                                split_mappings.append((orig_id, new_id, "add_user_preference", f"Added preference: {add.get('content', '')}"))
                                sub_calls_count += 1
                                
                            for idx, edit in enumerate(edits):
                                new_id = f"{orig_id}_edit_{idx}"
                                new_tool_calls.append({
                                    "id": new_id,
                                    "type": "function",
                                    "function": {
                                        "name": "edit_user_preference",
                                        "arguments": json.dumps({"id": edit.get("id", ""), "content": edit.get("content", ""), "tag": edit.get("tag", "preference")})
                                    }
                                })
                                split_mappings.append((orig_id, new_id, "edit_user_preference", f"Updated preference [{edit.get('id', '')[:8]}]: OK"))
                                sub_calls_count += 1
                                
                            for idx, delete_id in enumerate(deletions):
                                new_id = f"{orig_id}_del_{idx}"
                                new_tool_calls.append({
                                    "id": new_id,
                                    "type": "function",
                                    "function": {
                                        "name": "delete_user_preference",
                                        "arguments": json.dumps({"id": delete_id})
                                    }
                                })
                                split_mappings.append((orig_id, new_id, "delete_user_preference", f"Deleted preference [{delete_id[:8]}]: OK"))
                                sub_calls_count += 1
                                
                            if sub_calls_count == 0:
                                new_id = f"{orig_id}_add_0"
                                new_tool_calls.append({
                                    "id": new_id,
                                    "type": "function",
                                    "function": {
                                        "name": "add_user_preference",
                                        "arguments": json.dumps({"content": "", "tag": "preference"})
                                    }
                                })
                                split_mappings.append((orig_id, new_id, "add_user_preference", "No changes made."))
                        else:
                            new_tool_calls.append(tc)
                            
                    # Update assistant message's tool_calls list
                    c.execute("UPDATE messages SET tool_calls = ? WHERE id = ?", (json.dumps(new_tool_calls), msg_id))
                    
                    # Split tool responses matching split_mappings
                    for orig_id, new_id, new_name, resp_text in split_mappings:
                        c.execute(
                            "SELECT content, model, parent_id, parent_type FROM messages WHERE role = 'tool' AND name = 'manage_user_preferences' AND tool_call_id = ?",
                            (orig_id,)
                        )
                        resp_row = c.fetchone()
                        if resp_row:
                            # Insert a split tool response
                            c.execute(
                                "INSERT INTO messages (chat_id, role, content, timestamp, model, tool_call_id, name, parent_id, parent_type) VALUES (?, 'tool', ?, ?, ?, ?, ?, ?, ?)",
                                (chat_id, resp_text, timestamp + 0.001, resp_row[1], new_id, new_name, parent_id, parent_type)
                            )
                            
                    # Delete the original tool response message
                    c.execute("DELETE FROM messages WHERE role = 'tool' AND name = 'manage_user_preferences' AND tool_call_id = ?", (orig_id,))
                except Exception as ex:
                    logger.error(f"Error migrating message ID {msg_id}: {ex}")
            
            # Migrate 'sub_agent_messages' table (in case sub-agents also called this tool, e.g. through skills or nesting)
            c.execute("SELECT id, chat_id, tool_calls, timestamp, model, parent_message_id, parent_type, agent_name, sequence_order FROM sub_agent_messages WHERE tool_calls LIKE '%\"manage_user_preferences\"%'")
            rows = c.fetchall()
            for row in rows:
                msg_id, chat_id, tool_calls_str, timestamp, model, parent_message_id, parent_type, agent_name, sequence_order = row
                try:
                    tool_calls = json.loads(tool_calls_str)
                    new_tool_calls = []
                    split_mappings = []
                    
                    for tc in tool_calls:
                        if tc.get("function", {}).get("name") == "manage_user_preferences":
                            orig_id = tc.get("id", "call_pref")
                            try:
                                args = json.loads(tc["function"]["arguments"])
                            except Exception:
                                args = {}
                                
                            additions = args.get("additions") or []
                            edits = args.get("edits") or []
                            deletions = args.get("deletions") or []
                            
                            sub_calls_count = 0
                            for idx, add in enumerate(additions):
                                new_id = f"{orig_id}_add_{idx}"
                                new_tool_calls.append({
                                    "id": new_id,
                                    "type": "function",
                                    "function": {
                                        "name": "add_user_preference",
                                        "arguments": json.dumps({"content": add.get("content", ""), "tag": add.get("tag", "preference")})
                                    }
                                })
                                split_mappings.append((orig_id, new_id, "add_user_preference", f"Added preference: {add.get('content', '')}"))
                                sub_calls_count += 1
                                
                            for idx, edit in enumerate(edits):
                                new_id = f"{orig_id}_edit_{idx}"
                                new_tool_calls.append({
                                    "id": new_id,
                                    "type": "function",
                                    "function": {
                                        "name": "edit_user_preference",
                                        "arguments": json.dumps({"id": edit.get("id", ""), "content": edit.get("content", ""), "tag": edit.get("tag", "preference")})
                                    }
                                })
                                split_mappings.append((orig_id, new_id, "edit_user_preference", f"Updated preference [{edit.get('id', '')[:8]}]: OK"))
                                sub_calls_count += 1
                                
                            for idx, delete_id in enumerate(deletions):
                                new_id = f"{orig_id}_del_{idx}"
                                new_tool_calls.append({
                                    "id": new_id,
                                    "type": "function",
                                    "function": {
                                        "name": "delete_user_preference",
                                        "arguments": json.dumps({"id": delete_id})
                                    }
                                })
                                split_mappings.append((orig_id, new_id, "delete_user_preference", f"Deleted preference [{delete_id[:8]}]: OK"))
                                sub_calls_count += 1
                                
                            if sub_calls_count == 0:
                                new_id = f"{orig_id}_add_0"
                                new_tool_calls.append({
                                    "id": new_id,
                                    "type": "function",
                                    "function": {
                                        "name": "add_user_preference",
                                        "arguments": json.dumps({"content": "", "tag": "preference"})
                                    }
                                })
                                split_mappings.append((orig_id, new_id, "add_user_preference", "No changes made."))
                        else:
                            new_tool_calls.append(tc)
                            
                    c.execute("UPDATE sub_agent_messages SET tool_calls = ? WHERE id = ?", (json.dumps(new_tool_calls), msg_id))
                    
                    for orig_id, new_id, new_name, resp_text in split_mappings:
                        c.execute(
                            "SELECT content, model FROM sub_agent_messages WHERE role = 'tool' AND name = 'manage_user_preferences' AND tool_call_id = ?",
                            (orig_id,)
                        )
                        resp_row = c.fetchone()
                        if resp_row:
                            c.execute(
                                "INSERT INTO sub_agent_messages (chat_id, parent_message_id, parent_type, agent_name, sequence_order, role, content, tool_call_id, name, model, timestamp) VALUES (?, ?, ?, ?, ?, 'tool', ?, ?, ?, ?, ?)",
                                (chat_id, parent_message_id, parent_type, agent_name, sequence_order, resp_text, new_id, new_name, resp_row[1], timestamp + 0.001)
                            )
                            
                    c.execute("DELETE FROM sub_agent_messages WHERE role = 'tool' AND name = 'manage_user_preferences' AND tool_call_id = ?", (orig_id,))
                except Exception as ex:
                    logger.error(f"Error migrating sub_agent_message ID {msg_id}: {ex}")
            logger.info("MIGRATION: Successfully migrated manage_user_preferences tool calls in database.")
        except Exception as e:
            logger.error(f"Error migrating manage_user_preferences tool calls: {e}")
        try:
            import json
            for tool_name in ("replace_fs_text", "replace_fs_lines"):
                # Migrate 'messages' table
                c.execute(f"SELECT id, chat_id, tool_calls, timestamp, model, parent_id, parent_type FROM messages WHERE tool_calls LIKE '%\"{tool_name}\"%'")
                rows = c.fetchall()
                for row in rows:
                    msg_id, chat_id, tool_calls_str, timestamp, model, parent_id, parent_type = row
                    try:
                        tool_calls = json.loads(tool_calls_str)
                        new_tool_calls = []
                        split_mappings = []  # (orig_id, new_id, tool_name, new_args)
                        
                        for tc in tool_calls:
                            if tc.get("function", {}).get("name") == tool_name:
                                orig_id = tc.get("id", f"call_{tool_name}")
                                try:
                                    args = json.loads(tc["function"]["arguments"])
                                except Exception:
                                    args = {}
                                
                                if "edits" not in args:
                                    new_tool_calls.append(tc)
                                    continue
                                    
                                path = args.get("path", "")
                                expected_version = args.get("expected_version")
                                try:
                                    expected_version = int(expected_version) if expected_version is not None else 1
                                except Exception:
                                    expected_version = 1
                                    
                                edits = args.get("edits") or []
                                if not isinstance(edits, list):
                                    edits = [edits]
                                
                                if len(edits) == 0:
                                    if tool_name == "replace_fs_text":
                                        edits = [{"target_text": "", "new_content": ""}]
                                    else:
                                        edits = [{"start_line": 1, "end_line": 1, "new_content": ""}]
                                
                                for idx, edit in enumerate(edits):
                                    new_id = orig_id if len(edits) == 1 else f"{orig_id}_edit_{idx}"
                                    if tool_name == "replace_fs_text":
                                        new_args = {
                                            "path": path,
                                            "expected_version": expected_version + idx,
                                            "target_text": edit.get("target_text", ""),
                                            "new_content": edit.get("new_content", ""),
                                        }
                                        if "start_line" in edit:
                                            new_args["start_line"] = edit["start_line"]
                                        if "end_line" in edit:
                                            new_args["end_line"] = edit["end_line"]
                                        if "allow_multiple" in edit:
                                            new_args["allow_multiple"] = edit["allow_multiple"]
                                    else:
                                        new_args = {
                                            "path": path,
                                            "expected_version": expected_version + idx,
                                            "start_line": edit.get("start_line", 1),
                                            "end_line": edit.get("end_line", 1),
                                            "new_content": edit.get("new_content", ""),
                                        }
                                    
                                    new_tool_calls.append({
                                        "id": new_id,
                                        "type": "function",
                                        "function": {
                                            "name": tool_name,
                                            "arguments": json.dumps(new_args)
                                        }
                                    })
                                    split_mappings.append((orig_id, new_id, tool_name, new_args))
                            else:
                                new_tool_calls.append(tc)
                        
                        # Update assistant message's tool_calls list
                        c.execute("UPDATE messages SET tool_calls = ? WHERE id = ?", (json.dumps(new_tool_calls), msg_id))
                        
                        # Migrate tool responses matching split_mappings
                        for idx, (orig_id, new_id, t_name, new_args) in enumerate(split_mappings):
                            c.execute(
                                f"SELECT content, model, parent_id, parent_type FROM messages WHERE role = 'tool' AND name = '{t_name}' AND tool_call_id = ?",
                                (orig_id,)
                            )
                            resp_row = c.fetchone()
                            if resp_row:
                                content_str = resp_row[0]
                                try:
                                    resp_data = json.loads(content_str)
                                except Exception:
                                    resp_data = {}
                                
                                if isinstance(resp_data, dict):
                                    success = resp_data.get("success", True)
                                    diff = resp_data.get("diff", "")
                                    file_system_id = resp_data.get("file_system_id", "")
                                    version_id = resp_data.get("version_id", new_args["expected_version"] + 1)
                                    
                                    new_resp_data = {
                                        "success": success,
                                        "file_system_id": file_system_id,
                                        "version_id": version_id,
                                        "message": "Applied edit." if success else "Failed to apply edit.",
                                        "diff": diff
                                    }
                                    orig_edit_results = resp_data.get("edit_results")
                                    if isinstance(orig_edit_results, list) and idx < len(orig_edit_results):
                                        new_resp_data["edit_results"] = [orig_edit_results[idx]]
                                    else:
                                        new_resp_data["edit_results"] = [{"edit_index": 0, "status": "applied" if success else "failed"}]
                                else:
                                    new_resp_data = {"success": True, "message": "Applied edit."}
                                
                                new_content_str = json.dumps(new_resp_data)
                                
                                if new_id == orig_id:
                                    c.execute(
                                        "UPDATE messages SET content = ? WHERE role = 'tool' AND name = ? AND tool_call_id = ?",
                                        (new_content_str, t_name, orig_id)
                                    )
                                else:
                                    c.execute(
                                        "INSERT INTO messages (chat_id, role, content, timestamp, model, tool_call_id, name, parent_id, parent_type) VALUES (?, 'tool', ?, ?, ?, ?, ?, ?, ?)",
                                        (chat_id, new_content_str, timestamp + 0.001 * (idx + 1), resp_row[1], new_id, t_name, parent_id, parent_type)
                                    )
                        
                        for orig_id, new_id, t_name, _ in split_mappings:
                            if new_id != orig_id:
                                c.execute(f"DELETE FROM messages WHERE role = 'tool' AND name = '{tool_name}' AND tool_call_id = ?", (orig_id,))
                            
                    except Exception as ex:
                        logger.error(f"Error migrating message ID {msg_id} for {tool_name}: {ex}")

                # Migrate 'sub_agent_messages' table
                c.execute(f"SELECT id, chat_id, parent_message_id, parent_type, agent_name, sequence_order, tool_calls, timestamp, model FROM sub_agent_messages WHERE tool_calls LIKE '%\"{tool_name}\"%'")
                rows = c.fetchall()
                for row in rows:
                    msg_id, chat_id, parent_message_id, parent_type, agent_name, sequence_order, tool_calls_str, timestamp, model = row
                    try:
                        tool_calls = json.loads(tool_calls_str)
                        new_tool_calls = []
                        split_mappings = []  # (orig_id, new_id, tool_name, new_args)
                        
                        for tc in tool_calls:
                            if tc.get("function", {}).get("name") == tool_name:
                                orig_id = tc.get("id", f"call_{tool_name}")
                                try:
                                    args = json.loads(tc["function"]["arguments"])
                                except Exception:
                                    args = {}
                                
                                if "edits" not in args:
                                    new_tool_calls.append(tc)
                                    continue
                                    
                                path = args.get("path", "")
                                expected_version = args.get("expected_version")
                                try:
                                    expected_version = int(expected_version) if expected_version is not None else 1
                                except Exception:
                                    expected_version = 1
                                    
                                edits = args.get("edits") or []
                                if not isinstance(edits, list):
                                    edits = [edits]
                                
                                if len(edits) == 0:
                                    if tool_name == "replace_fs_text":
                                        edits = [{"target_text": "", "new_content": ""}]
                                    else:
                                        edits = [{"start_line": 1, "end_line": 1, "new_content": ""}]
                                
                                for idx, edit in enumerate(edits):
                                    new_id = orig_id if len(edits) == 1 else f"{orig_id}_edit_{idx}"
                                    if tool_name == "replace_fs_text":
                                        new_args = {
                                            "path": path,
                                            "expected_version": expected_version + idx,
                                            "target_text": edit.get("target_text", ""),
                                            "new_content": edit.get("new_content", ""),
                                        }
                                        if "start_line" in edit:
                                            new_args["start_line"] = edit["start_line"]
                                        if "end_line" in edit:
                                            new_args["end_line"] = edit["end_line"]
                                        if "allow_multiple" in edit:
                                            new_args["allow_multiple"] = edit["allow_multiple"]
                                    else:
                                        new_args = {
                                            "path": path,
                                            "expected_version": expected_version + idx,
                                            "start_line": edit.get("start_line", 1),
                                            "end_line": edit.get("end_line", 1),
                                            "new_content": edit.get("new_content", ""),
                                        }
                                    
                                    new_tool_calls.append({
                                        "id": new_id,
                                        "type": "function",
                                        "function": {
                                            "name": tool_name,
                                            "arguments": json.dumps(new_args)
                                        }
                                    })
                                    split_mappings.append((orig_id, new_id, tool_name, new_args))
                            else:
                                new_tool_calls.append(tc)
                        
                        # Update sub-agent message's tool_calls list
                        c.execute("UPDATE sub_agent_messages SET tool_calls = ? WHERE id = ?", (json.dumps(new_tool_calls), msg_id))
                        
                        for idx, (orig_id, new_id, t_name, new_args) in enumerate(split_mappings):
                            c.execute(
                                f"SELECT content, model FROM sub_agent_messages WHERE role = 'tool' AND name = '{t_name}' AND tool_call_id = ?",
                                (orig_id,)
                            )
                            resp_row = c.fetchone()
                            if resp_row:
                                content_str = resp_row[0]
                                try:
                                    resp_data = json.loads(content_str)
                                except Exception:
                                    resp_data = {}
                                
                                if isinstance(resp_data, dict):
                                    success = resp_data.get("success", True)
                                    diff = resp_data.get("diff", "")
                                    file_system_id = resp_data.get("file_system_id", "")
                                    version_id = resp_data.get("version_id", new_args["expected_version"] + 1)
                                    
                                    new_resp_data = {
                                        "success": success,
                                        "file_system_id": file_system_id,
                                        "version_id": version_id,
                                        "message": "Applied edit." if success else "Failed to apply edit.",
                                        "diff": diff
                                    }
                                    orig_edit_results = resp_data.get("edit_results")
                                    if isinstance(orig_edit_results, list) and idx < len(orig_edit_results):
                                        new_resp_data["edit_results"] = [orig_edit_results[idx]]
                                    else:
                                        new_resp_data["edit_results"] = [{"edit_index": 0, "status": "applied" if success else "failed"}]
                                else:
                                    new_resp_data = {"success": True, "message": "Applied edit."}
                                
                                new_content_str = json.dumps(new_resp_data)
                                
                                if new_id == orig_id:
                                    c.execute(
                                        "UPDATE sub_agent_messages SET content = ? WHERE role = 'tool' AND name = ? AND tool_call_id = ?",
                                        (new_content_str, t_name, orig_id)
                                    )
                                else:
                                    c.execute(
                                        "INSERT INTO sub_agent_messages (chat_id, parent_message_id, parent_type, agent_name, sequence_order, role, content, tool_call_id, name, model, timestamp) VALUES (?, ?, ?, ?, ?, 'tool', ?, ?, ?, ?, ?)",
                                        (chat_id, parent_message_id, parent_type, agent_name, sequence_order, new_content_str, new_id, t_name, resp_row[1], timestamp + 0.001 * (idx + 1))
                                    )
                        
                        for orig_id, new_id, t_name, _ in split_mappings:
                            if new_id != orig_id:
                                c.execute(f"DELETE FROM sub_agent_messages WHERE role = 'tool' AND name = '{tool_name}' AND tool_call_id = ?", (orig_id,))
                            
                    except Exception as ex:
                        logger.error(f"Error migrating sub_agent_message ID {msg_id} for {tool_name}: {ex}")
            logger.info("MIGRATION: Successfully migrated replace_fs_text and replace_fs_lines tool calls in database.")
        except Exception as e:
            logger.error(f"Error migrating replace_fs_text and replace_fs_lines tool calls: {e}")

        # 14. Drop the unused file_system_counters table. Artifact ids are UUIDs, so nothing reads or writes
        # it any more. Explicit decision (docs/data.md, Migrations rule 4): it held only per-owner sequence
        # numbers, no user data, and artifacts with older numeric ids keep their ids in file_systems.
        c.execute("DROP TABLE IF EXISTS file_system_counters")

        conn.commit()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        logger.info("Database initialization complete.")
