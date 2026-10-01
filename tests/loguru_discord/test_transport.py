import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event, get_ident
from typing import Any
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from clyde import RateLimitExceeded, RequestDeadlineExceeded, RequestPolicy, Webhook
from loguru import logger
from niquests import (
    AsyncSession,
    ConnectionError,
    HTTPError,
    PreparedRequest,
    Response,
    Session,
)

from loguru_discord import AsyncDiscordSink, DiscordSink
from loguru_discord._delivery import delivery_active
from tests.loguru_discord.test_async_sink import run
from tests.loguru_discord.test_avatars import AVATAR_BYTES, AVATAR_DATA_URI


def response(
    request: PreparedRequest, status: int = 204, body: bytes = b""
) -> Response:
    result = Response()
    result.status_code = status
    result._content = body
    result._content_consumed = True
    result.request = request
    result.url = request.url
    return result


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("custom_policy", [False, True])
def test_policy_forwarding_through_real_request_building(
    asynchronous: bool,
    custom_policy: bool,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
) -> None:
    requests = []
    policy = (
        RequestPolicy(
            connect_timeout=2,
            read_timeout=7,
            max_rate_limit_retries=1,
            total_timeout=20,
        )
        if custom_policy
        else None
    )

    def transport(session: Any, request: PreparedRequest, **options: Any) -> Response:
        assert delivery_active.get()
        logging.debug("Transport log must not be admitted")
        requests.append((request, options))
        return response(request, 200 if request.method == "PATCH" else 204, b"{}")

    async def async_transport(
        session: Any, request: PreparedRequest, **options: Any
    ) -> Response:
        await asyncio.sleep(0)
        return transport(session, request, **options)

    monkeypatch.setattr(Session, "send", transport)
    monkeypatch.setattr(AsyncSession, "send", async_transport)
    arguments: dict[str, Any] = dict(
        avatar=None,
        username="Application",
        avatar_url="https://example.com/avatar.png",
        thread_id="456",
        rich=True,
        intercept=True,
        request_policy=policy,
    )
    if asynchronous:

        async def scenario() -> None:
            sink = AsyncDiscordSink(webhook_url + "?thread_id=123", **arguments)
            assert not requests  # Constructor is configuration-only.
            async with sink:
                add_sink(sink)
                for message in ["Short", "x" * 5000, "Short again"]:
                    logger.info(message)
                await sink.complete()
                assert sink.statistics.sent == 3

        run(scenario())
    else:
        sink = DiscordSink(webhook_url + "?thread_id=123", **arguments)
        add_sink(sink)
        for message in ["Short", "x" * 5000, "Short again"]:
            logger.info(message)
    assert len(requests) == 4
    assert [request.method for request, _ in requests] == [
        "PATCH",
        "POST",
        "POST",
        "POST",
    ]
    for request, options in requests:
        connect, read, remaining = options["timeout"]
        assert (connect, read) == ((2, 7) if custom_policy else (5, 10))
        assert 0 < remaining <= (20 if custom_policy else 30)
        if request.method == "PATCH":
            assert request.url == webhook_url
            assert json.loads(request.body) == {"avatar": None}
        else:
            assert parse_qs(urlsplit(request.url).query)["thread_id"] == ["456"]
    assert requests[2][0].headers["Content-Type"].startswith("multipart/form-data")
    assert "with_components" not in parse_qs(urlsplit(requests[2][0].url).query)
    for index in [1, 3]:
        body = json.loads(requests[index][0].body)
        assert body["username"] == "Application"
        assert body["avatar_url"] == "https://example.com/avatar.png"
        assert len(body["components"]) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("failure", ["rate_limit", "retry_deadline", "http", "network"])
def test_delivery_error_types_and_completion(
    asynchronous: bool,
    failure: str,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
) -> None:
    attempts = []
    closed_responses = []
    original_close = Response.close
    original_exit = Response.__aexit__

    def close(result: Response) -> None:
        closed_responses.append(result)
        original_close(result)

    monkeypatch.setattr(Response, "close", close)

    async def exit(result: Response, *exc_info: Any) -> None:
        closed_responses.append(result)
        await original_exit(result, *exc_info)

    monkeypatch.setattr(Response, "__aexit__", exit)
    types = {
        "rate_limit": RateLimitExceeded,
        "retry_deadline": RequestDeadlineExceeded,
        "http": HTTPError,
        "network": ConnectionError,
    }

    def transport(session: Any, request: PreparedRequest, **options: Any) -> Response:
        attempts.append(request)
        if failure == "network":
            raise ConnectionError("Network failure")
        if failure == "http":
            return response(request, 500, b"{}")
        return response(
            request,
            429,
            b'{"retry_after": 60}'
            if failure == "retry_deadline"
            else b'{"retry_after": 0}',
        )

    async def async_transport(
        session: Any, request: PreparedRequest, **options: Any
    ) -> Response:
        return transport(session, request, **options)

    monkeypatch.setattr(Session, "send", transport)
    monkeypatch.setattr(AsyncSession, "send", async_transport)
    policy = RequestPolicy(
        connect_timeout=5, read_timeout=10, max_rate_limit_retries=3, total_timeout=30
    )
    if asynchronous:

        async def scenario() -> None:
            errors = []
            async with AsyncDiscordSink(
                webhook_url, request_policy=policy, on_error=errors.append
            ) as sink:
                add_sink(sink)
                logger.info("Failure")
                await sink.complete()
                assert sink.statistics.failed == 1 and sink.statistics.pending == 0
                assert len(errors) == 1 and isinstance(errors[0], types[failure])
                if failure == "rate_limit":
                    assert errors[0].attempts == 4

        run(scenario())
    else:
        add_sink(DiscordSink(webhook_url, request_policy=policy))
        with pytest.raises(types[failure]) as error:
            logger.info("Failure")
        if failure == "rate_limit":
            assert isinstance(error.value, RateLimitExceeded)
            assert error.value.attempts == 4
    assert len(attempts) == (4 if failure == "rate_limit" else 1)
    assert len(closed_responses) == (0 if failure == "network" else len(attempts))
    assert not delivery_active.get()


@pytest.mark.parametrize("cancel", [False, True])
def test_async_deadline_and_session_cleanup(
    cancel: bool,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
) -> None:
    async def scenario() -> None:
        entered, cleaned = asyncio.Event(), asyncio.Event()
        original_close = AsyncSession.close
        sessions = []

        async def close(session: AsyncSession) -> None:
            await original_close(session)
            sessions.append(session)

        async def transport(
            session: AsyncSession, request: PreparedRequest, **options: Any
        ) -> Response:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
            raise AssertionError("Transport should have been cancelled")

        monkeypatch.setattr(AsyncSession, "send", transport)
        monkeypatch.setattr(AsyncSession, "close", close)
        errors = []
        policy = RequestPolicy(
            total_timeout=30 if cancel else 0.03, max_rate_limit_retries=0
        )
        async with AsyncDiscordSink(
            webhook_url, request_policy=policy, on_error=errors.append
        ) as sink:
            add_sink(sink)
            logger.info("Deadline")
            await entered.wait()  # Event loop progresses while HTTP is pending.
            if cancel:
                close_task = asyncio.create_task(sink.aclose())
                await asyncio.sleep(0)
                close_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await close_task
            await sink.complete()
            assert cleaned.is_set() and len(sessions) == 1
            if cancel:
                assert not errors
            else:
                assert isinstance(errors[0], RequestDeadlineExceeded)
            assert sink.statistics.failed == 1

    run(scenario())


@pytest.mark.parametrize("shutdown", ["timeout", "cancel", "graceful"])
def test_shutdown_during_request_deadline_cleanup(
    shutdown: str,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
) -> None:
    async def scenario() -> None:
        cleanup_started, release_cleanup, cleaned, shutdown_expired = (
            asyncio.Event() for _ in range(4)
        )
        requests = []
        errors = []
        original_close = AsyncSession.close

        async def close(session: AsyncSession) -> None:
            cleanup_started.set()
            await release_cleanup.wait()
            await original_close(session)
            cleaned.set()

        async def transport(
            session: AsyncSession, request: PreparedRequest, **options: Any
        ) -> Response:
            requests.append(request)
            if len(requests) == 1:
                await asyncio.Event().wait()
            return response(request)

        def report(error: Exception) -> None:
            errors.append(error)
            if isinstance(error, TimeoutError):
                shutdown_expired.set()

        monkeypatch.setattr(AsyncSession, "send", transport)
        monkeypatch.setattr(AsyncSession, "close", close)
        async with AsyncDiscordSink(
            webhook_url,
            request_policy=RequestPolicy(total_timeout=0.1),
            shutdown_timeout=0.02 if shutdown == "timeout" else 30,
            on_error=report,
        ) as sink:
            add_sink(sink)
            logger.info("Request that exceeds its deadline")
            logger.info("Queued record 1")
            logger.info("Queued record 2")
            await cleanup_started.wait()
            # Clyde's deadline has cancelled the worker, but its session must
            # finish closing before that cancellation becomes a delivery error.
            assert sink._worker_task is not None
            assert sink._worker_task.cancelling() > 0
            drain = asyncio.create_task(sink.complete())
            closing = asyncio.create_task(sink.aclose())
            try:
                if shutdown == "timeout":
                    await shutdown_expired.wait()
                else:
                    await asyncio.sleep(0)
                    if shutdown == "cancel":
                        closing.cancel()
                        await asyncio.sleep(0)
                assert not cleaned.is_set()
                assert not closing.done()
                assert not drain.done()
            finally:
                release_cleanup.set()
            if shutdown == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    await closing
            else:
                await closing
            await drain
            assert cleaned.is_set()
            assert any(isinstance(error, RequestDeadlineExceeded) for error in errors)
            assert len(requests) == (3 if shutdown == "graceful" else 1)
            stats = sink.statistics
            assert stats.sent == (2 if shutdown == "graceful" else 0)
            assert stats.failed == (1 if shutdown == "graceful" else 3)
            assert stats.pending == stats.buffered_bytes == 0
            await sink.aclose()

    run(scenario())


@pytest.mark.parametrize("avatar", [None, AVATAR_BYTES, AVATAR_DATA_URI])
def test_async_avatar_input_parity(
    avatar: None | bytes | str, webhook_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        requests = []

        async def transport(
            session: AsyncSession, request: PreparedRequest, **options: Any
        ) -> Response:
            requests.append(request)
            return response(request, 200, b"{}")

        monkeypatch.setattr(AsyncSession, "send", transport)
        sink = AsyncDiscordSink(webhook_url, avatar=avatar)
        assert not requests
        async with sink:
            assert len(requests) == 1
            assert requests[0].method == "PATCH"
            assert json.loads(requests[0].body) == {
                "avatar": None if avatar is None else AVATAR_DATA_URI
            }

    run(scenario())


@pytest.mark.parametrize("failure", ["invalid_image", "missing_file", "http", "retry"])
def test_async_avatar_errors_propagate_after_cleanup(
    failure: str, webhook_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def scenario() -> None:
        requests = []
        original_close = AsyncSession.close
        closed = []

        async def close(session: AsyncSession) -> None:
            await original_close(session)
            closed.append(session)

        async def transport(
            session: AsyncSession, request: PreparedRequest, **options: Any
        ) -> Response:
            requests.append(request)
            return response(request, 500 if failure == "http" else 429, b"{}")

        monkeypatch.setattr(AsyncSession, "send", transport)
        monkeypatch.setattr(AsyncSession, "close", close)
        avatars = {
            "invalid_image": b"invalid",
            "missing_file": tmp_path / "missing.png",
            "http": None,
            "retry": None,
        }
        errors = {
            "invalid_image": ValueError,
            "missing_file": FileNotFoundError,
            "http": HTTPError,
            "retry": RateLimitExceeded,
        }
        sink = AsyncDiscordSink(
            webhook_url,
            avatar=avatars[failure],
            request_policy=RequestPolicy(max_rate_limit_retries=0, total_timeout=30),
        )
        with pytest.raises(errors[failure]):
            await sink.start()
        assert len(requests) == (1 if failure in {"http", "retry"} else 0)
        assert len(closed) == len(requests)
        assert sink._worker_task is None
        await sink.aclose()

    run(scenario())


def test_startup_cancellation_does_not_interrupt_transport_cleanup(
    webhook_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        entered, closing, release, cleaned = (asyncio.Event() for _ in range(4))
        original_close = AsyncSession.close

        async def close(session: AsyncSession) -> None:
            closing.set()
            await release.wait()
            await original_close(session)
            cleaned.set()

        async def transport(
            session: AsyncSession, request: PreparedRequest, **options: Any
        ) -> Response:
            entered.set()
            await asyncio.Event().wait()
            raise AssertionError("Expected cancellation")

        monkeypatch.setattr(AsyncSession, "send", transport)
        monkeypatch.setattr(AsyncSession, "close", close)
        sink = AsyncDiscordSink(webhook_url, avatar=None)
        startup = asyncio.create_task(sink.start())
        await entered.wait()
        startup.cancel()
        await closing.wait()
        # A concurrent close joins cancellation cleanup instead of cancelling
        # modify_async() again while its session is being closed.
        concurrent_close = asyncio.create_task(sink.aclose())
        await asyncio.sleep(0)
        assert not startup.done() and not concurrent_close.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await startup
        await concurrent_close
        assert cleaned.is_set()

    run(scenario())


def test_async_retry_wait_is_nonblocking(
    webhook_url: str, monkeypatch: pytest.MonkeyPatch, add_sink: Callable[..., int]
) -> None:
    async def scenario() -> None:
        waiting, release = asyncio.Event(), asyncio.Event()
        requests = []

        async def sleep(delay: float) -> None:
            assert delay == 0.5
            waiting.set()
            await release.wait()

        async def transport(
            session: AsyncSession, request: PreparedRequest, **options: Any
        ) -> Response:
            requests.append(request)
            return (
                response(request, 429, b'{"retry_after": 0.5}')
                if len(requests) == 1
                else response(request)
            )

        monkeypatch.setattr("clyde.webhook.async_sleep", sleep)
        monkeypatch.setattr(AsyncSession, "send", transport)
        async with AsyncDiscordSink(webhook_url) as sink:
            add_sink(sink)
            logger.info("Retry")
            await waiting.wait()
            logger.info("Admitted during retry")
            assert sink.statistics.pending == 2
            release.set()
            await sink.complete()
            assert len(requests) == 3 and sink.statistics.sent == 2

    run(scenario())


@pytest.mark.parametrize("cancel", [False, True])
def test_async_avatar_file_loading_runs_off_loop(
    cancel: bool, webhook_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def scenario() -> None:
        reading, release = Event(), Event()
        path = tmp_path / "avatar.png"
        path.write_bytes(AVATAR_BYTES)
        original_read = Path.read_bytes
        owner_thread = get_ident()
        requests = []

        def read(file: Path) -> bytes:
            assert get_ident() != owner_thread
            reading.set()
            assert release.wait(5)
            return original_read(file)

        async def transport(
            session: AsyncSession, request: PreparedRequest, **options: Any
        ) -> Response:
            requests.append(request)
            return response(request, 200, b"{}")

        monkeypatch.setattr(Path, "read_bytes", read)
        monkeypatch.setattr(AsyncSession, "send", transport)
        sink = AsyncDiscordSink(webhook_url, avatar=path)
        startup = asyncio.create_task(sink.start())
        try:
            assert await asyncio.to_thread(reading.wait, 5)
            assert not startup.done() and not requests
            if cancel:
                startup.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await startup
                assert not requests
            else:
                release.set()
                await startup
                assert json.loads(requests[0].body) == {"avatar": AVATAR_DATA_URI}
        finally:
            release.set()
            await sink.aclose()

    run(scenario())
