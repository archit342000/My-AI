import asyncio
import pytest
from unittest.mock import patch, MagicMock
from backend.file_system.channel import FileSystemPersistenceChannel, FileSystemChannelManager, ChannelState

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture(autouse=True)
def cleanup_manager():
    FileSystemChannelManager.cleanup()
    yield
    FileSystemChannelManager.cleanup()

@pytest.mark.anyio
async def test_channel_init():
    channel = FileSystemPersistenceChannel("test_chat")
    assert channel.chat_id == "test_chat"
    assert channel.state == ChannelState.FREE
    stats = channel.get_stats()
    assert stats["chat_id"] == "test_chat"
    assert stats["state"] == "free"

@pytest.mark.anyio
async def test_channel_acquire_release():
    channel = FileSystemPersistenceChannel("test_chat")
    
    # Acquire AI
    res = await channel.acquire("ai")
    assert res is True
    assert channel.state == ChannelState.LOCKED_AI
    
    # Release AI
    await channel.release()
    assert channel.state == ChannelState.FREE
    assert channel.get_stats()["total_operations"] == 1
    
    # Acquire User
    res = await channel.acquire("user")
    assert res is True
    assert channel.state == ChannelState.LOCKED_USER
    
    # Release User
    await channel.release()
    assert channel.state == ChannelState.FREE
    assert channel.get_stats()["total_operations"] == 2

@pytest.mark.anyio
async def test_channel_acquire_timeout():
    channel = FileSystemPersistenceChannel("test_chat")
    
    with patch("backend.config.FILE_SYSTEM_CHANNEL_ACQUIRE_TIMEOUT", 0.01):
        # Lock it first
        await channel.acquire("ai")
        
        # Second acquire should time out, force release, then acquire
        res = await channel.acquire("user")
        assert res is True
        assert channel.state == ChannelState.LOCKED_USER

@pytest.mark.anyio
async def test_channel_wait_if_blocked():
    channel = FileSystemPersistenceChannel("test_chat")
    
    # Not blocked
    res = await channel.wait_if_blocked("ai")
    assert res is True
    
    # Blocked by same type
    await channel.acquire("ai")
    res = await channel.wait_if_blocked("ai")
    assert res is True
    
    # Blocked by different type
    async def delayed_release():
        await asyncio.sleep(0.05)
        await channel.release()
    
    asyncio.create_task(delayed_release())
    res = await channel.wait_if_blocked("user")
    assert res is True

def test_manager_initialize_cleanup():
    assert not FileSystemChannelManager._initialized
    FileSystemChannelManager.initialize()
    assert FileSystemChannelManager._initialized
    FileSystemChannelManager.initialize() # idempotent
    FileSystemChannelManager.cleanup()
    assert not FileSystemChannelManager._initialized

def test_manager_get_release_channel():
    chan = FileSystemChannelManager.get_channel("chat1")
    assert chan.chat_id == "chat1"
    
    # Get same channel
    chan2 = FileSystemChannelManager.get_channel("chat1")
    assert chan is chan2
    
    FileSystemChannelManager.release_channel("chat1")
    chan3 = FileSystemChannelManager.get_channel("chat1")
    assert chan is not chan3

def test_manager_max_channels():
    FileSystemChannelManager._max_channels = 2
    FileSystemChannelManager.get_channel("c1")
    FileSystemChannelManager.get_channel("c2")
    FileSystemChannelManager.get_channel("c3")
    
    assert "c3" in FileSystemChannelManager._channels
    assert "c2" in FileSystemChannelManager._channels
    assert "c1" not in FileSystemChannelManager._channels
    FileSystemChannelManager._max_channels = 100

@patch("backend.database.db.get_all_chat_ids")
def test_manager_cleanup_stale_channels(mock_get_all_chats):
    mock_get_all_chats.return_value = ["active1", "of-another-user"]
    
    FileSystemChannelManager.get_channel("active1")
    FileSystemChannelManager.get_channel("stale1")
    
    FileSystemChannelManager.cleanup_stale_channels()
    
    assert "active1" in FileSystemChannelManager._channels
    assert "stale1" not in FileSystemChannelManager._channels

@patch("backend.database.db.get_all_chat_ids", side_effect=Exception("DB Error"))
def test_manager_cleanup_stale_channels_error(mock_get_all_chats):
    FileSystemChannelManager.get_channel("active1")
    FileSystemChannelManager.cleanup_stale_channels()
    # Should not raise exception
    assert "active1" in FileSystemChannelManager._channels

@pytest.mark.anyio
async def test_channel_multi_lock_contention():
    channel = FileSystemPersistenceChannel("test_chat_concurrency")
    
    # 1. Acquire initial lock (blocks all others)
    assert await channel.acquire("ai") is True
    assert channel.state == ChannelState.LOCKED_AI

    execution_order = []
    
    # Define tasks to acquire and release
    async def worker(worker_id: str, op_type: str):
        # This will block until the lock is released
        assert await channel.acquire(op_type) is True
        execution_order.append(f"{worker_id}_start")
        await asyncio.sleep(0.01) # Simulate minor operation
        await channel.release()
        execution_order.append(f"{worker_id}_end")

    # Spawn 3 concurrent acquire tasks
    t1 = asyncio.create_task(worker("w1", "user"))
    t2 = asyncio.create_task(worker("w2", "ai"))
    t3 = asyncio.create_task(worker("w3", "user"))

    # Let them register in the condition waiting queue
    await asyncio.sleep(0.02)
    assert len(execution_order) == 0  # Still blocked by initial lock

    # 2. Release initial lock -> lets the next one acquire
    await channel.release()
    
    # Wait for all workers to complete
    await asyncio.gather(t1, t2, t3)
    
    # Assert all completed
    assert len(execution_order) == 6
    
    # Verify strict serialization: each start must have its end before next start
    for i in range(0, 6, 2):
        start = execution_order[i]
        end = execution_order[i+1]
        assert start.split("_")[0] == end.split("_")[0]
        assert start.endswith("_start")
        assert end.endswith("_end")

def test_manager_lru_eviction_stats_validation():
    FileSystemChannelManager._max_channels = 3
    
    c1 = FileSystemChannelManager.get_channel("c1")
    c2 = FileSystemChannelManager.get_channel("c2")
    c3 = FileSystemChannelManager.get_channel("c3")
    
    assert "c1" in FileSystemChannelManager._channels
    assert "c2" in FileSystemChannelManager._channels
    assert "c3" in FileSystemChannelManager._channels
    
    # Get c4 -> c1 (oldest inserted) should be evicted
    c4 = FileSystemChannelManager.get_channel("c4")
    
    assert "c4" in FileSystemChannelManager._channels
    assert "c3" in FileSystemChannelManager._channels
    assert "c2" in FileSystemChannelManager._channels
    assert "c1" not in FileSystemChannelManager._channels
    
    # Restore defaults
    FileSystemChannelManager._max_channels = 100

