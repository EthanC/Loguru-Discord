import logging
from collections.abc import Callable
from copy import deepcopy

import pytest
from clyde import Markdown, Webhook
from clyde.components import Container, Seperator, TextDisplay
from clyde.webhook import AllowedMentions, MessageFlags
from loguru import logger
from msgspec import UNSET

from loguru_discord import DiscordSink

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
    assert attachment.content == Markdown.code_block(message).encode()


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
    assert long._attachments[0].content == Markdown.code_block(messages[1]).encode()
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
