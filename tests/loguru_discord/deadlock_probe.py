"""Reproduce lock inversion with synchronized producers and a real queue pipe."""

import asyncio
import logging
import sys
from threading import Event, Thread
from typing import Any
from unittest.mock import patch

from loguru import logger
from niquests import PreparedRequest, Response, Session

from loguru_discord import AsyncDiscordSink, DiscordSink, Intercept


def run(queued: bool, webhook_url: str) -> None:
    """Deliver transport logs while a standard-library producer holds its lock."""
    delivering = Event()
    intercepted = Event()
    requests = []
    original_emit = Intercept.emit

    def emit(handler: Intercept, record: logging.LogRecord) -> None:
        if record.name == "application":
            intercepted.set()
        original_emit(handler, record)

    def transport(
        session: Session, request: PreparedRequest, **options: Any
    ) -> Response:
        requests.append(request)
        if len(requests) == 1:
            delivering.set()
            assert intercepted.wait(5)
            logging.getLogger("transport").debug("Transport-generated log")
        response = Response()
        response.status_code = 204
        response._content = b""
        response.request = request
        response.url = request.url
        return response

    logger.remove()
    with (
        patch.object(Intercept, "emit", emit),
        patch("clyde.webhook.Session.send", transport),
    ):
        sink = DiscordSink(webhook_url, intercept=True)
        handler = logger.add(sink, enqueue=queued, catch=False, format="{message}")
        first = Thread(target=logger.info, args=("First record",), daemon=True)
        first.start()
        assert delivering.wait(5)
        # A 2 MiB record cannot fit in the SimpleQueue pipe while its only
        # reader is inside transport. put() holds Loguru's and Intercept's locks.
        text = "x" * (2 * 1024 * 1024) if queued else "Concurrent record"
        second = Thread(
            target=logging.getLogger("application").info, args=(text,), daemon=True
        )
        second.start()
        first.join(5)
        second.join(5)
        assert not first.is_alive() and not second.is_alive(), "Lock-order deadlock"
        logger.complete()
        logger.remove(handler)
        assert len(requests) == 2


async def run_eager(webhook_url: str) -> None:
    """Check that an eager task factory cannot reenter the admission lock."""
    asyncio.get_running_loop().set_task_factory(getattr(asyncio, "eager_task_factory"))
    sent = []

    async def execute(webhook: Any, **options: Any) -> None:
        sent.append(webhook.content)

    logger.remove()
    with patch("clyde.webhook.Webhook.execute_async", execute):
        async with AsyncDiscordSink(webhook_url) as sink:
            handler = logger.add(sink, catch=False, enqueue=False, format="{message}")
            logger.info("Eager record")
            await logger.complete()
            logger.remove(handler)
            assert sink.statistics.sent == 1
            assert len(sent) == 1


if __name__ == "__main__":
    if sys.argv[1] == "eager":
        asyncio.run(run_eager(sys.argv[2]))
    else:
        run(sys.argv[1] == "queued", sys.argv[2])
