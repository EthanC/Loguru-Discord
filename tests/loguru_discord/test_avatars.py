import json
import logging
from base64 import b64decode
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from clyde import Markdown, Webhook
from loguru import logger
from msgspec import UNSET, UnsetType
from niquests import ConnectionError, HTTPError, PreparedRequest, Response, Session

from loguru_discord import DiscordSink
from loguru_discord._delivery import delivery_active

AVATAR_URL = "https://example.com/avatar.png"
AVATAR_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1XkAAAAASUVORK5CYII="
)
AVATAR_BYTES = b64decode(AVATAR_DATA_URI.split(",", 1)[1])


def test_default_avatar_does_not_make_request(
    webhook_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = Mock()
    monkeypatch.setattr("clyde.webhook.Session.send", transport)

    sink = DiscordSink(webhook_url)

    transport.assert_not_called()
    assert sink.avatar is UNSET
    assert sink.webhook.avatar_url is UNSET


@pytest.mark.parametrize("rich", [False, True])
@pytest.mark.parametrize("avatar_url", [None, AVATAR_URL])
@pytest.mark.parametrize(
    "avatar", [UNSET, None, AVATAR_DATA_URI, AVATAR_BYTES, Path("avatar.png")]
)
def test_avatar_requests(
    rich: bool,
    avatar_url: str | None,
    avatar: UnsetType | None | str | bytes | Path,
    webhook_url: str,
    add_sink: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    requests: list[PreparedRequest] = []
    if isinstance(avatar, Path):
        avatar = tmp_path / avatar
        avatar.write_bytes(AVATAR_BYTES)

    def transport(
        session: Session, request: PreparedRequest, **options: Any
    ) -> Response:
        requests.append(request)
        response = Response()
        response.status_code = 200 if request.method == "PATCH" else 204
        response._content = b"{}" if request.method == "PATCH" else b""
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr("clyde.webhook.Session.send", transport)
    sink = DiscordSink(
        f"{webhook_url}?thread_id=123&wait=true",
        thread_id="456",
        username="Application logs",
        avatar_url=avatar_url,
        avatar=avatar,
        rich=rich,
    )

    if avatar is UNSET:
        assert requests == []
    else:
        assert len(requests) == 1
        modification = requests[0]
        assert modification.method == "PATCH"
        assert modification.url == webhook_url
        assert isinstance(modification.body, bytes)
        assert json.loads(modification.body) == {
            "avatar": None if avatar is None else AVATAR_DATA_URI
        }
    assert sink.avatar == avatar
    assert sink.avatar_url == avatar_url
    if isinstance(avatar, Path):
        avatar.unlink()

    add_sink(sink)
    for message in ["First application record", "Second application record"]:
        logger.info(message)
        request = requests[-1]
        assert request.method == "POST"
        assert isinstance(request.url, str)
        assert request.url.startswith(webhook_url + "?")
        assert "thread_id=456" in request.url
        assert isinstance(request.body, bytes)
        payload = json.loads(request.body)
        assert payload["username"] == "Application logs"
        if avatar_url is None:
            assert "avatar_url" not in payload
        else:
            assert payload["avatar_url"] == avatar_url
        assert "avatar" not in payload
        if rich:
            assert payload["components"][0]["components"][1]["content"] == (
                Markdown.code_block(message)
            )
        else:
            assert payload["content"] == Markdown.code_block(message)
    assert len(requests) == (2 if avatar is UNSET else 3)


@pytest.mark.parametrize("avatar", [b"", b"not an image", Path("missing.png")])
def test_invalid_avatar_fails_before_request(
    avatar: bytes | Path,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    transport = Mock()
    monkeypatch.setattr("clyde.webhook.Session.send", transport)
    if isinstance(avatar, Path):
        avatar = tmp_path / avatar
        error = FileNotFoundError
        message = "missing.png"
    else:
        error = ValueError
        message = "PNG, JPEG, or GIF"

    with pytest.raises(error, match=message):
        DiscordSink(webhook_url, avatar=avatar)

    transport.assert_not_called()
    assert not delivery_active.get()


@pytest.mark.parametrize("already_active", [False, True])
@pytest.mark.parametrize("failure", ["none", "http", "transport"])
def test_avatar_request_restores_context_and_suppresses_transport_logs(
    already_active: bool,
    failure: str,
    webhook_url: str,
    deliveries: list[Webhook],
    add_sink: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[PreparedRequest] = []
    add_sink(DiscordSink(webhook_url, intercept=True))

    def transport(
        session: Session, request: PreparedRequest, **options: Any
    ) -> Response:
        requests.append(request)
        assert delivery_active.get()
        logging.getLogger("urllib3.connectionpool").debug("Updating webhook avatar")
        if failure == "transport":
            raise ConnectionError("Avatar update failed", request=request)
        response = Response()
        response.status_code = 400 if failure == "http" else 200
        response._content = b"{}"
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr("clyde.webhook.Session.send", transport)
    token = delivery_active.set(already_active)
    try:
        if failure == "none":
            DiscordSink(webhook_url, avatar=None)
        else:
            error = HTTPError if failure == "http" else ConnectionError
            with pytest.raises(error):
                DiscordSink(webhook_url, avatar=None)

        assert len(requests) == 1
        assert requests[0].method == "PATCH"
        assert deliveries == []
        assert delivery_active.get() is already_active
    finally:
        delivery_active.reset(token)

    logging.info("Application logging resumes")
    assert len(deliveries) == 1
    assert deliveries[0].content == Markdown.code_block("Application logging resumes")
