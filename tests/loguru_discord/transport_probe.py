"""Exercise real webhook execution in a process with a bounded lifetime."""

import logging
import sys
from typing import Any
from unittest.mock import patch

from loguru import logger
from niquests import ConnectionError, HTTPError, PreparedRequest, Response, Session

from loguru_discord import DiscordSink
from loguru_discord._delivery import delivery_active


def run(enqueue: bool, failure: str, webhook_url: str) -> None:
    """Check delivery counts and guard cleanup for synchronous or queued logs."""
    requests: list[PreparedRequest] = []
    guard_states: list[bool] = []
    emit = DiscordSink.emit

    def transport(
        session: Session, request: PreparedRequest, **options: Any
    ) -> Response:
        requests.append(request)
        assert len(requests) <= 2, "Transport logs triggered extra deliveries"
        logging.getLogger("urllib3.connectionpool").debug("Sending webhook request")
        response = Response()
        response.status_code = 204
        response._content = b""
        response.request = request
        response.url = request.url
        if len(requests) == 1:
            if failure == "transport":
                raise ConnectionError("Transport failure", request=request)
            if failure == "http":
                response.status_code = 500
        return response

    def checked_emit(sink: DiscordSink, record: logging.LogRecord) -> None:
        try:
            emit(sink, record)
        finally:
            guard_states.append(delivery_active.get())

    logger.remove()
    with (
        patch("clyde.webhook.Session.send", transport),
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
                except (ConnectionError, HTTPError):
                    pass
                else:
                    raise AssertionError("Expected transport failure")
            else:
                logger.info("First application record")
            logger.complete()
            logging.info("Second application record")
            logger.complete()
            assert len(requests) == 2
            assert isinstance(requests[0].body, bytes)
            assert b"First application record" in requests[0].body
            assert isinstance(requests[1].body, bytes)
            assert b"Second application record" in requests[1].body
            assert guard_states == [False, False]
            assert not delivery_active.get()
        finally:
            logger.remove(handler)


if __name__ == "__main__":
    run(sys.argv[1] == "queued", sys.argv[2], sys.argv[3])
