"""TCP relay: forwards connections on 0.0.0.0:8100 to RELAY_TARGET (host:port).

Used so the app reaches the code runner without joining runner-net, where the
sandboxed user code runs. Forwards bytes only; it does not parse or log payloads.
"""
import asyncio
import logging
import os

LISTEN_PORT = 8100

logger = logging.getLogger(__name__)


def parse_target(value: str) -> tuple[str, int]:
    """Parse 'host:port'. Raises ValueError on a missing or malformed value."""
    host, sep, port = value.rpartition(":")
    if not sep or not host or not port.isdigit():
        raise ValueError(f"RELAY_TARGET must be 'host:port', got {value!r}")
    return host, int(port)


async def pipe(reader, writer, abort_pair):
    """Copy one direction. On EOF, half-close the destination so replies still flow.
    On a transport error, abort both sides so neither hangs."""
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
        if writer.can_write_eof():
            writer.write_eof()
    except (ConnectionError, OSError) as exc:
        logger.warning("relay copy failed, aborting connection: %s", exc)
        for w in abort_pair:
            w.transport.abort()


def make_handler(target_host, target_port):
    async def handle(client_reader, client_writer):
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(target_host, target_port)
        except OSError as exc:
            logger.warning("relay target %s:%s unreachable: %s", target_host, target_port, exc)
            client_writer.close()
            return
        pair = (client_writer, upstream_writer)
        try:
            await asyncio.gather(
                pipe(client_reader, upstream_writer, pair),
                pipe(upstream_reader, client_writer, pair),
            )
        finally:
            for writer in pair:
                writer.close()
            for writer in pair:
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError) as exc:
                    logger.debug("relay close: %s", exc)
    return handle


async def main():
    target_host, target_port = parse_target(os.environ["RELAY_TARGET"])
    server = await asyncio.start_server(make_handler(target_host, target_port), "0.0.0.0", LISTEN_PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
