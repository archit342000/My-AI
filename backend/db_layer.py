"""
Database layer with WAL mode and hybrid row-level read blocking.

This module provides the low-level database access layer that wraps SQLite
with Write-Ahead Logging (WAL) mode. It includes:

1. Connection Management:
   - WAL mode enabled for concurrent reads/writes
   - Foreign key support enabled
   - Timeout handling for busy connections

2. Locking Primitives:
   - row_read_lock: Row-level read lock with WAL checkpoint wait
   - table_read_lock: Table-level read lock with WAL checkpoint wait
   - row_write_lock: Row-level write lock (BEGIN IMMEDIATE)
   - table_write_lock: Table-level write lock

3. WAL Management:
   - flush_wal: Force WAL checkpoint for a table
   - Callback registration for cache invalidation coordination

Lock Hierarchy (to prevent deadlocks):
- Read locks wait for WAL checkpoint before acquiring
- Write locks acquire immediately (BEGIN IMMEDIATE)
- Read locks release with rollback, write locks with commit

Logging
-------
This module logs all database operations:
- Connection creation
- SQL queries executed
- Lock operations (acquire/release)
- WAL flush operations
- Transaction management
"""
import sqlite3
import os
import time
import logging
from contextlib import contextmanager
from backend.cache_layer import cache_layer
from backend.config import DATA_DIR

logger = logging.getLogger(__name__)

# Enable debug logging for DB operations
DB_DEBUG = True


def _log_db_op(op_type: str, table: str = None, row_id: str = None, sql: str = None):
    """
    Internal logging helper for DB operations.

    Args:
        op_type: Type of operation (e.g., "EXECUTE", "WAL_FLUSH")
        table: Optional table name
        row_id: Optional row identifier
        sql: Optional SQL statement (truncated to 100 chars for readability)
    """
    msg = f"[DB {op_type}]"
    if table:
        msg += f" table={table}"
    if row_id:
        msg += f" row_id={row_id}"
    if sql:
        # Truncate SQL for readability
        sql_preview = sql[:100] if len(sql) > 100 else sql
        msg += f" sql={sql_preview}"
    logger.debug(msg)


def _log_db_connection(action: str):
    """
    Log DB connection operation.

    Args:
        action: Connection action (e.g., "opening", "opened", "FAILED")
    """
    logger.debug(f"[DB CONNECTION] {action}")


def _log_db_lock(action: str, table: str, row_id: str = None, lock_type: str = None):
    """
    Log DB lock operation.

    Args:
        action: Lock action (e.g., "ACQUIRING", "ACQUIRED", "FAILED", "RELEASED")
        table: Table name
        row_id: Optional row identifier
        lock_type: Optional lock type (e.g., "row_read", "row_write", "table_read", "table_write")
    """
    msg = f"[DB LOCK] {action}"
    if lock_type:
        msg += f" type={lock_type}"
    msg += f" table={table}"
    if row_id:
        msg += f" row_id={row_id}"
    logger.debug(msg)

DB_PATH = os.path.join(DATA_DIR, "chats.db")

def make_connection() -> sqlite3.Connection:
    """
    Open SQLite connection with WAL mode enabled.

    This function creates a new database connection with the following settings:
    - WAL mode: Allows concurrent reads while writes are happening
    - NORMAL sync: Balanced durability and performance
    - 30 second busy timeout: Waits for locks to release
    - Foreign keys: Enabled for referential integrity

    Returns:
        sqlite3.Connection: Configured database connection

    Raises:
        sqlite3.OperationalError: If connection cannot be established
    """
    _log_db_connection("opening")
    start_time = time.time()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA foreign_keys=ON")
        duration_ms = (time.time() - start_time) * 1000
        _log_db_connection(f"opened (duration_ms={duration_ms:.2f})")
        return conn
    except sqlite3.OperationalError as e:
        _log_db_connection(f"FAILED: {e}")
        logger.error(f"Failed to create DB connection: {e}")
        raise

def execute_with_fk(conn, sql, params=()):
    """
    Execute SQL with foreign key support enabled.

    Note: This function enables foreign keys for the current execution,
    but the connection's PRAGMA setting should be used for persistent
    foreign key enforcement.

    Args:
        conn: Database connection
        sql: SQL statement to execute
        params: Optional parameters for the SQL statement

    Returns:
        cursor: The executed cursor
    """
    _log_db_op("EXECUTE_WITH_FK", sql=sql)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    c.execute(sql, params)
    return c

@contextmanager
def row_read_lock(table: str, row_id: str):
    """
    Context manager for row-level read lock at DB level.

    This context manager provides a read lock at the row level. Before
    acquiring the lock, it waits for any pending WAL flushes to complete
    to ensure consistency.

    The lock uses BEGIN (read transaction) which allows concurrent reads
    but blocks when a write lock is held.

    Args:
        table: Table name
        row_id: Row identifier

    Yields:
        sqlite3.Connection: Database connection with read lock

    Raises:
        sqlite3.OperationalError: If lock cannot be acquired
    """
    _log_db_lock("ACQUIRING", table, row_id, "row_read")
    start_time = time.time()
    max_wait = 30.0
    wait_start = time.time()

    while cache_layer._is_row_wal_pending(table, row_id) and (time.time() - wait_start) < max_wait:
        time.sleep(0.1)
    wait_duration_ms = (time.time() - wait_start) * 1000
    if wait_duration_ms > 100:
        _log_db_lock("WAITED", table, row_id, f"wal_pending wait_ms={wait_duration_ms:.2f}")

    conn = make_connection()
    try:
        c = conn.cursor()
        c.execute("BEGIN")
        _log_db_lock("ACQUIRED", table, row_id, "row_read")
        yield conn
        conn.rollback()
    except sqlite3.OperationalError as e:
        _log_db_lock("FAILED", table, row_id, f"row_read error={e}")
        logger.error(f"Row read lock failed for {table}:{row_id}: {e}")
        raise
    finally:
        conn.close()
        duration_ms = (time.time() - start_time) * 1000
        _log_db_lock("RELEASED", table, row_id, f"row_read duration_ms={duration_ms:.2f}")

@contextmanager
def table_read_lock(table: str):
    """
    Context manager for table-level read lock.

    This context manager provides a read lock at the table level. Before
    acquiring the lock, it waits for any pending WAL flushes to complete
    to ensure consistency across all rows in the table.

    The lock uses BEGIN (read transaction) which allows concurrent reads
    but blocks when a write lock is held.

    Args:
        table: Table name

    Yields:
        sqlite3.Connection: Database connection with read lock

    Raises:
        sqlite3.OperationalError: If lock cannot be acquired
    """
    _log_db_lock("ACQUIRING", table, None, "table_read")
    start_time = time.time()
    max_wait = 30.0
    wait_start = time.time()

    while cache_layer._is_table_wal_pending(table) and (time.time() - wait_start) < max_wait:
        time.sleep(0.1)
    wait_duration_ms = (time.time() - wait_start) * 1000
    if wait_duration_ms > 100:
        _log_db_lock("WAITED", table, None, f"table_wal_pending wait_ms={wait_duration_ms:.2f}")

    conn = make_connection()
    try:
        c = conn.cursor()
        c.execute("BEGIN")
        _log_db_lock("ACQUIRED", table, None, "table_read")
        yield conn
        conn.rollback()
    except sqlite3.OperationalError as e:
        _log_db_lock("FAILED", table, None, f"table_read error={e}")
        logger.error(f"Table read lock failed for {table}: {e}")
        raise
    finally:
        conn.close()
        duration_ms = (time.time() - start_time) * 1000
        _log_db_lock("RELEASED", table, None, f"table_read duration_ms={duration_ms:.2f}")

@contextmanager
def row_write_lock(table: str, row_id: str):
    """
    Context manager for row-level write lock.

    This context manager provides a write lock at the row level using
    BEGIN IMMEDIATE which acquires the write lock immediately.

    The lock blocks all other readers and writers for this row until
    the transaction completes. Use this for operations that modify data.

    Args:
        table: Table name
        row_id: Row identifier

    Yields:
        sqlite3.Connection: Database connection with write lock

    Raises:
        sqlite3.OperationalError: If lock cannot be acquired
    """
    _log_db_lock("ACQUIRING", table, row_id, "row_write")
    start_time = time.time()
    conn = make_connection()
    try:
        c = conn.cursor()
        c.execute("BEGIN IMMEDIATE")
        _log_db_lock("ACQUIRED", table, row_id, "row_write")
        yield conn
        conn.commit()
    except sqlite3.OperationalError as e:
        _log_db_lock("FAILED", table, row_id, f"row_write error={e}")
        logger.error(f"Row write lock failed for {table}:{row_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        duration_ms = (time.time() - start_time) * 1000
        _log_db_lock("RELEASED", table, row_id, f"row_write duration_ms={duration_ms:.2f}")

@contextmanager
def table_write_lock(table: str):
    """
    Context manager for table-level write lock.

    This context manager provides a write lock at the table level using
    BEGIN IMMEDIATE which acquires the write lock immediately.

    The lock blocks all other readers and writers for this table until
    the transaction completes. Use this for operations that modify data
    across multiple rows.

    Args:
        table: Table name

    Yields:
        sqlite3.Connection: Database connection with write lock

    Raises:
        sqlite3.OperationalError: If lock cannot be acquired
    """
    _log_db_lock("ACQUIRING", table, None, "table_write")
    start_time = time.time()
    conn = make_connection()
    try:
        c = conn.cursor()
        c.execute("BEGIN IMMEDIATE")
        _log_db_lock("ACQUIRED", table, None, "table_write")
        yield conn
        conn.commit()
    except sqlite3.OperationalError as e:
        _log_db_lock("FAILED", table, None, f"table_write error={e}")
        logger.error(f"Table write lock failed for {table}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        duration_ms = (time.time() - start_time) * 1000
        _log_db_lock("RELEASED", table, None, f"table_write duration_ms={duration_ms:.2f}")

def flush_wal(table: str) -> None:
    """
    Force WAL checkpoint for table.

    This function forces SQLite to perform a WAL checkpoint, which:
    1. Flushes all WAL pages to the main database file
    2. Truncates the WAL file
    3. Ensures durability of all committed transactions

    This is called by the cache layer to ensure that reads don't
    access stale data after writes have completed.

    Args:
        table: Table name (used for logging only)

    Raises:
        sqlite3.OperationalError: If checkpoint fails
    """
    _log_db_op("WAL_FLUSH_START", table)
    start_time = time.time()
    conn = make_connection()
    try:
        c = conn.cursor()
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        duration_ms = (time.time() - start_time) * 1000
        _log_db_op("WAL_FLUSH_COMPLETE", table, f"duration_ms={duration_ms:.2f}")
    except sqlite3.OperationalError as e:
        _log_db_op("WAL_FLUSH_FAILED", table, f"error={e}")
        logger.error(f"WAL flush failed for {table}: {e}")
        raise
    finally:
        conn.close()

# Register WAL flush callbacks
logger.debug("[DB] Registering WAL flush callbacks")
cache_layer.register_flush_callback("chats", lambda: flush_wal("chats"))
logger.debug("[DB] Registered flush callback for 'chats'")
cache_layer.register_flush_callback("messages", lambda: flush_wal("messages"))
logger.debug("[DB] Registered flush callback for 'messages'")
cache_layer.register_flush_callback("canvases", lambda: flush_wal("canvases"))
logger.debug("[DB] Registered flush callback for 'canvases'")
cache_layer.register_flush_callback("canvas_versions", lambda: flush_wal("canvas_versions"))
logger.debug("[DB] Registered flush callback for 'canvas_versions'")
cache_layer.register_flush_callback("canvas_permissions", lambda: flush_wal("canvas_permissions"))
logger.debug("[DB] Registered flush callback for 'canvas_permissions'")
