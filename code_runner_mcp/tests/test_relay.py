import asyncio
import socket

import pytest

import relay
from relay import handle_health, make_handler, parse_target


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_relay_round_trip_and_half_close():
    async def run():
        async def echo(reader, writer):
            # Read until EOF: the reply is only sent once the relay forwards the client's half-close.
            data = await reader.read()
            writer.write(data)
            await writer.drain()
            writer.close()

        echo_server = await asyncio.start_server(echo, "127.0.0.1", 0)
        echo_port = echo_server.sockets[0].getsockname()[1]
        relay_server = await asyncio.start_server(make_handler("127.0.0.1", echo_port), "127.0.0.1", 0)
        relay_port = relay_server.sockets[0].getsockname()[1]
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", relay_port)
            writer.write(b"ping")
            await writer.drain()
            writer.write_eof()
            reply = await asyncio.wait_for(reader.read(), 5)
            writer.close()
            return reply
        finally:
            relay_server.close()
            echo_server.close()
            await relay_server.wait_closed()
            await echo_server.wait_closed()

    assert asyncio.run(run()) == b"ping"


def test_relay_closes_client_when_target_is_down():
    async def run():
        relay_server = await asyncio.start_server(make_handler("127.0.0.1", _free_port()), "127.0.0.1", 0)
        relay_port = relay_server.sockets[0].getsockname()[1]
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", relay_port)
            data = await asyncio.wait_for(reader.read(100), 5)
            writer.close()
            return data
        finally:
            relay_server.close()
            await relay_server.wait_closed()

    assert asyncio.run(run()) == b""


def test_relay_does_not_hang_when_target_aborts_mid_stream():
    # Checks liveness only: the client's stream ends (EOF or reset) within the timeout.
    # Whether the client sees EOF or a reset depends on timing, so the outcome is not asserted.
    async def run():
        async def abort_after_partial(reader, writer):
            await reader.read(100)
            writer.write(b"partial")
            await writer.drain()
            writer.transport.abort()

        target = await asyncio.start_server(abort_after_partial, "127.0.0.1", 0)
        target_port = target.sockets[0].getsockname()[1]
        relay_server = await asyncio.start_server(make_handler("127.0.0.1", target_port), "127.0.0.1", 0)
        relay_port = relay_server.sockets[0].getsockname()[1]
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", relay_port)
            writer.write(b"go")
            await writer.drain()
            # The client must see the end of the stream (EOF or reset), not hang.
            try:
                tail = await asyncio.wait_for(reader.read(), 5)
            except ConnectionResetError:
                tail = None
            writer.close()
            return tail
        finally:
            relay_server.close()
            target.close()
            await relay_server.wait_closed()
            await target.wait_closed()

    result = asyncio.run(run())
    assert result in (None, b"partial")


@pytest.mark.parametrize("value, expected", [("code_runner_runtime:8100", ("code_runner_runtime", 8100)),
                                             ("127.0.0.1:9", ("127.0.0.1", 9))])
def test_parse_target_accepts_host_and_port(value, expected):
    assert parse_target(value) == expected


@pytest.mark.parametrize("value", ["", "no-port", ":8100", "host:", "host:abc", "host:0", "host:70000"])
def test_parse_target_rejects_malformed_values(value):
    with pytest.raises(ValueError):
        parse_target(value)


def test_relay_ends_session_when_target_replies_and_client_keeps_write_side_open():
    async def run():
        async def reply_then_close(reader, writer):
            await reader.read(100)
            writer.write(b"done")
            await writer.drain()
            writer.close()

        target = await asyncio.start_server(reply_then_close, "127.0.0.1", 0)
        target_port = target.sockets[0].getsockname()[1]
        relay_server = await asyncio.start_server(make_handler("127.0.0.1", target_port), "127.0.0.1", 0)
        relay_port = relay_server.sockets[0].getsockname()[1]
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", relay_port)
            writer.write(b"go")
            await writer.drain()
            # No write_eof(): the relay must still end the session once the target has replied.
            reply = await asyncio.wait_for(reader.read(), 5)
            writer.close()
            return reply
        finally:
            relay_server.close()
            target.close()
            await relay_server.wait_closed()
            await target.wait_closed()

    assert asyncio.run(run()) == b"done"


def test_main_listens_on_8100_and_serves_health_on_loopback(monkeypatch):
    calls = []

    class _Server:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def serve_forever(self):
            raise RuntimeError("stop after setup")

    async def fake_start_server(handler, host, port):
        calls.append((host, port, handler))
        return _Server()

    monkeypatch.setenv("RELAY_TARGET", "code_runner_runtime:8100")
    monkeypatch.setattr(relay.asyncio, "start_server", fake_start_server)
    with pytest.raises(RuntimeError, match="stop after setup"):
        asyncio.run(relay.main())
    assert [(host, port) for host, port, _ in calls] == [("0.0.0.0", 8100), ("127.0.0.1", 8101)]
    assert calls[0][2] is not handle_health and callable(calls[0][2])
    assert calls[1][2] is handle_health


async def _echo_forever(reader, writer):
    try:
        while data := await reader.read(1024):
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()


async def _start(handler):
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


async def _stop(*servers):
    for server in servers:
        server.close()
    for server in servers:
        await server.wait_closed()


async def _served_eventually(port, tries=40) -> bool:
    """True once a new client gets its echo (a slot has been freed); polls instead of sleeping once."""
    for _ in range(tries):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"new")
        await writer.drain()
        try:
            if await asyncio.wait_for(reader.readexactly(3), 0.5) == b"new":
                writer.close()
                return True
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError):
            pass
        writer.close()
        await asyncio.sleep(0.05)
    return False


async def _is_closed(reader, timeout=2.0) -> bool:
    try:
        return await asyncio.wait_for(reader.read(10), timeout) == b""
    except ConnectionError:
        return True


def test_relay_refuses_clients_over_the_cap_and_frees_the_slot():
    async def run():
        echo, echo_port = await _start(_echo_forever)
        relay_server, port = await _start(make_handler("127.0.0.1", echo_port, max_connections=1))
        try:
            r1, w1 = await asyncio.open_connection("127.0.0.1", port)
            w1.write(b"one")
            await w1.drain()
            assert await asyncio.wait_for(r1.readexactly(3), 2) == b"one"
            r2, w2 = await asyncio.open_connection("127.0.0.1", port)
            over_cap_closed = await _is_closed(r2)
            w2.close()
            # The first session still works.
            w1.write(b"two")
            await w1.drain()
            first_still_works = await asyncio.wait_for(r1.readexactly(3), 2) == b"two"
            w1.close()
            await w1.wait_closed()
            freed = await _served_eventually(port)
            return over_cap_closed, first_still_works, freed
        finally:
            await _stop(relay_server, echo)

    assert asyncio.run(run()) == (True, True, True)


def test_relay_frees_the_slot_when_the_target_is_unreachable():
    async def run():
        target_port = _free_port()
        relay_server, port = await _start(make_handler("127.0.0.1", target_port, max_connections=1))
        echo = None
        try:
            r1, w1 = await asyncio.open_connection("127.0.0.1", port)
            first_closed = await _is_closed(r1)
            w1.close()
            echo = await asyncio.start_server(_echo_forever, "127.0.0.1", target_port)
            return first_closed, await _served_eventually(port)
        finally:
            await _stop(*(s for s in (relay_server, echo) if s is not None))

    assert asyncio.run(run()) == (True, True)


def test_relay_closes_an_idle_session():
    async def run():
        echo, echo_port = await _start(_echo_forever)
        relay_server, port = await _start(make_handler("127.0.0.1", echo_port, idle_timeout=0.3))
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            started = asyncio.get_running_loop().time()
            closed = await _is_closed(reader, timeout=3)
            elapsed = asyncio.get_running_loop().time() - started
            writer.close()
            return closed, elapsed
        finally:
            await _stop(relay_server, echo)

    closed, elapsed = asyncio.run(run())
    assert closed and elapsed < 2


def test_relay_keeps_a_session_with_steady_traffic():
    async def run():
        echo, echo_port = await _start(_echo_forever)
        relay_server, port = await _start(make_handler("127.0.0.1", echo_port, idle_timeout=1.0))
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            for _ in range(6):  # 6 x 0.25 s is longer than the idle timeout, but never idle for 1.0 s
                await asyncio.sleep(0.25)
                writer.write(b"x")
                await writer.drain()
                assert await asyncio.wait_for(reader.readexactly(1), 1) == b"x"
            writer.close()
        finally:
            await _stop(relay_server, echo)

    asyncio.run(run())


def test_health_answers_200_without_a_target():
    async def run():
        server, port = await _start(handle_health)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            data = await asyncio.wait_for(reader.read(), 2)
            writer.close()
            return data
        finally:
            await _stop(server)

    data = asyncio.run(run())
    assert data.startswith(b"HTTP/1.0 200 OK") and data.endswith(b"ok")


def test_relay_frees_the_slot_of_an_idle_session_it_aborted():
    async def run():
        echo, echo_port = await _start(_echo_forever)
        relay_server, port = await _start(make_handler("127.0.0.1", echo_port, max_connections=1, idle_timeout=0.3))
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            aborted = await _is_closed(reader, timeout=3)
            writer.close()
            return aborted, await _served_eventually(port)
        finally:
            await _stop(relay_server, echo)

    assert asyncio.run(run()) == (True, True)
