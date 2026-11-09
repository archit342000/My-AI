"""Per-user fixed-window rate limits: window arithmetic, independence, exemption and the search-limit helper."""
from unittest.mock import patch

import pytest

from backend import config
from backend.auth import rate_limit
from backend.auth.rate_limit import FixedWindowLimiter, SearchLimitReached, check_search_limit, is_exempt, reset_limiters


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_the_limit_is_enforced_and_the_window_rolls_over():
    clock = Clock()
    limiter = FixedWindowLimiter(2, 60, clock=clock)
    assert limiter.try_acquire("u1") == (True, 0)
    clock.now += 10
    assert limiter.try_acquire("u1") == (True, 0)
    allowed, retry_after = limiter.try_acquire("u1")
    assert allowed is False and retry_after == 50  # the window opened at t=1000, it is t=1010
    clock.now += 50  # exactly at the boundary the window is over
    assert limiter.try_acquire("u1") == (True, 0)


def test_a_denied_attempt_does_not_count_and_does_not_extend_the_window():
    clock = Clock()
    limiter = FixedWindowLimiter(1, 60, clock=clock)
    assert limiter.try_acquire("u1")[0] is True
    for _ in range(5):
        clock.now += 1
        assert limiter.try_acquire("u1")[0] is False
    clock.now = 1060
    assert limiter.try_acquire("u1")[0] is True  # the window ended on schedule, hits while denied changed nothing


def test_keys_are_independent():
    limiter = FixedWindowLimiter(1, 60, clock=Clock())
    assert limiter.try_acquire("u1")[0] is True
    assert limiter.try_acquire("u1")[0] is False
    assert limiter.try_acquire("u2")[0] is True


@pytest.mark.parametrize("limit", [0, -3])
def test_a_non_positive_limit_is_unlimited(limit):
    limiter = FixedWindowLimiter(limit, 60, clock=Clock())
    assert all(limiter.try_acquire("u1") == (True, 0) for _ in range(100))


def test_retry_after_is_at_least_one_second():
    clock = Clock()
    limiter = FixedWindowLimiter(1, 60, clock=clock)
    limiter.try_acquire("u1")
    clock.now += 59.6
    allowed, retry_after = limiter.try_acquire("u1")
    assert allowed is False and retry_after == 1


def test_reset_clears_the_singletons():
    rate_limit.turn_limiter.try_acquire("u1")
    rate_limit.search_limiter.try_acquire("u1")
    reset_limiters()
    assert rate_limit.turn_limiter._windows == {} and rate_limit.search_limiter._windows == {}


def test_the_admin_exemption_follows_the_setting():
    admin, user = {"id": "a", "role": "admin"}, {"id": "u", "role": "user"}
    with patch.object(config, "RATE_LIMIT_EXEMPT_ADMIN", True):
        assert is_exempt(admin) is True and is_exempt(user) is False
    with patch.object(config, "RATE_LIMIT_EXEMPT_ADMIN", False):
        assert is_exempt(admin) is False
    assert is_exempt(None) is False


@pytest.fixture
def search_env():
    with patch("backend.auth.rate_limit.db") as db, patch("backend.auth.rate_limit.log_event") as events:
        db.get_chat_owner.return_value = "u1"
        db.get_user.return_value = {"id": "u1", "role": "user"}
        yield db, events


def test_check_search_limit_allows_until_the_limit_then_returns_the_message(search_env):
    _, events = search_env
    with patch.object(rate_limit, "search_limiter", FixedWindowLimiter(2, 86400, clock=Clock())):
        assert check_search_limit("c1") is None
        assert check_search_limit("c1") is None
        assert check_search_limit("c1") == "Error: Daily web search limit reached."
    events.assert_called_once_with("rate_limited", {"kind": "searches"})


def test_check_search_limit_is_per_chat_owner(search_env):
    db, _ = search_env
    with patch.object(rate_limit, "search_limiter", FixedWindowLimiter(1, 86400, clock=Clock())):
        assert check_search_limit("c1") is None
        assert check_search_limit("c1") == "Error: Daily web search limit reached."
        db.get_chat_owner.return_value = "u2"
        db.get_user.return_value = {"id": "u2", "role": "user"}
        assert check_search_limit("c2") is None


def test_check_search_limit_fails_closed_without_an_owner_or_user(search_env):
    db, _ = search_env
    db.get_chat_owner.return_value = None
    assert check_search_limit("c1") == "Error: Daily web search limit reached."
    db.get_chat_owner.return_value = "ghost"
    db.get_user.return_value = None
    assert check_search_limit("c1") == "Error: Daily web search limit reached."


def test_the_exempt_admin_is_never_limited_by_searches(search_env):
    db, _ = search_env
    db.get_user.return_value = {"id": "u1", "role": "admin"}
    with patch.object(rate_limit, "search_limiter", FixedWindowLimiter(1, 86400, clock=Clock())), \
         patch.object(config, "RATE_LIMIT_EXEMPT_ADMIN", True):
        assert all(check_search_limit("c1") is None for _ in range(5))


def test_search_limit_reached_carries_the_message():
    assert str(SearchLimitReached("Error: Daily web search limit reached.")) == "Error: Daily web search limit reached."
