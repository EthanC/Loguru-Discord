import logging
from collections.abc import Callable, Iterator
from copy import deepcopy
from typing import Any

import httpx
import pytest
from clyde import Webhook
from loguru import logger

WEBHOOK_URL = "https://discord.com/api/webhooks/00000000/test-token"


@pytest.fixture
def webhook_url() -> str:
    return WEBHOOK_URL


@pytest.fixture
def deliveries(monkeypatch: pytest.MonkeyPatch) -> list[Webhook]:
    payloads: list[Webhook] = []

    def execute(webhook: Webhook) -> httpx.Response:
        payload = deepcopy(webhook)
        payload._validate()
        payloads.append(payload)
        return httpx.Response(204, request=httpx.Request("POST", webhook.url))

    monkeypatch.setattr(Webhook, "execute", execute)
    return payloads


@pytest.fixture
def add_sink() -> Iterator[Callable[..., int]]:
    handler_ids: list[int] = []

    def add(sink: Any, **options: Any) -> int:
        options = {
            "catch": False,
            "backtrace": False,
            "diagnose": False,
            "format": "{message}",
            **options,
        }
        handler_id = logger.add(sink, **options)
        handler_ids.append(handler_id)
        return handler_id

    yield add

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
