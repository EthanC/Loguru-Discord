"""Exercise real webhook execution in a process with a bounded lifetime."""

import logging
import sys
from typing import Any
from unittest.mock import patch

import httpx
from loguru import logger

from loguru_discord import DiscordSink
from loguru_discord._delivery import delivery_active


def run(enqueue: bool, failure: str, webhook_url: str) -> None:
    """Check delivery counts and guard cleanup for synchronous or queued logs."""
    requests: list[httpx.Request] = []
    guard_states: list[bool] = []
    client_type = httpx.Client
    emit = DiscordSink.emit

    def transport(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert len(requests) <= 2, "Transport logs triggered extra deliveries"
        if len(requests) == 1:
            if failure == "transport":
                raise httpx.ConnectError("Transport failure", request=request)
            if failure == "http":
                return httpx.Response(500)
        return httpx.Response(204)

    def client(**options: Any) -> httpx.Client:
        return client_type(transport=httpx.MockTransport(transport), **options)

    def checked_emit(sink: DiscordSink, record: logging.LogRecord) -> None:
        try:
            emit(sink, record)
        finally:
            guard_states.append(delivery_active.get())

    logger.remove()
    with (
        patch("clyde.webhook.httpx.Client", client),
        patch.object(DiscordSink, "emit", checked_emit),
    ):
        sink = DiscordSink(webhook_url, intercept=True)
        handler = logger.add(
            sink,
            enqueue=enqueue,
            catch=enqueue and failure != "none",
            format="{message}",
            backtrace=False,
            diagnose=False,
        )
        try:
            if failure != "none" and not enqueue:
                try:
                    logger.info("First application record")
                except (httpx.ConnectError, httpx.HTTPStatusError):
                    pass
                else:
                    raise AssertionError("Expected transport failure")
            else:
                logger.info("First application record")
            logger.complete()
            logging.info("Second application record")
            logger.complete()
            assert len(requests) == 2
            assert b"First application record" in requests[0].read()
            assert b"Second application record" in requests[1].read()
            assert guard_states == [False, False]
            assert not delivery_active.get()
        finally:
            logger.remove(handler)


if __name__ == "__main__":
    run(sys.argv[1] == "queued", sys.argv[2], sys.argv[3])
