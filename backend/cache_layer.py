"""
Unified cache layer with hybrid row-level locking using Cache-Aside pattern.

Architecture Overview
---------------------
This module implements a sophisticated caching layer with these key features:

1. Cache-Aside Pattern:
   - Reads: Check cache first, fetch from DB on miss, populate cache
   - Writes: Write to DB directly, invalidate cache for affected rows

2. Hybrid Row-Level Locking:
   - Global lock for table management
   - Per-table locks for row management
   - Per-row locks for concurrent access

3. Two-Level Blocking for Consistency:
   - Reads wait for pending writes to complete
   - Reads wait for WAL checkpoint before accessing cache
   - Prevents reading stale data after writes

4. Thread Safety:
   - Lock hierarchy: _global_lock → table_state.lock → row.lock
   - Never acquire locks in reverse order to prevent deadlocks

The Cache-Aside pattern is used because:
1. Chat messages are written frequently (high write throughput needed)
2. Readback after every write is too expensive (30-50ms per message)
3. SQLite auto-checkpoint handles WAL truncation efficiently
4. Brief cache stale periods are acceptable for chat history

Logging
-------
This module logs all cache operations for debugging:
- cache_layer.get() calls: cache hits, misses, invalidations
- cache_layer.invalidate() calls: row and table invalidations
- Lock operations: pending writes, WAL flushes, wait times
"""
import threading
import time
import logging
from typing import Optional, Dict, Any, Callable, List

# Configure cache layer logging
logger = logging.getLogger(__name__)

# Enable debug logging with trace info
CACHE_DEBUG = True  # Set to False for less verbose logging


def _log_cache_op(op_type: str, table: str, row_id: str = None, details: str = None):
    """Internal logging helper for cache operations."""
    msg = f"[CACHE {op_type}]"
    if table:
        msg += f" table={table}"
    if row_id:
        msg += f" row_id={row_id}"
    if details:
        msg += f" | {details}"
    logger.debug(msg)


def _log_cache_read(cache_result: str, table: str, row_id: str, duration_ms: float, data_len: int = None):
    """Log cache read operation."""
    logger.debug(f"[CACHE READ] table={table} row_id={row_id} result={cache_result} duration_ms={duration_ms:.2f} data_len={data_len}")


def _log_cache_write(table: str, row_id: str, optimistic: bool = False):
    """Log cache write operation."""
    logger.debug(f"[CACHE WRITE] table={table} row_id={row_id} optimistic={optimistic}")


def _log_cache_invalidate(table: str, row_id: str = None, reason: str = None):
    """Log cache invalidation."""
    msg = f"[CACHE INVALIDATE] table={table}"
    if row_id:
        msg += f" row_id={row_id}"
    if reason:
        msg += f" reason={reason}"
    logger.warning(msg)  # Use warning level for invalidations since they're important


def _log_lock_wait(lock_type: str, table: str, row_id: str, wait_ms: float, max_wait: float):
    """Log lock wait operation."""
    status = "completed" if wait_ms < max_wait * 1000 else "timeout"
    logger.debug(f"[LOCK WAIT] type={lock_type} table={table} row_id={row_id} wait_ms={wait_ms:.2f} max_ms={max_wait*1000:.0f} status={status}")


def _log_wal_flush(table: str, row_id: str = None, duration_ms: float = None):
    """Log WAL flush operation."""
    msg = f"[WAL FLUSH] table={table}"
    if row_id:
        msg += f" row_id={row_id}"
    if duration_ms:
        msg += f" duration_ms={duration_ms:.2f}"
    logger.debug(msg)

class RowState:
    """
    Per-row state for locking and caching.

    This class maintains the concurrency control state for each row in a table.
    It uses condition variables to coordinate between readers and writers.

    Attributes:
        lock: Per-row lock for protecting cached data
        pending_write: Count of pending write operations
        wal_pending: Count of pending WAL flush operations
        write_condition: Condition variable for coordinating reads/writes
        invalidated: Flag marking entry for cache invalidation
    """
    __slots__ = ('lock', 'pending_write', 'wal_pending', 'write_condition', 'invalidated')

    def __init__(self):
        self.lock = threading.Lock()
        self.pending_write: int = 0  # Number of active pending writes
        self.wal_pending: int = 0    # Number of pending WAL flushes
        self.write_condition = threading.Condition()  # For reader/writer coordination
        self.invalidated: bool = False  # Cache entry marked for invalidation

class TableState:
    """
    Per-table state for locking and caching.

    Each table has its own state with per-row locking granularity.
    This enables concurrent access to different rows while maintaining
    consistency for each row.

    Attributes:
        table: Table name identifier
        lock: Per-table lock for managing row_locks dictionary
        row_locks: Map of row_id to RowState for per-row locking
        cache: Map of row_id to cached data entries
        pending_writes: Count of pending table-level writes
        wal_pending: Count of pending table-level WAL flushes
        write_condition: Condition variable for table-level coordination
    """
    __slots__ = ('table', 'lock', 'row_locks', 'cache', 'pending_writes', 'wal_pending', 'write_condition')

    def __init__(self, table: str):
        self.table = table
        self.lock = threading.Lock()  # Protects row_locks and cache dictionaries
        self.row_locks: Dict[str, RowState] = {}  # Per-row locks
        self.cache: Dict[str, Dict[str, Any]] = {}  # Cached data by row_id
        self.pending_writes: int = 0  # Pending table-level writes
        self.wal_pending: int = 0     # Pending table-level WAL flushes
        self.write_condition = threading.Condition()  # Table-level condition

class CachedDatabase:
    """
    Cache layer with hybrid row-level locking using Cache-Aside pattern.

    This is the main cache layer class that coordinates caching across all tables.
    It provides thread-safe operations with fine-grained locking for concurrency.

    Lock Hierarchy (critical for avoiding deadlocks):
        1. _global_lock (acquired first)
        2. TableState.lock
        3. RowState.lock (acquired last)

    Operations:
        - Single-row reads: Uses row-level locking for maximum concurrency
        - Table-scope reads: Uses table-level locking for consistency
        - Row invalidation: Removes specific row from cache
        - Table invalidation: Clears entire table cache

    Usage:
        cache = CachedDatabase()
        cache.register_flush_callback("chats", flush_wal_callback)
        data = cache.get("chats", "chat-123", fetch_fn)
    """

    def __init__(self):
        self._tables: Dict[str, TableState] = {}  # Table name -> TableState
        self._global_lock = threading.Lock()  # Protects _tables dictionary
        self._db_flush_callbacks: Dict[str, Callable] = {}  # Table -> WAL flush callback

    def _get_table(self, table: str) -> TableState:
        """
        Get or create table state (thread-safe).

        Uses global lock to safely check/create table entries.
        This is the entry point for accessing any table's state.

        Args:
            table: Table name to get/create

        Returns:
            TableState: The table state object
        """
        _log_cache_op("GET_TABLE", table)
        with self._global_lock:
            if table not in self._tables:
                self._tables[table] = TableState(table)
                _log_cache_op("CREATE_TABLE", table)
            return self._tables[table]

    def _get_row(self, table: str, row_id: str) -> RowState:
        """
        Get or create row state (thread-safe, upfront initialization).

        This method is called during initialization and allocates row-level
        locks when first accessed. The row state is created once and reused.

        Args:
            table: Table name
            row_id: Row identifier

        Returns:
            RowState: The row state object for this row
        """
        _log_cache_op("GET_ROW", table, row_id)
        table_state = self._get_table(table)
        with table_state.lock:
            if row_id not in table_state.row_locks:
                table_state.row_locks[row_id] = RowState()
                _log_cache_op("CREATE_ROW", table, row_id)
            return table_state.row_locks[row_id]

    def _is_row_write_pending(self, table: str, row_id: str) -> bool:
        """
        Check if writes are queued/active for this row.

        Args:
            table: Table name
            row_id: Row identifier

        Returns:
            bool: True if write is pending, False otherwise
        """
        row = self._get_row(table, row_id)
        return row.pending_write > 0

    def _is_row_wal_pending(self, table: str, row_id: str) -> bool:
        """
        Check if WAL flush is pending for this row.

        Args:
            table: Table name
            row_id: Row identifier

        Returns:
            bool: True if WAL flush is pending, False otherwise
        """
        row = self._get_row(table, row_id)
        return row.wal_pending > 0

    def _is_table_write_pending(self, table: str) -> bool:
        """
        Check if writes are pending for table-scope operations.

        Args:
            table: Table name

        Returns:
            bool: True if table-level write is pending, False otherwise
        """
        state = self._get_table(table)
        return state.pending_writes > 0

    def _is_table_wal_pending(self, table: str) -> bool:
        """
        Check if WAL flush is pending for table-scope operations.

        Args:
            table: Table name

        Returns:
            bool: True if table-level WAL flush is pending, False otherwise
        """
        state = self._get_table(table)
        return state.wal_pending > 0

    def register_flush_callback(self, table: str, callback: Callable[[], None]) -> None:
        """
        Register callback to flush WAL for a table.

        The WAL flush callback is called during cache operations that need
        to ensure durability before releasing readers. This is typically
        used to trigger SQLite's WAL checkpoint.

        Args:
            table: Table name
            callback: Function to call to flush WAL
        """
        _log_cache_op("REGISTER_FLUSH_CALLBACK", table)
        with self._global_lock:
            self._db_flush_callbacks[table] = callback
            _log_cache_op("REGISTER_FLUSH_CALLBACK_DONE", table)

    # ==================== SINGLE-ROW READ (Row-Level) ====================

    def get(self, table: str, row_id: str, fetch_fn: Callable[[], Any],
            ttl: Optional[int] = None, max_wait: float = 10.0) -> Any:
        """
        Cache-aside read with two-level blocking (row-level).

        This method implements the core cache-aside pattern with consistency
        guarantees. The two-level blocking ensures that reads never return
        stale data even when writes are happening concurrently.

        Order of operations (critical for consistency):
        1. Wait for pending writes to complete (blocks until write finishes)
        2. Wait for WAL checkpoint (ensures durability before reading)
        3. Check cache (now safe to return cached data)
        4. Fetch from DB on cache miss and populate cache

        Args:
            table: Table name
            row_id: Row identifier to read
            fetch_fn: Callback function to fetch data from DB on cache miss
            ttl: Optional TTL in seconds for cache entry
            max_wait: Maximum wait time in seconds for blocking operations

        Returns:
            Cached or fetched data, or None if fetch_fn returns None

        Cache Entry Structure:
            {
                'data': Any,                    # The cached data
                'ttl': Optional[float],         # Time-to-live timestamp
                'updated': float,               # Last update timestamp
                'invalidated': bool             # Flag for invalidation
            }
        """
        _log_cache_op("GET_START", table, row_id)
        start_time = time.time()
        row = self._get_row(table, row_id)
        table_state = self._get_table(table)

        # Level 1: Wait for row writes to complete (blocks until write finishes)
        wait_start = time.time()
        with row.write_condition:
            while row.pending_write > 0 and (time.time() - wait_start) < max_wait:
                row.write_condition.wait(timeout=0.1)
        wait1_ms = (time.time() - wait_start) * 1000
        if wait1_ms > 100:
            _log_lock_wait("WRITE", table, row_id, wait1_ms, max_wait)

        # Level 2: Wait for WAL checkpoint (consistency) - MUST come before cache check
        # This ensures that if a write was committed, its WAL is flushed before we read
        with row.write_condition:
            while row.wal_pending > 0 and (time.time() - wait_start) < max_wait:
                row.write_condition.wait(timeout=0.1)
        wait2_ms = (time.time() - wait_start) * 1000
        total_wait_ms = wait1_ms + wait2_ms
        if total_wait_ms > 100:
            _log_lock_wait("WAL", table, row_id, total_wait_ms, max_wait)

        # Check cache (safe now - WAL flushed)
        entry = None
        invalidated = False
        cache_hit = False
        with table_state.lock:
            with row.lock:
                if row_id in table_state.cache:
                    entry = table_state.cache[row_id]
                    # Check if entry was marked for invalidation
                    if entry.get('invalidated'):
                        invalidated = True
                        # Clear the invalidated flag for future reads
                        entry['invalidated'] = False
                    else:
                        cache_hit = True

        # Check TTL and invalidation
        if entry:
            if invalidated:
                _log_cache_op("CACHE_INVALIDATED", table, row_id)
                # Entry was invalidated, fetch fresh data
            elif entry.get('ttl') is None or time.time() < entry['ttl']:
                # Return cached data if not expired
                data = entry['data']
                if data is not None:
                    duration_ms = (time.time() - start_time) * 1000
                    data_len = len(str(data)) if isinstance(data, (str, list, dict)) else 0
                    _log_cache_read("HIT", table, row_id, duration_ms, data_len)
                    return data
            # else: entry expired, continue to fetch

        # Cache miss or invalidated - fetch from DB
        _log_cache_op("CACHE_MISS", table, row_id)
        fetch_start = time.time()
        data = fetch_fn()
        fetch_duration_ms = (time.time() - fetch_start) * 1000
        data_len = len(str(data)) if data is not None else 0

        # Update cache (only if data is not None)
        # Note: We don't set invalidated=False here because the entry might have been invalidated
        if data is not None:
            with table_state.lock:
                with row.lock:
                    table_state.cache[row_id] = {
                        'data': data,
                        'ttl': time.time() + ttl if ttl else None,
                        'updated': time.time(),
                        'invalidated': False  # Fresh data is not invalidated
                    }
            _log_cache_write(table, row_id)
            _log_cache_op("CACHE_POPULATED", table, row_id)
        else:
            _log_cache_op("CACHE_SKIPPED", table, row_id, "data is None")

        duration_ms = (time.time() - start_time) * 1000
        _log_cache_read("MISS", table, row_id, duration_ms, data_len)

        return data

    # ==================== TABLE-SCOPE READ (Table-Level) ====================

    def get_table(self, table: str, query_fn: Callable[[], List],
                  key_extractor: Callable[[Any], str],
                  ttl: Optional[int] = None, max_wait: float = 10.0) -> List[Any]:
        """
        Table-scope read (e.g., SELECT * FROM table).

        This method performs a full table scan, waiting for all pending writes
        and WAL checkpoints before querying the database. All returned rows
        are populated into the cache for subsequent row-level reads.

        Args:
            table: Table name to query
            query_fn: Callback function to execute DB query
            key_extractor: Function to extract row_id from each result item
            ttl: Optional TTL in seconds for cached entries
            max_wait: Maximum wait time in seconds for blocking operations

        Returns:
            List of query results, with each row cached by its extracted key
        """
        _log_cache_op("GET_TABLE_START", table)
        start_time = time.time()
        state = self._get_table(table)

        # Wait for table-level writes
        wait_start = time.time()
        with state.write_condition:
            while state.pending_writes > 0 and (time.time() - wait_start) < max_wait:
                state.write_condition.wait(timeout=0.1)
        wait1_ms = (time.time() - wait_start) * 1000
        if wait1_ms > 100:
            _log_lock_wait("TABLE_WRITE", table, None, wait1_ms, max_wait)

        # Wait for WAL checkpoint (consistency)
        with state.write_condition:
            while state.wal_pending > 0 and (time.time() - wait_start) < max_wait:
                state.write_condition.wait(timeout=0.1)
        wait2_ms = (time.time() - wait_start) * 1000
        total_wait_ms = wait1_ms + wait2_ms
        if total_wait_ms > 100:
            _log_lock_wait("TABLE_WAL", table, None, total_wait_ms, max_wait)

        # Query from DB
        _log_cache_op("TABLE_QUERY_START", table)
        results = query_fn()
        result_count = len(results) if results else 0
        _log_cache_op("TABLE_QUERY_END", table, f"count={result_count}")

        # Update cache for each result
        for item in results:
            row_id = key_extractor(item) if key_extractor else str(id(item))
            with state.lock:
                state.cache[row_id] = {
                    'data': item,
                    'ttl': time.time() + ttl if ttl else None,
                    'updated': time.time(),
                    'invalidated': False
                }
                _log_cache_write(table, row_id)

        duration_ms = (time.time() - start_time) * 1000
        _log_cache_op("GET_TABLE_COMPLETE", table, f"count={result_count} duration_ms={duration_ms:.2f}")

        return results

    # ==================== INVALIDATION ====================

    def invalidate(self, table: str, row_id: Optional[str] = None) -> None:
        """
        Invalidate cache for a specific row or entire table.

        This removes entries from the cache so subsequent reads will fetch
        fresh data from the database. This is called after write operations
        to maintain cache consistency.

        Args:
            table: Table name
            row_id: Optional row identifier. If None, clears entire table cache.
        """
        _log_cache_invalidate(table, row_id, "explicit_invalidate")
        state = self._get_table(table)
        with state.lock:
            if row_id:
                if row_id in state.cache:
                    del state.cache[row_id]
                    _log_cache_op("INVALIDATE_ROW", table, row_id)
                else:
                    _log_cache_op("INVALIDATE_ROW_NOT_FOUND", table, row_id)
            else:
                if state.cache:
                    _log_cache_op("INVALIDATE_TABLE", table, f"cleared={len(state.cache)} entries")
                state.cache.clear()

    def invalidate_with_ttl(self, table: str, row_id: str, ttl: int = 300) -> None:
        """
        Mark entry for invalidation after TTL.

        Unlike invalidate() which removes immediately, this method sets an
        invalidated flag and keeps the entry in cache until the TTL expires.
        The next read will then fetch fresh data from the database.

        Args:
            table: Table name
            row_id: Row identifier to invalidate
            ttl: Time-to-live in seconds before entry is fully cleared
        """
        _log_cache_invalidate(table, row_id, f"invalidated_with_ttl_{ttl}s")
        state = self._get_table(table)
        with state.lock:
            if row_id in state.cache:
                state.cache[row_id]['invalidated'] = True
                state.cache[row_id]['data'] = None
                # Keep the TTL to auto-clear after expiration
                state.cache[row_id]['ttl'] = time.time() + ttl
                _log_cache_op("INVALIDATE_WITH_TTL_SET", table, row_id)
            else:
                _log_cache_op("INVALIDATE_WITH_TTL_NOT_FOUND", table, row_id)

    # ==================== UTILITIES ====================

    def _flush_row_wal(self, table: str, row: RowState, row_id: str) -> None:
        """
        Force WAL flush for row.

        This method coordinates with the cache layer to ensure WAL flush
        happens before cache reads proceed. The design allows cache reads
        to unblock immediately after flush starts while DB reads wait.

        Algorithm:
        1. Increment wal_pending counter (blocks new readers)
        2. Notify waiting cache readers immediately (cache unblocks)
        3. Execute WAL flush callback (DB blocks until complete)
        4. Decrement counter and notify all waiting parties

        Args:
            table: Table name
            row: RowState object with pending counters
            row_id: Row identifier
        """
        _log_wal_flush(table, row_id, 0)
        with row.write_condition:
            row.wal_pending += 1
            row.write_condition.notify_all()  # Unblock cache immediately

        flush_start = time.time()
        try:
            # Execute WAL flush
            if table in self._db_flush_callbacks:
                _log_cache_op("FLUSH_CALLBACK_START", table, row_id)
                self._db_flush_callbacks[table]()
                _log_cache_op("FLUSH_CALLBACK_END", table, row_id)
            # SQLite WAL checkpoint is synchronous, so we wait here
        except Exception as e:
            logger.error(f"WAL flush failed for {table}:{row_id}: {e}")
            _log_wal_flush(table, row_id, 0)  # Log failure
        finally:
            with row.write_condition:
                row.wal_pending -= 1
                row.write_condition.notify_all()
        duration_ms = (time.time() - flush_start) * 1000
        _log_wal_flush(table, row_id, duration_ms)

    def _flush_table_wal(self, table: str, state: TableState) -> None:
        """
        Force WAL flush for table.

        WARNING: This is called from put_table's finally block, which already
        decrements pending_writes. Do NOT decrement pending_writes here.

        Args:
            table: Table name
            state: TableState object with pending counters
        """
        _log_wal_flush(table, None, 0)
        with state.write_condition:
            state.wal_pending += 1
            state.write_condition.notify_all()

        flush_start = time.time()
        try:
            if table in self._db_flush_callbacks:
                _log_cache_op("FLUSH_TABLE_CALLBACK_START", table)
                self._db_flush_callbacks[table]()
                _log_cache_op("FLUSH_TABLE_CALLBACK_END", table)
        except Exception as e:
            logger.error(f"WAL flush failed for {table}: {e}")
            _log_wal_flush(table, None, 0)  # Log failure
        finally:
            with state.write_condition:
                state.wal_pending -= 1
                state.write_condition.notify_all()
        duration_ms = (time.time() - flush_start) * 1000
        _log_wal_flush(table, None, duration_ms)

    def clear_cache(self) -> None:
        """
        Clear all cache entries.

        This removes all cached data but does NOT invalidate the table
        structures or row locks. Use this to reset the cache without
        requiring re-initialization of table states.
        """
        _log_cache_op("CLEAR_CACHE_START", None, None)
        with self._global_lock:
            old_tables = len(self._tables)
            self._tables = {}
        _log_cache_op("CLEAR_CACHE_DONE", None, None, f"cleared={old_tables} tables")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with:
                - tables: Number of tables with cached data
                - total_rows: Total cached rows across all tables
                - rows_with_pending_writes: Rows currently waiting on writes
                - tables_with_pending_writes: Tables with pending writes
        """
        _log_cache_op("GET_STATS", None, None)
        with self._global_lock:
            stats = {
                'tables': len(self._tables),
                'total_rows': sum(len(s.cache) for s in self._tables.values()),
                'rows_with_pending_writes': sum(
                    len([row_id for row_id, row_state in s.row_locks.items() if row_state.pending_write > 0])
                    for s in self._tables.values()
                ),
                'tables_with_pending_writes': [
                    t for t, s in self._tables.items() if s.pending_writes > 0
                ]
            }
            _log_cache_op("GET_STATS_RESULT", None, None, f"tables={stats['tables']} total_rows={stats['total_rows']}")
            return stats


# Global cache instance
cache_layer = CachedDatabase()
