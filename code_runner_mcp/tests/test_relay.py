import asyncio
import socket

import pytest

from relay import make_handler, parse_target


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


def test_relay_ends_client_when_target_aborts_mid_stream():
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


@pytest.mark.parametrize("value", ["", "no-port", ":8100", "host:", "host:abc"])
def test_parse_target_rejects_malformed_values(value):
    with pytest.raises(ValueError):
        parse_target(value)
