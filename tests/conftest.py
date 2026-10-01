import inspect
import logging
from collections.abc import Callable, Iterator
from copy import deepcopy
from typing import Any

import pytest
from clyde import Webhook
from loguru import logger
from niquests import Response

WEBHOOK_URL = "https://discord.com/api/webhooks/00000000/test-token"


@pytest.fixture
def webhook_url() -> str:
    return WEBHOOK_URL


@pytest.fixture
def deliveries(monkeypatch: pytest.MonkeyPatch) -> list[Webhook]:
    payloads: list[Webhook] = []

    def execute(webhook: Webhook, **options: Any) -> Response:
        payload = deepcopy(webhook)
        payload._validate()
        payloads.append(payload)
        response = Response()
        response.status_code = 204
        return response

    monkeypatch.setattr(Webhook, "execute", execute)
    return payloads


@pytest.fixture
def add_sink() -> Iterator[Callable[..., int]]:
    handler_ids: list[int] = []
    async_handler_ids: list[int] = []

    def add(sink: Any, **options: Any) -> int:
        options = {
            "catch": False,
            "backtrace": False,
            "diagnose": False,
            "format": "{message}",
            **options,
        }
        handler_id = logger.add(sink, **options)
        if inspect.iscoroutinefunction(getattr(sink, "complete", None)):
            async_handler_ids.append(handler_id)
        else:
            handler_ids.append(handler_id)
        return handler_id

    yield add

    for handler_id in async_handler_ids:
        logger.remove(handler_id)
    logger.complete()
    for handler_id in handler_ids:
        logger.remove(handler_id)


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers = root.handlers[:]
    filters = root.filters[:]
    level = root.level
    disabled = root.disabled
    yield
    root.handlers = handlers
    root.filters = filters
    root.setLevel(level)
    root.disabled = disabled
