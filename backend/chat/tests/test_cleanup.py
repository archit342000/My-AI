import pytest
from unittest.mock import MagicMock, patch

from backend.chat import cleanup


@pytest.fixture
def mocks():
    with patch.object(cleanup, 'db') as db, patch.object(cleanup, 'task_manager') as tm, patch.object(cleanup, 'log_event') as events, \
         patch.object(cleanup.config, 'TEMPORARY_CHAT_TTL_SECONDS', 1000):
        tm.is_task_running.return_value = False
        tm.claim_turn.return_value = True
        db.get_chat.return_value = {"is_temporary": 1}
        yield db, tm, events


def test_expired_chats_are_deleted_using_the_cutoff_from_the_ttl(mocks):
    db, tm, events = mocks
    db.get_expired_temporary_chats.return_value = ["a", "b"]
    delete = MagicMock(return_value=True)
    removed = cleanup.purge_expired_temporary_chats("u1", delete, now=5000.0)
    assert removed == ["a", "b"]
    db.get_expired_temporary_chats.assert_called_once_with("u1", 4000.0)  # now minus the TTL
    assert [c.args[0] for c in delete.call_args_list] == ["a", "b"]
    assert [c.args for c in events.call_args_list] == [("temporary_chat_expired", {"chat_id": "a"}), ("temporary_chat_expired", {"chat_id": "b"})]


def test_a_chat_with_a_running_turn_is_skipped_never_stopped(mocks):
    db, tm, _ = mocks
    db.get_expired_temporary_chats.return_value = ["busy", "idle"]
    tm.is_task_running.side_effect = lambda chat_id: chat_id == "busy"
    delete = MagicMock(return_value=True)
    assert cleanup.purge_expired_temporary_chats("u1", delete, now=5000.0) == ["idle"]
    assert [c.args[0] for c in delete.call_args_list] == ["idle"]
    tm.stop_task_and_wait.assert_not_called()


def test_a_delete_that_could_not_finish_or_raised_is_left_for_the_next_time_and_the_rest_continue(mocks):
    db, _, events = mocks
    db.get_expired_temporary_chats.return_value = ["stuck", "boom", "ok"]

    def delete(chat_id):
        if chat_id == "boom":
            raise OSError("disk")
        return chat_id == "ok"

    assert cleanup.purge_expired_temporary_chats("u1", delete, now=5000.0) == ["ok"]
    assert any(c.args[0] == "temporary_chat_purge_error" and c.args[1]["chat_id"] == "boom" for c in events.call_args_list)


def test_a_failing_lookup_is_logged_and_never_raised(mocks):
    db, _, events = mocks
    db.get_expired_temporary_chats.side_effect = RuntimeError("db down")
    delete = MagicMock()
    assert cleanup.purge_expired_temporary_chats("u1", delete) == []
    delete.assert_not_called()
    assert events.call_args_list[0].args[0] == "temporary_chat_purge_error"


def test_nothing_expired_deletes_nothing(mocks):
    db, _, _ = mocks
    db.get_expired_temporary_chats.return_value = []
    delete = MagicMock()
    assert cleanup.purge_expired_temporary_chats("u1", delete) == []
    delete.assert_not_called()


def test_a_chat_whose_turn_slot_is_taken_by_a_send_is_skipped(mocks):
    db, tm, _ = mocks
    db.get_expired_temporary_chats.return_value = ["sending", "idle"]
    tm.claim_turn.side_effect = lambda chat_id: chat_id != "sending"
    delete = MagicMock(return_value=True)
    assert cleanup.purge_expired_temporary_chats("u1", delete, now=5000.0) == ["idle"]
    assert [c.args[0] for c in delete.call_args_list] == ["idle"]
    tm.release_turn_claim.assert_called_once_with("idle")  # only a claim that was taken is released


def test_the_turn_slot_is_released_even_when_the_delete_fails_or_the_chat_is_skipped(mocks):
    db, tm, _ = mocks
    db.get_expired_temporary_chats.return_value = ["a", "b", "c"]
    tm.is_task_running.side_effect = lambda chat_id: chat_id == "c"
    delete = MagicMock(side_effect=[RuntimeError("boom"), True])
    assert cleanup.purge_expired_temporary_chats("u1", delete, now=5000.0) == ["b"]
    assert sorted(c.args[0] for c in tm.release_turn_claim.call_args_list) == ["a", "b", "c"]


def test_a_chat_saved_after_the_lookup_is_not_deleted(mocks):
    db, _, _ = mocks
    db.get_expired_temporary_chats.return_value = ["saved", "gone", "still"]
    db.get_chat.side_effect = lambda chat_id: {"saved": {"is_temporary": 0}, "gone": None}.get(chat_id, {"is_temporary": 1})
    delete = MagicMock(return_value=True)
    assert cleanup.purge_expired_temporary_chats("u1", delete, now=5000.0) == ["still"]
    assert [c.args[0] for c in delete.call_args_list] == ["still"]


def test_at_most_the_cap_is_removed_per_call(mocks):
    db, _, _ = mocks
    db.get_expired_temporary_chats.return_value = [f"c{i}" for i in range(cleanup.MAX_REMOVED_PER_CALL + 5)]
    delete = MagicMock(return_value=True)
    assert len(cleanup.purge_expired_temporary_chats("u1", delete, now=5000.0)) == cleanup.MAX_REMOVED_PER_CALL
