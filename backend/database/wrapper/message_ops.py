import sqlite3
import time
import json
import logging
from ..db_layer import make_connection
from ..cache_layer import cache_layer
from ..cache_system import cache_system
from .base import BaseMixin

logger = logging.getLogger(__name__)

class MessageOpsMixin(BaseMixin):
    """
    Mixin for message-level operations (CRUD, truncation, rollback).
    """

    def get_all_sub_agent_messages(self, chat_id: str) -> list:
        """
        Get all sub-agent messages for a chat, across all agents and parents.
        Used for full historical weaving.
        """
        self._log_db_wrapper_op("GET_ALL_SUB_AGENT_MESSAGES_START", chat_id)
        fetch_start = time.time()
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM sub_agent_messages WHERE chat_id = ? ORDER BY parent_message_id, sequence_order ASC", (chat_id,))
                
                def _parse_json_field(val):
                    if isinstance(val, str):
                        v = val.strip()
                        if (v.startswith('[') and v.endswith(']')) or (v.startswith('{') and v.endswith('}')):
                            try:
                                return json.loads(v)
                            except Exception:
                                pass
                    return val
                
                rows = []
                for row in c.fetchall():
                    d = dict(row)
                    d["content"] = _parse_json_field(d.get("content"))
                    if "tool_calls" in d and d.get("tool_calls"):
                        d["tool_calls"] = _parse_json_field(d.get("tool_calls"))
                    rows.append(d)
                return rows
            finally:
                conn.close()
        
        result = cache_layer.get("sub_agent_messages", f"chat:{chat_id}:all", _fetch, ttl=300)
        duration_ms = (time.time() - fetch_start) * 1000
        self._log_db_wrapper_op("GET_ALL_SUB_AGENT_MESSAGES_END", chat_id, f"count={len(result)} duration_ms={duration_ms:.2f}")
        return result

    def get_messages(self, chat_id: str, parent_message_id: int = None, parent_type: str = "main"):
        """
        Unified history retrieval for both main chat and sub-agents.
        If parent_type is 'main', fetches from the messages table.
        Otherwise, fetches from the sub_agent_messages table anchored to parent_message_id.
        """
        self._log_db_wrapper_op("GET_MESSAGES_START", chat_id, f"parent_type={parent_type} parent_id={parent_message_id}")
        fetch_start = time.time()
        
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                if parent_type == "main":
                    c.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
                else:
                    agent_name = parent_type
                    if not parent_message_id:
                        logger.error(f"parent_message_id required for agent history lookup ({agent_name})")
                        return []
                    c.execute('''
                        SELECT * FROM sub_agent_messages 
                        WHERE chat_id = ? AND parent_message_id = ? AND agent_name = ? 
                        ORDER BY sequence_order ASC
                    ''', (chat_id, parent_message_id, agent_name))
                
                def _parse_json_field(val):
                    if isinstance(val, str):
                        v = val.strip()
                        if (v.startswith('[') and v.endswith(']')) or (v.startswith('{') and v.endswith('}')):
                            try:
                                return json.loads(v)
                            except Exception:
                                pass
                    return val
                
                messages = c.fetchall()
                rows = []
                for row in messages:
                    d = dict(row)
                    d["content"] = _parse_json_field(d.get("content"))
                    if "tool_calls" in d and d.get("tool_calls"):
                        d["tool_calls"] = _parse_json_field(d.get("tool_calls"))
                    if d.get("attachments"):
                        d["attachments"] = _parse_json_field(d["attachments"])
                    rows.append(d)
                return rows
            finally:
                conn.close()

        # Cache separation by parent anchor
        cache_key = f"chat:{chat_id}"
        if parent_type != "main":
            cache_key += f":{parent_type}:{parent_message_id}"
            
        result = cache_layer.get("messages", cache_key, _fetch)
        duration_ms = (time.time() - fetch_start) * 1000
        result_count = len(result) if result else 0
        self._log_db_wrapper_op("GET_MESSAGES_END", chat_id, f"count={result_count} duration_ms={duration_ms:.2f}")
        return result

    def get_last_assistant_message(self, chat_id: str, parent_message_id: int = None, parent_type: str = "main"):
        """
        Get the most recent assistant message for a chat or sub-agent turn.
        Used for tool execution gates.
        """
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            if parent_type == "main":
                c.execute(
                    "SELECT * FROM messages WHERE chat_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
                    (chat_id,)
                )
            else:
                agent_name = parent_type
                if not parent_message_id:
                    logger.error(f"parent_message_id required for agent message lookup ({agent_name})")
                    return None
                c.execute('''
                    SELECT * FROM sub_agent_messages 
                    WHERE chat_id = ? AND parent_message_id = ? AND agent_name = ? AND role = 'assistant'
                    ORDER BY sequence_order DESC LIMIT 1
                ''', (chat_id, parent_message_id, agent_name))
            
            def _parse_json_field(val):
                if isinstance(val, str):
                    v = val.strip()
                    if (v.startswith('[') and v.endswith(']')) or (v.startswith('{') and v.endswith('}')):
                        try:
                            return json.loads(v)
                        except Exception:
                            pass
                return val

            row = c.fetchone()
            if row:
                d = dict(row)
                d["content"] = _parse_json_field(d.get("content"))
                if "tool_calls" in d and d.get("tool_calls"):
                    d["tool_calls"] = _parse_json_field(d.get("tool_calls"))
                return d
            return None
        finally:
            conn.close()

    def add_message(self, chat_id: str, role: str, content: str,
                    model: str = None, timestamp: float = None,
                    tool_calls: str = None, tool_call_id: str = None,
                    name: str = None, parent_id: int = None,
                    parent_type: str = "main", reasoning_content: str = None,
                    attachments: list = None):
        """
        Unified method to add messages to both main chat and sub-agents.
        If parent_type is 'main', adds to the 'messages' table.
        Otherwise, adds to 'sub_agent_messages' using parent_type as agent_name.
        `attachments` (a list of file references) is stored only on main messages.
        """
        self._log_db_wrapper_op("ADD_MESSAGE_START", chat_id, f"role={role} parent_type={parent_type}")
        write_start = time.time()

        if timestamp is None: timestamp = time.time()
        if isinstance(content, (list, dict)): content = json.dumps(content)
        if isinstance(tool_calls, (list, dict)): tool_calls = json.dumps(tool_calls)
        if name is None: name = ""
        attachments_json = json.dumps(attachments) if attachments else None

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                
                try:
                    if parent_type == "main":
                        # Standard main chat message
                        c.execute('''
                            INSERT INTO messages (chat_id, role, content, timestamp, model,
                                                tool_calls, tool_call_id, name, parent_id, parent_type, reasoning_content,
                                                attachments)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (chat_id, role, content, timestamp, model,
                            tool_calls, tool_call_id, name, parent_id, parent_type, reasoning_content,
                            attachments_json))
                        new_id = c.lastrowid
                        
                        # Fetch existing state for main chat pointers/order map
                        c.execute("SELECT last_user_id, last_assistant_id, message_order_map FROM chats WHERE id = ?", (chat_id,))
                        row = c.fetchone()
                        
                        if row:
                            last_u_id, last_a_id = row[0], row[1]
                            try: order_map = json.loads(row[2]) if row[2] else []
                            except: order_map = []

                            if role == 'user': last_u_id = new_id
                            elif role == 'assistant': last_a_id = new_id
                            
                            new_entry = {'type': 'message', 'id': new_id}
                            if not any(e.get('id') == new_id for e in order_map if isinstance(e, dict)):
                                order_map.append(new_entry)
                            
                            c.execute('''
                                UPDATE chats SET 
                                    last_user_id = ?, 
                                    last_assistant_id = ?, 
                                    message_order_map = ?,
                                    timestamp = ?
                                WHERE id = ?
                            ''', (last_u_id, last_a_id, json.dumps(order_map), timestamp, chat_id))
                    else:
                        # Sub-agent message
                        agent_name = parent_type
                        if not parent_id:
                            raise ValueError(f"parent_id (anchor) required for sub-agent message ({agent_name})")
                        
                        # Calculate sequence_order
                        c.execute('''
                            SELECT COALESCE(MAX(sequence_order), -1) + 1 
                            FROM sub_agent_messages 
                            WHERE chat_id = ? AND parent_message_id = ? AND agent_name = ?
                        ''', (chat_id, parent_id, agent_name))
                        seq = c.fetchone()[0]

                        c.execute('''
                            INSERT INTO sub_agent_messages (
                                chat_id, parent_message_id, parent_type, agent_name, sequence_order,
                                role, content, tool_calls, tool_call_id, name, model, timestamp, reasoning_content
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (chat_id, parent_id, parent_type, agent_name, seq, role, content, 
                              tool_calls, tool_call_id, name, model, timestamp, reasoning_content))
                        new_id = c.lastrowid
                    
                    c.execute("COMMIT")
                    return new_id
                except Exception as e:
                    c.execute("ROLLBACK")
                    raise e
            finally:
                conn.close()

        new_id = _write()
        
        # Comprehensive cache invalidation
        if parent_type == "main":
            cache_layer.invalidate("messages", f"chat:{chat_id}")
            cache_layer.invalidate("chats", chat_id)
            cache_layer.invalidate("chats_full", chat_id)
        else:
            # Anchor-specific invalidation for sub-agents
            cache_layer.invalidate("messages", f"chat:{chat_id}:{parent_type}:{parent_id}")
            # Also invalid our general sub-agent list cache
            cache_layer.invalidate("sub_agent_messages", f"chat:{chat_id}:all")
        
        duration_ms = (time.time() - write_start) * 1000
        self._log_db_wrapper_op("ADD_MESSAGE_END", chat_id, f"duration_ms={duration_ms:.2f} msg_id={new_id}")
        return new_id

    def add_tool_result(self, chat_id: str, tool_call_id: str, name: str, content: str, parent_id: int = None, parent_type: str = "main"):
        """
        Convenience wrapper to add a tool result message.
        """
        return self.add_message(
            chat_id=chat_id,
            role='tool',
            content=content,
            tool_call_id=tool_call_id,
            name=name,
            parent_id=parent_id,
            parent_type=parent_type
        )

    def delete_sub_agent_message(self, chat_id: str, message_id: int):
        """Delete a single sub-agent message by ID. Used for orphan cleanup during resume."""
        self._log_db_wrapper_op("DELETE_SUB_AGENT_MSG", chat_id, f"id={message_id}")
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM sub_agent_messages WHERE id = ? AND chat_id = ?",
                      (message_id, chat_id))
            conn.commit()
        finally:
            conn.close()
        cache_layer.invalidate("sub_agent_messages", f"chat:{chat_id}:all")

    def delete_message(self, chat_id: str, message_id: int, cutoff_idx: int = None):
        """
        Hierarchically deletes a message and every turn following it.
        Uses BEGIN IMMEDIATE and atomic state reconstruction.
        """
        self._log_db_wrapper_op("DELETE_MESSAGE_START", chat_id, f"target_id={message_id} cutoff={cutoff_idx}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                # 1. Lock DB for immediate write to prevent desync
                c.execute("BEGIN IMMEDIATE")
                
                try:
                    # Invalidate history_compression if deleting messages before/equal to boundary
                    c.execute("SELECT history_compression FROM chats WHERE id = ?", (chat_id,))
                    meta_row = c.fetchone()
                    if meta_row and meta_row[0]:
                        try:
                            comp_data = json.loads(meta_row[0])
                            boundary_id = comp_data.get("boundary_message_id")
                            if boundary_id is not None and message_id <= boundary_id:
                                c.execute("UPDATE chats SET history_compression = NULL WHERE id = ?", (chat_id,))
                        except Exception:
                            pass

                    # 2. Identify all messages to be deleted (target + all subsequent)
                    c.execute("SELECT id FROM messages WHERE chat_id = ? AND id >= ?", (chat_id, message_id))
                    ids_to_purge = [row[0] for row in c.fetchall()]

                    if ids_to_purge:
                        placeholders = ','.join(['?'] * len(ids_to_purge))
                        
                        # 3. Cleanup artifacts for all purged messages
                        c.execute(f"DELETE FROM sub_agent_messages WHERE parent_message_id IN ({placeholders})", ids_to_purge)
                        c.execute(f"DELETE FROM collections WHERE parent_message_id IN ({placeholders})", ids_to_purge)
                        for mid in ids_to_purge:
                            cache_system.delete_sse_chunks(chat_id, parent_message_id=mid)

                        # 4. Delete the messages themselves
                        c.execute(f"DELETE FROM messages WHERE chat_id = ? AND id >= ?", (chat_id, message_id))

                    # 5. Atomic Update of Order Map
                    c.execute("SELECT message_order_map FROM chats WHERE id = ?", (chat_id,))
                    row = c.fetchone()
                    try: order_map = json.loads(row[0]) if row and row[0] else []
                    except: order_map = []

                    if order_map:
                        if cutoff_idx is not None:
                            new_order_map = order_map[:cutoff_idx]
                        else:
                            purged_set = set(ids_to_purge)
                            found_idx = next((i for i, e in enumerate(order_map) if isinstance(e, dict) and 
                                            ((e.get('type') == 'message' and e.get('id') in purged_set) or 
                                                (e.get('type') in ('sse', 'sub_agent', 'collection') and e.get('parent_id') in purged_set))), None)
                            new_order_map = order_map[:found_idx] if found_idx is not None else order_map
                        
                        c.execute("UPDATE chats SET message_order_map = ? WHERE id = ?", (json.dumps(new_order_map), chat_id))

                    # 6. Restore Pointers and Timestamp
                    c.execute("SELECT id FROM messages WHERE chat_id = ? AND role = 'user' ORDER BY id DESC LIMIT 1", (chat_id,))
                    u_row = c.fetchone()
                    last_u_id = u_row[0] if u_row else None

                    c.execute("SELECT id FROM messages WHERE chat_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1", (chat_id,))
                    a_row = c.fetchone()
                    last_a_id = a_row[0] if a_row else None

                    c.execute('''
                        UPDATE chats SET 
                            last_user_id = ?, 
                            last_assistant_id = ?, 
                            timestamp = ? 
                        WHERE id = ?
                    ''', (last_u_id, last_a_id, time.time(), chat_id))

                    # Reset research_state if ongoing — the triggering message may have been deleted
                    c.execute(
                        "UPDATE chats SET research_state = 'none' WHERE id = ? AND research_state = 'ongoing'",
                        (chat_id,)
                    )

                    c.execute("COMMIT")
                    return True
                except Exception as e:
                    c.execute("ROLLBACK")
                    raise e
            finally:
                conn.close()

        _write()
        # Surgical cache invalidation
        cache_layer.invalidate("messages", f"chat:{chat_id}")
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("chats_full", chat_id)
        
        duration_ms = (time.time() - write_start) * 1000
        self._log_db_wrapper_op("DELETE_MESSAGE_END", chat_id, f"duration_ms={duration_ms:.2f}")

    def truncate_messages(self, chat_id: str, keep_up_to_index: int):
        """
        Delete chronological suffix based on 0-indexed count.
        Resolves the index via order_map (Source of Truth) and passes it to delete_message.
        """
        self._log_db_wrapper_op("TRUNCATE_MESSAGES_START", chat_id, f"keep={keep_up_to_index}")
        
        # 1. Resolve ID and verify index via order_map
        order_map = self.get_message_order_map(chat_id)
        if not order_map or keep_up_to_index >= len(order_map):
            return True # Nothing to truncate or out of bounds
        
        entry = order_map[keep_up_to_index]
        if not isinstance(entry, dict) or entry.get('type') != 'message':
            # If the entry at the index isn't a message (e.g. SSE placeholder), 
            # we need to find the nearest real message ID to anchor the deletion.
            target_id = None
            for e in order_map[keep_up_to_index:]:
                if isinstance(e, dict) and e.get('type') == 'message':
                    target_id = e.get('id')
                    break
            if not target_id: return True
        else:
            target_id = entry.get('id')

        # 2. Hand off to the safe cascading delete with the known index
        return self.delete_message(chat_id, target_id, cutoff_idx=keep_up_to_index)

    def edit_message(self, chat_id: str, message_id: int, new_content: str) -> bool:
        """
        Atomically updates a message's content and truncates all subsequent history.
        Ensures transactional integrity for message update AND cascading deletion.

        Returns:
            True if the edit was applied. False if no message with that id exists in this chat;
            nothing is written and no cache is invalidated.
        """
        self._log_db_wrapper_op("EDIT_MESSAGE_START", chat_id, f"target_id={message_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                
                try:
                    # 0. The message must belong to this chat; otherwise nothing is written
                    c.execute("SELECT 1 FROM messages WHERE id = ? AND chat_id = ?", (message_id, chat_id))
                    if c.fetchone() is None:
                        c.execute("ROLLBACK")
                        return False

                    # 1. Update the content of the target message (chat_id filter: defence in depth)
                    c.execute("UPDATE messages SET content = ? WHERE id = ? AND chat_id = ?", (new_content, message_id, chat_id))
                    
                    # 2. Reset immediate artifacts for the edited message (SSE/Sub-agents)
                    # We keep collections for the edited message for continuity.
                    c.execute("DELETE FROM sub_agent_messages WHERE parent_message_id = ?", (message_id,))
                    cache_system.delete_sse_chunks(chat_id, parent_message_id=message_id)

                    # 3. Identify and purge all subsequent messages and their artifacts
                    c.execute("SELECT id FROM messages WHERE chat_id = ? AND id > ?", (chat_id, message_id))
                    ids_to_purge = [row[0] for row in c.fetchall()]

                    if ids_to_purge:
                        placeholders = ','.join(['?'] * len(ids_to_purge))
                        # Cleanup sub-agents, collections and chunks for all following turns
                        c.execute(f"DELETE FROM sub_agent_messages WHERE parent_message_id IN ({placeholders})", ids_to_purge)
                        c.execute(f"DELETE FROM collections WHERE parent_message_id IN ({placeholders})", ids_to_purge)
                        for mid in ids_to_purge:
                            cache_system.delete_sse_chunks(chat_id, parent_message_id=mid)
                        
                        # Finally delete following messages
                        c.execute(f"DELETE FROM messages WHERE chat_id = ? AND id > ?", (chat_id, message_id))

                    # 4. Atomic reconstruction of Order Map
                    c.execute("SELECT message_order_map FROM chats WHERE id = ?", (chat_id,))
                    row = c.fetchone()
                    try: order_map = json.loads(row[0]) if row and row[0] else []
                    except: order_map = []
                    
                    if order_map:
                        # Find the index of the message we just edited
                        edit_idx = next((i for i, e in enumerate(order_map) 
                                       if isinstance(e, dict) and e.get('type') == 'message' and e.get('id') == message_id), None)
                        
                        if edit_idx is not None:
                            # Truncate map after the edited turn
                            new_order_map = order_map[:edit_idx + 1]
                            c.execute("UPDATE chats SET message_order_map = ? WHERE id = ?", (json.dumps(new_order_map), chat_id))

                    # 5. Restore Pointers and Timestamp
                    c.execute("SELECT id FROM messages WHERE chat_id = ? AND role = 'user' ORDER BY id DESC LIMIT 1", (chat_id,))
                    u_row = c.fetchone()
                    last_u_id = u_row[0] if u_row else None

                    c.execute("SELECT id FROM messages WHERE chat_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1", (chat_id,))
                    a_row = c.fetchone()
                    last_a_id = a_row[0] if a_row else None

                    c.execute('''
                        UPDATE chats SET 
                            last_user_id = ?, 
                            last_assistant_id = ?, 
                            timestamp = ? 
                        WHERE id = ?
                    ''', (last_u_id, last_a_id, time.time(), chat_id))

                    # Reset research_state — the edited message may have triggered research
                    c.execute(
                        "UPDATE chats SET research_state = 'none' WHERE id = ? AND research_state = 'ongoing'",
                        (chat_id,)
                    )

                    c.execute("COMMIT")
                    return True
                except Exception as e:
                    c.execute("ROLLBACK")
                    raise e
            finally:
                conn.close()

        success = _write()
        
        if success:
            # Cache Invalidation
            cache_layer.invalidate("messages", f"chat:{chat_id}")
            cache_layer.invalidate("chats", chat_id)
            cache_layer.invalidate("chats_full", chat_id)

        duration_ms = (time.time() - write_start) * 1000
        self._log_db_wrapper_op("EDIT_MESSAGE_END", chat_id, f"duration_ms={duration_ms:.2f} edited={success}")
        return success

    def clear_messages(self, chat_id: str):
        """
        Performs a deep reset of the chat history and all associated artifacts.
        Wipes messages, order map, pointers, and agent history.
        """
        self._log_db_wrapper_op("CLEAR_MESSAGES_START", chat_id)
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                
                try:
                    # 1. Delete all message-anchored records
                    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM sub_agent_messages WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM collections WHERE chat_id = ?", (chat_id,))
                    cache_system.delete_sse_chunks(chat_id)

                    # 2. Reset Chat Metadata (including research_state)
                    c.execute('''
                        UPDATE chats SET 
                            message_order_map = '[]', 
                            last_user_id = NULL, 
                            last_assistant_id = NULL,
                            research_state = 'none',
                            timestamp = ?
                        WHERE id = ?
                    ''', (time.time(), chat_id))

                    c.execute("COMMIT")
                    return True
                except Exception as e:
                    c.execute("ROLLBACK")
                    raise e
            finally:
                conn.close()

        _write()
        # Surgical cache invalidation
        cache_layer.invalidate("messages", f"chat:{chat_id}")
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("chats_full", chat_id)

        db_write_duration = (time.time() - write_start) * 1000
        self._log_db_wrapper_op("CLEAR_MESSAGES_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    def rollback_to_last_user_message(self, chat_id: str) -> bool:
        """
        Surgically removes all artifacts added after the most recent 'user' message.
        Optimized to use batch queries and the robust truncate_messages utility.
        """
        self._log_db_wrapper_op("ROLLBACK_START", chat_id)
        
        order_map = self.get_message_order_map(chat_id)
        if not order_map:
            return False
            
        # 1. Batch fetch roles for all messages in the map
        msg_ids = [e['id'] for e in order_map if isinstance(e, dict) and e.get('type') == 'message']
        if not msg_ids:
            return False
            
        conn = make_connection()
        try:
            c = conn.cursor()
            placeholders = ','.join(['?'] * len(msg_ids))
            c.execute(f"SELECT id, role FROM messages WHERE id IN ({placeholders})", msg_ids)
            role_map = {row[0]: row[1] for row in c.fetchall()}
        finally:
            conn.close()
        
        # 2. Find the index of the LAST user message
        last_user_idx = None
        for i, entry in enumerate(order_map):
            if isinstance(entry, dict) and entry.get('type') == 'message':
                if role_map.get(entry['id']) == 'user':
                    last_user_idx = i
        
        if last_user_idx is not None:
            # We keep up to and INCLUDING the last user message
            result = self.truncate_messages(chat_id, last_user_idx + 1)

            # Reset research_state since the research tool call is now gone
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute(
                    "UPDATE chats SET research_state = 'none' WHERE id = ? AND research_state = 'ongoing'",
                    (chat_id,)
                )
                conn.commit()
            finally:
                conn.close()
            cache_layer.invalidate("chats", chat_id)
            cache_layer.invalidate("chats_full", chat_id)
            return result
            
        return False
