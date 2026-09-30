import logging
from collections.abc import Callable

import pytest
from clyde import Markdown, Webhook
from clyde.components import Container, Seperator, TextDisplay
from clyde.webhook import MessageFlags
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
