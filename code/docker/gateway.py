#!/usr/bin/env python3
"""Dumb TCP forwarder -- the ONLY container attached to the outside (edge) network.

The LLM servers and the harness live on an internal-only Docker network (no egress,
no published ports).  This process publishes their ports on the host by piping raw
bytes, so HTTP streaming (SSE) and keep-alive work unchanged.  It never parses or
logs request bodies and connects only to the upstreams listed in GATEWAY_ROUTES.

GATEWAY_ROUTES="18000=harness:18000;18080=llm-base:8080|llm:8080"
  <listen_port>=<host:port>[|<fallback host:port>...]   (routes separated by ';' or ',')
The first upstream that accepts the TCP connection wins, so the raw port serves the
untouched base model when the 'base' profile is up and the trained model otherwise.

Stdlib only.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

log = logging.getLogger("gateway")
CONNECT_TIMEOUT = float(os.environ.get("GATEWAY_CONNECT_TIMEOUT", "5"))
BUF = 1 << 16


def parse_routes(spec: str) -> dict[int, list[tuple[str, int]]]:
    routes: dict[int, list[tuple[str, int]]] = {}
    for part in spec.replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        port, targets = part.split("=", 1)
        ups = []
        for t in targets.split("|"):
            host, p = t.strip().rsplit(":", 1)
            ups.append((host, int(p)))
        routes[int(port)] = ups
    if not routes:
        raise SystemExit("GATEWAY_ROUTES is empty")
    return routes


async def _pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await src.read(BUF)
            if not data:
                break
            dst.write(data)
            await dst.drain()
        if dst.can_write_eof():
            dst.write_eof()
    except (ConnectionError, OSError, asyncio.CancelledError):
        pass


async def _open_upstream(ups: list[tuple[str, int]]):
    last: Exception | None = None
    for host, port in ups:
        try:
            r, w = await asyncio.wait_for(asyncio.open_connection(host, port), CONNECT_TIMEOUT)
            return (host, port), r, w
        except Exception as e:  # noqa: BLE001 - try the next fallback
            last = e
    raise ConnectionError(f"no upstream reachable in {ups}: {last!r}")


def make_handler(listen_port: int, ups: list[tuple[str, int]]):
    async def handle(cr: asyncio.StreamReader, cw: asyncio.StreamWriter) -> None:
        peer = cw.get_extra_info("peername")
        try:
            (host, port), ur, uw = await _open_upstream(ups)
        except ConnectionError as e:
            log.warning(":%d %s -> %s", listen_port, peer, e)
            cw.close()
            return
        log.info(":%d %s -> %s:%d", listen_port, peer, host, port)
        try:
            await asyncio.gather(_pipe(cr, uw), _pipe(ur, cw))
        finally:
            for w in (uw, cw):
                try:
                    w.close()
                except Exception:  # noqa: BLE001
                    pass

    return handle


async def main() -> None:
    routes = parse_routes(os.environ.get("GATEWAY_ROUTES", "18000=harness:18000"))
    bind = os.environ.get("GATEWAY_BIND", "0.0.0.0")
    servers = []
    for port, ups in routes.items():
        srv = await asyncio.start_server(make_handler(port, ups), bind, port, reuse_address=True)
        servers.append(srv)
        log.info("listening %s:%d -> %s", bind, port, " | ".join(f"{h}:{p}" for h, p in ups))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()
    for s in servers:
        s.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("GATEWAY_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    asyncio.run(main())
