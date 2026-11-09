import asyncio
import threading

import pytest

from backend.tools.implementations import run_slot
from backend.tools.implementations.run_slot import RunQueueFull, RunQueueTimeout, async_run_slot, run_slot as sync_run_slot


@pytest.fixture(autouse=True)
def clean_state():
    """Every test starts and ends with a free lock and zero counters."""
    assert not run_slot._lock.locked() and run_slot._counts == {}
    yield
    assert not run_slot._lock.locked(), "the slot leaked"
    assert run_slot._counts == {}, "a counter leaked"


@pytest.fixture
def cap(monkeypatch):
    def _set(value):
        monkeypatch.setattr("backend.config.CODE_RUNNER_MAX_QUEUED_PER_USER", value)
    _set(2)
    return _set


def test_two_threads_never_hold_the_slot_together():
    first_in, release_first, second_in = threading.Event(), threading.Event(), threading.Event()
    done = []

    def first():
        with sync_run_slot("u1", timeout=5):
            first_in.set()
            release_first.wait(5)
            done.append("first")

    def second():
        with sync_run_slot("u2", timeout=5):
            second_in.set()
            done.append("second")

    t1 = threading.Thread(target=first); t1.start()
    assert first_in.wait(5)
    t2 = threading.Thread(target=second); t2.start()
    t2.join(timeout=0.2)
    assert t2.is_alive() and not second_in.is_set()  # still waiting while the first holds the slot
    release_first.set()
    t1.join(5); t2.join(5)
    assert not t1.is_alive() and not t2.is_alive()
    assert done == ["first", "second"]  # one after the other, in order


def test_the_third_concurrent_entry_of_one_user_is_refused_but_another_user_queues(cap):
    held, release = threading.Event(), threading.Event()
    entered = []

    def hold(user):
        with sync_run_slot(user, timeout=5):
            entered.append(user)
            held.set()
            release.wait(5)

    t1 = threading.Thread(target=hold, args=("u1",)); t1.start()
    assert held.wait(5)  # u1: one running
    t2 = threading.Thread(target=hold, args=("u1",)); t2.start()
    for _ in range(200):  # u1's second run is queued (counted, waiting)
        if run_slot._counts.get("u1") == 2:
            break
        threading.Event().wait(0.01)
    assert run_slot._counts.get("u1") == 2
    with pytest.raises(RunQueueFull):
        with sync_run_slot("u1", timeout=0.1):
            pytest.fail("a third run of one user must not enter")
    t3 = threading.Thread(target=hold, args=("u2",)); t3.start()  # another user still queues
    for _ in range(200):
        if run_slot._counts.get("u2") == 1:
            break
        threading.Event().wait(0.01)
    assert run_slot._counts.get("u2") == 1
    release.set()
    for t in (t1, t2, t3):
        t.join(5)
        assert not t.is_alive()
    assert sorted(entered) == ["u1", "u1", "u2"]


def test_a_short_timeout_raises_and_leaves_the_lock_to_its_holder():
    holder_in, release = threading.Event(), threading.Event()

    def hold():
        with sync_run_slot("u1", timeout=5):
            holder_in.set()
            release.wait(5)

    t = threading.Thread(target=hold); t.start()
    assert holder_in.wait(5)
    with pytest.raises(RunQueueTimeout):
        with sync_run_slot("u2", timeout=0.05):
            pytest.fail("a timed-out run must never proceed unlocked")
    assert run_slot._lock.locked()  # still the holder's
    release.set(); t.join(5)


@pytest.mark.anyio
async def test_async_slot_waits_without_blocking_the_event_loop_and_enters_after_release():
    order = []
    async with async_run_slot("u1", timeout=5, poll=0):
        async def waiter():
            async with async_run_slot("u2", timeout=5, poll=0):
                order.append("waiter-in")

        task = asyncio.ensure_future(waiter())
        for _ in range(5):  # another coroutine runs while the waiter polls
            await asyncio.sleep(0)
            order.append("loop-alive")
        assert "waiter-in" not in order and not task.done()
        # work handed to the default executor still runs while a waiter polls (no executor threads are used for waiting)
        assert await asyncio.to_thread(lambda: "ran") == "ran"
    await asyncio.wait_for(task, 5)
    assert order[-1] == "waiter-in" and order.count("loop-alive") == 5


@pytest.mark.anyio
async def test_async_slot_times_out_and_counts_return_to_zero():
    async with async_run_slot("u1", timeout=5, poll=0):
        with pytest.raises(RunQueueTimeout):
            async with async_run_slot("u2", timeout=0.01, poll=0):
                pytest.fail("must not enter")
        assert run_slot._counts == {"u1": 1}


@pytest.mark.anyio
async def test_cancelling_a_waiter_leaks_nothing():
    async with async_run_slot("u1", timeout=5, poll=0):
        async def waiter():
            async with async_run_slot("u2", timeout=5, poll=0):
                pytest.fail("must not enter")

        task = asyncio.ensure_future(waiter())
        for _ in range(3):
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert run_slot._counts == {"u1": 1}
    async with async_run_slot("u3", timeout=5, poll=0):  # the slot is free again
        pass


@pytest.mark.anyio
async def test_async_slot_refuses_the_third_entry_of_one_user(cap):
    async with async_run_slot("u1", timeout=5, poll=0):
        async def second():
            async with async_run_slot("u1", timeout=5, poll=0):
                pass
        queued = asyncio.ensure_future(second())
        await asyncio.sleep(0)
        assert run_slot._counts == {"u1": 2}
        with pytest.raises(RunQueueFull):
            async with async_run_slot("u1", timeout=5, poll=0):
                pytest.fail("must not enter")
    await asyncio.wait_for(queued, 5)


def test_counters_return_to_zero_after_an_error_inside_the_slot():
    with pytest.raises(ValueError):
        with sync_run_slot("u1", timeout=1):
            raise ValueError("run failed")


@pytest.mark.anyio
async def test_async_slot_is_released_when_the_block_raises():
    with pytest.raises(ValueError):
        async with async_run_slot("u1", timeout=5, poll=0):
            raise ValueError("boom")
    assert not run_slot._lock.locked() and not run_slot._counts
    async with async_run_slot("u1", timeout=5, poll=0):  # usable again
        pass


def test_the_default_timeout_comes_from_the_config(monkeypatch):
    monkeypatch.setattr(run_slot.config, "CODE_RUNNER_QUEUE_TIMEOUT", 0)
    with sync_run_slot("u1"):
        with pytest.raises(RunQueueTimeout):
            with sync_run_slot("u2"):
                pass

