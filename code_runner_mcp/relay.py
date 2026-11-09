"""TCP relay: forwards connections on 0.0.0.0:8100 to RELAY_TARGET (host:port).

Used so the app reaches the code runner without joining runner-net, where the
sandboxed user code runs. Forwards bytes only; it does not parse or log payloads.
Caps concurrent connections and aborts idle sessions; serves its own health answer on 127.0.0.1:8101.
"""
import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

LISTEN_PORT = 8100
HEALTH_PORT = 8101  # loopback only; the compose healthcheck uses it
CONNECT_TIMEOUT = 5
CLOSE_TIMEOUT = 5  # bound on flushing a session's last bytes to a peer that stopped reading
MAX_CONNECTIONS = 64  # over this, new clients are closed at once instead of queued
# Seconds with no bytes in either direction before a session is aborted. Must stay above the longest
# legitimate silence: the execution timeout (the code_runner_timeout setting, which nothing in this
# repo caps at this value, so a larger setting makes a silent run end here) and the 130 s install wait.
IDLE_TIMEOUT = 600

Handler = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]

logger = logging.getLogger(__name__)


def parse_target(value: str) -> tuple[str, int]:
    """Parse 'host:port' with 1 <= port <= 65535. Raises ValueError otherwise."""
    host, sep, port = value.rpartition(":")
    if not sep or not host or not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError(f"RELAY_TARGET must be 'host:port' with a port of 1-65535, got {value!r}")
    return host, int(port)


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
               abort_pair: tuple[asyncio.StreamWriter, ...], on_activity: Callable[[], None]) -> None:
    """Copy one direction, calling on_activity for every chunk read. On EOF, half-close the
    destination so replies still flow. On a transport error, abort both sides so neither hangs."""
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            on_activity()
            writer.write(data)
            await writer.drain()
        if writer.can_write_eof():
            writer.write_eof()
    except (ConnectionError, OSError) as exc:
        logger.warning("relay copy failed, aborting connection: %s", exc)
        for w in abort_pair:
            w.transport.abort()


async def _watch_idle(last_activity: list[float], idle_timeout: float,
                      pair: tuple[asyncio.StreamWriter, ...]) -> None:
    """Abort both sides of a session once nothing has moved for idle_timeout seconds."""
    loop = asyncio.get_running_loop()
    while True:
        remaining = last_activity[0] + idle_timeout - loop.time()
        if remaining <= 0:
            logger.warning("relay session idle for %ss, closing it", idle_timeout)
            for w in pair:
                w.transport.abort()
            return
        await asyncio.sleep(remaining)


def make_handler(target_host: str, target_port: int, max_connections: int = MAX_CONNECTIONS,
                 idle_timeout: float = IDLE_TIMEOUT) -> Handler:
    """Build the per-connection handler. Connections over max_connections are closed at once;
    a session with no traffic in either direction for idle_timeout seconds is aborted."""
    active = 0

    async def handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
        nonlocal active
        if active >= max_connections:
            logger.warning("relay connection limit (%s) reached, refusing a client", max_connections)
            client_writer.close()
            return
        active += 1
        upstream_writer = None
        watchdog = None
        tasks: list[asyncio.Future] = []
        try:
            try:
                upstream_reader, upstream_writer = await asyncio.wait_for(
                    asyncio.open_connection(target_host, target_port), timeout=CONNECT_TIMEOUT)
            except (OSError, asyncio.TimeoutError) as exc:
                logger.warning("relay target %s:%s unreachable: %s", target_host, target_port, exc)
                return
            pair = (client_writer, upstream_writer)
            loop = asyncio.get_running_loop()
            last_activity = [loop.time()]

            def on_activity() -> None:
                last_activity[0] = loop.time()

            watchdog = asyncio.ensure_future(_watch_idle(last_activity, idle_timeout, pair))
            to_target = asyncio.ensure_future(pipe(client_reader, upstream_writer, pair, on_activity))
            to_client = asyncio.ensure_future(pipe(upstream_reader, client_writer, pair, on_activity))
            tasks = [to_target, to_client]
            done, _ = await asyncio.wait({to_target, to_client}, return_when=asyncio.FIRST_COMPLETED)
            if to_client in done:
                # The target finished its reply. End the session even if the client keeps its write side open.
                to_target.cancel()
            results = await asyncio.gather(to_target, to_client, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                    logger.error("relay session error: %r", result)
        finally:
            try:
                for task in [watchdog, *tasks]:
                    if task is not None:
                        task.cancel()
                await asyncio.gather(*(t for t in [watchdog, *tasks] if t is not None), return_exceptions=True)
            finally:
                writers = [client_writer] + ([upstream_writer] if upstream_writer is not None else [])
                for writer in writers:
                    writer.close()
                for writer in writers:
                    try:
                        await asyncio.wait_for(writer.wait_closed(), CLOSE_TIMEOUT)
                    except asyncio.TimeoutError:
                        logger.warning("relay close timed out, aborting the connection")
                        writer.transport.abort()
                    except (ConnectionError, OSError) as exc:
                        logger.debug("relay close: %s", exc)
                # Released last, so a session still closing keeps counting against the cap.
                active -= 1
    return handle


async def handle_health(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Answer any request with 200 'ok' without touching the target: the relay's own liveness."""
    try:
        await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2)
    except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError, OSError):
        pass
    try:
        writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nok")
        await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        writer.close()


async def main() -> None:
    """Serve the relay on 0.0.0.0:8100 and its health answer on 127.0.0.1:8101 (loopback only)."""
    target_host, target_port = parse_target(os.environ["RELAY_TARGET"])
    server = await asyncio.start_server(make_handler(target_host, target_port), "0.0.0.0", LISTEN_PORT)
    health = await asyncio.start_server(handle_health, "127.0.0.1", HEALTH_PORT)
    async with server, health:
        await asyncio.gather(server.serve_forever(), health.serve_forever())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
