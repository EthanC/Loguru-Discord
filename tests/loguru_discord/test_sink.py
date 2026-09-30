import logging
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from clyde import Markdown, Timestamp, Webhook
from clyde.components import Container, Seperator, TextDisplay
from clyde.webhook import AllowedMentions, MessageFlags
from loguru import logger
from msgspec import UNSET
from niquests import PreparedRequest, Response, Session

from loguru_discord import DiscordSink
from loguru_discord._delivery import delivery_active

TEST_MESSAGE = "An application log record"
AVATAR_URL = "https://example.com/avatar.png"


@pytest.mark.parametrize("rich", [False, True])
def test_emit(
    rich: bool,
    webhook_url: str,
    deliveries: list[Webhook],
    add_sink: Callable[..., int],
) -> None:
    add_sink(
        DiscordSink(
            webhook_url, username="Custom Username", avatar_url=AVATAR_URL, rich=rich
        )
    )

    logger.info(TEST_MESSAGE)

    assert len(deliveries) == 1
    payload = deliveries[0]
    assert payload.url == webhook_url
    assert payload.username == "Custom Username"
    assert payload.avatar_url == AVATAR_URL
    assert payload._attachments == []
    if rich:
        assert isinstance(payload.components, list)
        assert len(payload.components) == 1
        container = payload.components[0]
        assert isinstance(container, Container)
        assert isinstance(container.components[1], TextDisplay)
        assert container.components[1].content == Markdown.code_block(TEST_MESSAGE)
        assert payload.get_flag(MessageFlags.IS_COMPONENTS_V2)
        assert payload.content is UNSET
    else:
        assert payload.content == Markdown.code_block(TEST_MESSAGE)
        assert payload.components is UNSET
        assert not payload.get_flag(MessageFlags.IS_COMPONENTS_V2)


@pytest.mark.parametrize(
    ("level", "color"),
    [
        ("CRITICAL", 0x000000),
        ("ERROR", 0xD22D39),
        ("WARNING", 0xCE9C5C),
        ("SUCCESS", 0x43A25A),
        ("INFO", 0xFFFFFF),
        ("DEBUG", 0x5865F2),
        ("TRACE", UNSET),
    ],
)
def test_rich_formatting(
    level: str,
    color: object,
    webhook_url: str,
    deliveries: list[Webhook],
    add_sink: Callable[..., int],
) -> None:
    add_sink(DiscordSink(webhook_url, rich=True), level="TRACE")

    logger.log(level, TEST_MESSAGE)

    assert len(deliveries) == 1
    payload = deliveries[0]
    assert isinstance(payload.components, list)
    container = payload.components[0]
    assert isinstance(container, Container)
    assert container.accent_color == color
    assert len(container.components) == 4
    heading, body, separator, timestamp = container.components
    assert isinstance(heading, TextDisplay)
    assert heading.content == f"### {level}"
    assert isinstance(body, TextDisplay)
    assert body.content == Markdown.code_block(TEST_MESSAGE)
    assert isinstance(separator, Seperator)
    assert separator.divider
    assert isinstance(timestamp, TextDisplay)
    assert timestamp.content.startswith("-# <t:")
    assert ":F> (<t:" in timestamp.content
    assert timestamp.content.endswith(":R>)")


@pytest.mark.parametrize("rich", [False, True])
def test_emit_exception(
    rich: bool,
    webhook_url: str,
    deliveries: list[Webhook],
    add_sink: Callable[..., int],
) -> None:
    add_sink(DiscordSink(webhook_url, rich=rich))

    try:
        raise ValueError("Invalid application value")
    except ValueError:
        logger.exception(TEST_MESSAGE)

    assert len(deliveries) == 1
    payload = deliveries[0]
    body = payload.content
    if rich:
        assert isinstance(payload.components, list)
        container = payload.components[0]
        assert isinstance(container, Container)
        text = container.components[1]
        assert isinstance(text, TextDisplay)
        body = text.content
    assert isinstance(body, str)
    assert TEST_MESSAGE in body
    assert "Traceback (most recent call last):" in body
    assert "ValueError: Invalid application value" in body


def test_emit_long(
    webhook_url: str, deliveries: list[Webhook], add_sink: Callable[..., int]
) -> None:
    add_sink(DiscordSink(webhook_url))
    message = TEST_MESSAGE * 100

    logger.error(message)

    assert len(deliveries) == 1
    payload = deliveries[0]
    assert payload.content is UNSET
    assert len(payload._attachments) == 1
    attachment = payload._attachments[0]
    assert attachment.filename == "message.txt"
    assert attachment.content == message.encode()


@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("character", ["x", "é", "🚀"])
def test_plain_text_budget(
    offset: int,
    character: str,
    webhook_url: str,
    deliveries: list[Webhook],
    add_sink: Callable[..., int],
) -> None:
    message = character * (2000 - len("```\n\n```") + offset)
    add_sink(DiscordSink(webhook_url))

    logger.info(message)

    assert len(deliveries) == 1
    payload = deliveries[0]
    assert payload.components is UNSET
    assert not payload.get_flag(MessageFlags.IS_COMPONENTS_V2)
    if offset <= 0:
        assert payload.content == Markdown.code_block(message)
        assert len(payload.content) == 2000 + offset
        assert payload._attachments == []
    else:
        assert payload.content is UNSET
        assert len(payload._attachments) == 1
        attachment = payload._attachments[0]
        assert attachment.filename == "message.txt"
        assert attachment.content == message.encode()


@pytest.mark.parametrize("rich", [False, True])
def test_emit_suppressed(
    rich: bool,
    webhook_url: str,
    deliveries: list[Webhook],
    add_sink: Callable[..., int],
) -> None:
    add_sink(DiscordSink(webhook_url, rich=rich, suppress=[ZeroDivisionError]))

    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Suppressed record")

    assert deliveries == []


def test_emit_unsuppressed(
    webhook_url: str, deliveries: list[Webhook], add_sink: Callable[..., int]
) -> None:
    add_sink(DiscordSink(webhook_url, suppress=[ZeroDivisionError]))

    try:
        raise ValueError(TEST_MESSAGE)
    except ValueError:
        logger.exception("Unsuppressed record")

    assert len(deliveries) == 1
    assert isinstance(deliveries[0].content, str)
    assert TEST_MESSAGE in deliveries[0].content


def test_emit_intercept(
    webhook_url: str, deliveries: list[Webhook], add_sink: Callable[..., int]
) -> None:
    add_sink(DiscordSink(webhook_url, intercept=True))

    logging.error(TEST_MESSAGE)

    assert len(deliveries) == 1
    assert deliveries[0].content == Markdown.code_block(TEST_MESSAGE)


def test_execution_failure_propagates(
    webhook_url: str, add_sink: Callable[..., int], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(webhook: Webhook) -> None:
        raise RuntimeError("Webhook execution failed")

    monkeypatch.setattr(Webhook, "execute", fail)
    add_sink(DiscordSink(webhook_url))

    with pytest.raises(RuntimeError, match="Webhook execution failed"):
        logger.info(TEST_MESSAGE)


@pytest.mark.parametrize("already_active", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_delivery_restores_previous_context(
    already_active: bool,
    failure: bool,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard_states: list[bool] = []

    def execute(webhook: Webhook) -> None:
        guard_states.append(delivery_active.get())
        if failure:
            raise RuntimeError("Webhook execution failed")

    monkeypatch.setattr(Webhook, "execute", execute)
    sink = DiscordSink(webhook_url)
    record = logging.LogRecord(
        __name__, logging.INFO, __file__, 1, TEST_MESSAGE, (), None
    )
    token = delivery_active.set(already_active)
    try:
        if failure:
            with pytest.raises(RuntimeError, match="Webhook execution failed"):
                sink.emit(record)
        else:
            sink.emit(record)

        assert guard_states == [True]
        assert delivery_active.get() is already_active
    finally:
        delivery_active.reset(token)


def test_rich_records_have_independent_payloads(
    webhook_url: str, deliveries: list[Webhook], add_sink: Callable[..., int]
) -> None:
    sink = DiscordSink(webhook_url, rich=True)
    add_sink(sink)
    messages = [f"Record {index}" for index in range(10)]

    for message in messages:
        logger.info(message)

    assert len(deliveries) == len(messages)
    for payload, message in zip(deliveries, messages):
        assert isinstance(payload.components, list)
        assert len(payload.components) == 1
        container = payload.components[0]
        assert isinstance(container, Container)
        body = container.components[1]
        assert isinstance(body, TextDisplay)
        assert body.content == Markdown.code_block(message)
        assert payload._attachments == []
    assert sink.webhook.components is UNSET
    assert sink.webhook.flags is UNSET
    assert sink.webhook._query_params == {}


def test_plain_short_long_short_payloads(
    webhook_url: str, deliveries: list[Webhook], add_sink: Callable[..., int]
) -> None:
    sink = DiscordSink(webhook_url)
    add_sink(sink)
    messages = ["First short record", "Long record " * 250, "Last short record"]

    for message in messages:
        logger.info(message)

    assert len(deliveries) == 3
    first, long, last = deliveries
    assert first.content == Markdown.code_block(messages[0])
    assert first._attachments == []
    assert long.content is UNSET
    assert len(long._attachments) == 1
    assert long._attachments[0].content == messages[1].encode()
    assert last.content == Markdown.code_block(messages[2])
    assert last._attachments == []
    assert sink.webhook.content is UNSET
    assert sink.webhook._attachments == []


@pytest.mark.parametrize("rich", [False, True])
def test_payload_preserves_webhook_configuration(
    rich: bool,
    webhook_url: str,
    deliveries: list[Webhook],
    add_sink: Callable[..., int],
) -> None:
    sink = DiscordSink(
        webhook_url, username="Custom Username", avatar_url=AVATAR_URL, rich=rich
    )
    sink.webhook.set_allowed_mentions(AllowedMentions(parse=[], users=["123"]))
    sink.webhook.set_flag(MessageFlags.SUPPRESS_NOTIFICATIONS, True)
    sink.webhook.set_wait(True).set_thread_id("456")
    template = deepcopy(sink.webhook)
    add_sink(sink)

    for _ in range(3):
        logger.info(TEST_MESSAGE)

    assert len(deliveries) == 3
    for payload in deliveries:
        assert payload.username == template.username
        assert payload.avatar_url == template.avatar_url
        assert payload.allowed_mentions == template.allowed_mentions
        assert payload.allowed_mentions is not sink.webhook.allowed_mentions
        assert payload.get_flag(MessageFlags.SUPPRESS_NOTIFICATIONS)
        assert payload._query_params["wait"] == "True"
        assert payload._query_params["thread_id"] == "456"
        assert payload.get_flag(MessageFlags.IS_COMPONENTS_V2) is rich
    assert sink.webhook == template


@pytest.mark.parametrize("rich", [False, True])
@pytest.mark.parametrize("thread_id", [None, "987654321098765432"])
@pytest.mark.parametrize(
    "query",
    [
        "",
        "wait=true",
        "thread_id=123456789012345678",
        "wait=true&thread_id=123456789012345678",
        "thread_id=123456789012345678&wait=true",
        "thread_id=123456789012345678&wait=true&with_components=true",
    ],
)
def test_emit_preserves_thread_id(
    rich: bool,
    thread_id: str | None,
    query: str,
    webhook_url: str,
    add_sink: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[PreparedRequest] = []

    def transport(
        session: Session, request: PreparedRequest, **options: Any
    ) -> Response:
        requests.append(request)
        response = Response()
        response.status_code = 204
        response._content = b""
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr("clyde.webhook.Session.send", transport)
    url = f"{webhook_url}?{query}" if query else webhook_url
    sink = DiscordSink(url, thread_id=thread_id, rich=rich)
    add_sink(sink)
    messages = ["First short record", "x" * 5000, "Last short record"]

    for message in messages:
        logger.info(message)

    assert len(requests) == len(messages)
    for index, request in enumerate(requests):
        assert request.method == "POST"
        assert isinstance(request.url, str)
        assert request.url.split("?")[0] == webhook_url
        expected_params = parse_qs(query)
        if thread_id is not None:
            expected_params["thread_id"] = [thread_id]
        if rich:
            if index == 1:
                expected_params.pop("with_components", None)
            else:
                expected_params["with_components"] = ["True"]
        assert parse_qs(urlsplit(request.url).query) == expected_params
        assert request.headers is not None
        content_type = request.headers["Content-Type"]
        assert isinstance(content_type, str)
        expected_content_type = (
            "multipart/form-data" if index == 1 else "application/json"
        )
        assert content_type.split(";")[0] == expected_content_type
    assert sink.thread_id == thread_id
    assert sink.webhook.url == url


@pytest.mark.parametrize("level", ["INFO", "CRITICAL"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("character", ["x", "é", "🚀"])
def test_rich_text_budget(
    level: str,
    offset: int,
    character: str,
    webhook_url: str,
    deliveries: list[Webhook],
    add_sink: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "loguru_discord.sink.datetime", Mock(now=Mock(return_value=timestamp))
    )
    heading = f"### {level}"
    footer = f"-# {Timestamp.long_date_time(timestamp)} ({Timestamp.relative_time(timestamp)})"
    budget = 4000 - len(heading) - len(footer) - len("```\n\n```")
    message = character * (budget + offset)
    add_sink(DiscordSink(webhook_url, rich=True))

    logger.log(level, message)

    assert len(deliveries) == 1
    payload = deliveries[0]
    if offset <= 0:
        assert isinstance(payload.components, list)
        container = payload.components[0]
        assert isinstance(container, Container)
        text = [
            component.content
            for component in container.components
            if isinstance(component, TextDisplay)
        ]
        assert text == [heading, Markdown.code_block(message), footer]
        assert sum(map(len, text)) == 4000 + offset
        assert payload.get_flag(MessageFlags.IS_COMPONENTS_V2)
        assert payload._attachments == []
    else:
        assert payload.components is UNSET
        assert payload.content is UNSET
        assert not payload.get_flag(MessageFlags.IS_COMPONENTS_V2)
        assert "with_components" not in payload._query_params
        assert len(payload._attachments) == 1
        assert payload._attachments[0].filename == "message.txt"
        assert payload._attachments[0].content == message.encode()


def test_rich_short_oversized_short_payloads(
    webhook_url: str, deliveries: list[Webhook], add_sink: Callable[..., int]
) -> None:
    sink = DiscordSink(
        webhook_url, username="Custom Username", avatar_url=AVATAR_URL, rich=True
    )
    sink.webhook.set_flag(MessageFlags.SUPPRESS_NOTIFICATIONS, True)
    sink.webhook.set_wait(True).set_thread_id("456")
    add_sink(sink)
    messages = ["First short record", "Oversized 🚀 record " * 300, "Last short record"]

    for message in messages:
        logger.info(message)

    assert len(deliveries) == 3
    first, oversized, last = deliveries
    for payload, message in [(first, messages[0]), (last, messages[2])]:
        assert isinstance(payload.components, list)
        assert len(payload.components) == 1
        container = payload.components[0]
        assert isinstance(container, Container)
        body = container.components[1]
        assert isinstance(body, TextDisplay)
        assert body.content == Markdown.code_block(message)
        assert payload.get_flag(MessageFlags.IS_COMPONENTS_V2)
        assert payload._attachments == []
    assert oversized.components is UNSET
    assert oversized.content is UNSET
    assert not oversized.get_flag(MessageFlags.IS_COMPONENTS_V2)
    assert len(oversized._attachments) == 1
    assert oversized._attachments[0].content == messages[1].encode()
    for payload in deliveries:
        assert payload.username == "Custom Username"
        assert payload.avatar_url == AVATAR_URL
        assert payload.get_flag(MessageFlags.SUPPRESS_NOTIFICATIONS)
        assert payload._query_params["wait"] == "True"
        assert payload._query_params["thread_id"] == "456"


def test_oversized_traceback_preserves_formatted_record(
    webhook_url: str, deliveries: list[Webhook], add_sink: Callable[..., int]
) -> None:
    formatted: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            formatted.append(record.getMessage())

    options = {"format": "{level.name} | {message}"}
    add_sink(Capture(), **options)
    sink = DiscordSink(webhook_url, rich=True)
    sink.webhook.add_component(TextDisplay(content="Configured component"))
    add_sink(sink, **options)

    try:
        raise ValueError("Invalid Unicode value 🚀 " * 250)
    except ValueError:
        logger.exception("Application failure")

    assert len(deliveries) == 1
    payload = deliveries[0]
    assert payload.components is UNSET
    assert not payload.get_flag(MessageFlags.IS_COMPONENTS_V2)
    assert "with_components" not in payload._query_params
    assert len(payload._attachments) == 1
    content = payload._attachments[0].content
    assert content == formatted[0].encode()
    assert isinstance(content, bytes)
    assert b"ERROR | Application failure" in content
    assert b"Traceback (most recent call last):" in content
    assert sink.webhook.get_flag(MessageFlags.IS_COMPONENTS_V2)
    assert isinstance(sink.webhook.components, list)
    assert len(sink.webhook.components) == 1


@pytest.mark.parametrize("rich", [False, True])
def test_failed_payload_does_not_contaminate_next_record(
    rich: bool,
    webhook_url: str,
    add_sink: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[Webhook] = []

    def execute(webhook: Webhook) -> None:
        attempts.append(deepcopy(webhook))
        if len(attempts) == 1:
            webhook.set_username("Failed payload")
            webhook.set_thread_id("failed-thread")
            webhook.add_attachment("failed.txt", b"Failed payload")
            raise RuntimeError("Execution failed")

    monkeypatch.setattr(Webhook, "execute", execute)
    sink = DiscordSink(webhook_url, username="Custom Username", rich=rich)
    sink.webhook.set_thread_id("456")
    template = deepcopy(sink.webhook)
    add_sink(sink)

    with pytest.raises(RuntimeError, match="Execution failed"):
        logger.info("Failed record")
    logger.info("Successful record")

    assert len(attempts) == 2
    payload = attempts[1]
    assert payload.username == "Custom Username"
    assert payload._query_params["thread_id"] == "456"
    assert payload._attachments == []
    if rich:
        assert isinstance(payload.components, list)
        assert len(payload.components) == 1
        container = payload.components[0]
        assert isinstance(container, Container)
        body = container.components[1]
        assert isinstance(body, TextDisplay)
        assert body.content == Markdown.code_block("Successful record")
    else:
        assert payload.content == Markdown.code_block("Successful record")
    assert sink.webhook == template
