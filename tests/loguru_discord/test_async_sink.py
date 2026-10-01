import asyncio
import gc
import logging
import weakref
from collections.abc import Callable, Coroutine
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from io import StringIO
from threading import Thread
from typing import Any
from unittest.mock import Mock

import pytest
from clyde import Markdown, Timestamp, Webhook
from clyde.components import Container, TextDisplay
from loguru import logger

from loguru_discord import AsyncDiscordSink, BufferOverflowError
from loguru_discord._delivery import delivery_active


def run(coroutine: Coroutine[Any, Any, None]) -> None:
    asyncio.run(asyncio.wait_for(coroutine, 10))


@pytest.fixture
def async_deliveries(monkeypatch: pytest.MonkeyPatch) -> list[Webhook]:
    payloads = []

    async def execute(webhook: Webhook, **options: Any) -> None:
        webhook._validate()
        payloads.append(deepcopy(webhook))

    monkeypatch.setattr(Webhook, "execute_async", execute)
    return payloads


@pytest.mark.parametrize("rich", [False, True])
def test_loguru_stream_protocol(
    rich: bool, webhook_url: str, async_deliveries: list[Webhook]
) -> None:
    async def scenario() -> None:
        async with AsyncDiscordSink(webhook_url, rich=rich) as sink:
            handler = logger.add(sink, catch=False, format="{message}")
            logger.info("First")
            logger.opt(raw=True).info("Raw\n\n")
            logger.info("x" * 5000)
            await logger.complete()
            assert sink.statistics.sent == 3
            assert sink.statistics.pending == sink.statistics.buffered_bytes == 0
            with pytest.raises(FrozenInstanceError):
                setattr(sink.statistics, "sent", 0)
            # Removal must return while the owning event loop is still running.
            logger.remove(handler)
            await sink.aclose()
            await sink.aclose()
        assert (
            async_deliveries[2]._attachments[0].content == ("x" * 5000 + "\n").encode()
        )
        for payload, text in zip(async_deliveries[:2], ["First\n", "Raw\n\n"]):
            body = payload.content
            if rich:
                assert isinstance(payload.components, list)
                container = payload.components[0]
                assert isinstance(container, Container)
                text_component = container.components[1]
                assert isinstance(text_component, TextDisplay)
                body = text_component.content
            assert body == Markdown.code_block(text)
        assert sink.statistics.failed == sink.statistics.dropped == 0

    run(scenario())


@pytest.mark.parametrize("limit", ["count", "bytes"])
def test_overload_is_bounded_before_scheduling(
    limit: str,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
) -> None:
    async def scenario() -> None:
        errors: list[Exception] = []
        entered, release = asyncio.Event(), asyncio.Event()
        sent = []

        async def execute(webhook: Webhook, **options: Any) -> None:
            sent.append(webhook.content)
            entered.set()
            await release.wait()

        monkeypatch.setattr(Webhook, "execute_async", execute)
        options: dict[str, Any] = (
            {"max_pending": 2} if limit == "count" else {"max_buffer_bytes": 18}
        )
        async with AsyncDiscordSink(
            webhook_url, on_error=errors.append, **options
        ) as sink:
            add_sink(sink)
            logger.info("🚀")  # 4 UTF-8 text bytes + newline + 4 level-name bytes
            await entered.wait()
            loop = asyncio.get_running_loop()
            schedule = Mock(wraps=loop.call_soon_threadsafe)
            monkeypatch.setattr(loop, "call_soon_threadsafe", schedule)
            tasks = set(asyncio.all_tasks())
            logger.info("🚀")
            for _ in range(2000):
                logger.info("🚀")
            stats = sink.statistics
            assert stats.pending == 2 and stats.dropped == 2000
            assert stats.buffered_bytes == 18
            assert schedule.call_count == 1
            assert set(asyncio.all_tasks()) == tasks
            assert len(sink._queue) == 1
            await asyncio.sleep(0)
            assert len(errors) == 1
            assert isinstance(errors[0], BufferOverflowError)
            assert errors[0].dropped == 2000
            release.set()
            await sink.complete()
            assert sink.statistics.sent == 2
            assert sent == [Markdown.code_block("🚀\n"), Markdown.code_block("🚀\n")]

    run(scenario())


def test_completion_boundary_and_waiter_cancellation(
    webhook_url: str, monkeypatch: pytest.MonkeyPatch, add_sink: Callable[..., int]
) -> None:
    async def scenario() -> None:
        entered = [asyncio.Event(), asyncio.Event()]
        release = [asyncio.Event(), asyncio.Event()]
        attempts = []

        async def execute(webhook: Webhook, **options: Any) -> None:
            index = len(attempts)
            attempts.append(webhook.content)
            entered[index].set()
            await release[index].wait()

        monkeypatch.setattr(Webhook, "execute_async", execute)
        async with AsyncDiscordSink(webhook_url) as sink:
            add_sink(sink)
            logger.info("Before boundary")
            await entered[0].wait()
            drain = asyncio.create_task(sink.complete())
            cancelled = asyncio.create_task(sink.complete())
            await asyncio.sleep(0)
            cancelled.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled
            logger.info("After boundary")
            release[0].set()
            await drain
            assert sink.statistics.sent == 1 and sink.statistics.pending == 1
            await entered[1].wait()
            assert not release[1].is_set()
            release[1].set()
            await sink.complete()
            await sink.complete()

    run(scenario())


@pytest.mark.parametrize("shutdown", ["timeout", "cancel"])
def test_shutdown_cancels_delivery_and_accounts_for_abandonment(
    shutdown: str,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
) -> None:
    async def scenario() -> None:
        entered, cleaned = asyncio.Event(), asyncio.Event()
        errors = []

        async def execute(webhook: Webhook, **options: Any) -> None:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0)
                cleaned.set()

        monkeypatch.setattr(Webhook, "execute_async", execute)
        sink = await AsyncDiscordSink(
            webhook_url, shutdown_timeout=0.02, on_error=errors.append
        ).start()
        add_sink(sink)
        logger.info("In flight")
        logger.info("Queued")
        await entered.wait()
        drain = asyncio.create_task(sink.complete())
        close = asyncio.create_task(sink.aclose())
        await asyncio.sleep(0)
        if shutdown == "cancel":
            close.cancel()
            with pytest.raises(asyncio.CancelledError):
                await close
        else:
            await close
            assert isinstance(errors[0], TimeoutError)
        await drain
        assert cleaned.is_set()
        assert sink.statistics.failed == 2
        assert sink.statistics.pending == sink.statistics.buffered_bytes == 0
        assert sink._queue == sink._queue.__class__()
        sink.stop()
        await sink.aclose()

    run(scenario())


def test_threaded_and_async_producers_preserve_order(
    webhook_url: str, async_deliveries: list[Webhook], add_sink: Callable[..., int]
) -> None:
    async def scenario() -> None:
        async with AsyncDiscordSink(webhook_url, intercept=True) as sink:
            add_sink(sink)
            expected = []

            async def producer(index: int) -> None:
                for item in range(20):
                    text = f"{index}:{item}"
                    expected.append(text)
                    logger.info(text)
                    await asyncio.sleep(0)

            await asyncio.gather(*(producer(index) for index in range(4)))
            await asyncio.to_thread(logging.info, "Thread record")
            expected.append("Thread record")
            await logger.complete()
            assert [payload.content for payload in async_deliveries] == [
                Markdown.code_block(text + "\n") for text in expected
            ]
            assert sink.statistics.sent == 81

    run(scenario())


def test_buffer_does_not_retain_bound_objects_or_traceback_frames(
    webhook_url: str, monkeypatch: pytest.MonkeyPatch, add_sink: Callable[..., int]
) -> None:
    async def scenario() -> None:
        entered, release = asyncio.Event(), asyncio.Event()

        async def execute(webhook: Webhook, **options: Any) -> None:
            entered.set()
            await release.wait()

        monkeypatch.setattr(Webhook, "execute_async", execute)
        async with AsyncDiscordSink(webhook_url) as sink:
            add_sink(sink)
            logger.info("Block delivery")
            await entered.wait()

            class Object:
                pass

            def log_exception() -> weakref.ReferenceType[Object]:
                bound = Object()
                reference = weakref.ref(bound)
                try:
                    raise ValueError("Failure")
                except ValueError:
                    logger.bind(bound=bound).exception("Queued traceback")
                return reference

            reference = log_exception()
            gc.collect()
            assert reference() is None
            queued = sink._queue[0][1]
            assert type(queued.text) is str
            assert "ValueError: Failure" in queued.text
            release.set()
            await sink.complete()

    run(scenario())


def test_failures_continue_and_callback_cannot_reenter(
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def scenario() -> None:
        attempts = []

        async def execute(webhook: Webhook, **options: Any) -> None:
            attempts.append(webhook.content)
            if len(attempts) == 1:
                raise ValueError("Delivery failed")

        monkeypatch.setattr(Webhook, "execute_async", execute)

        def callback(error: Exception) -> None:
            assert sink.statistics.pending == 2  # Outside the admission lock
            logging.error("Callback standard-library log")
            logger.error("Callback Loguru log")
            raise RuntimeError("Callback failure")

        async with AsyncDiscordSink(
            webhook_url, intercept=True, on_error=callback
        ) as sink:
            add_sink(sink)
            logger.info("Fail")
            logger.info("Succeed")
            await sink.complete()
            assert sink.statistics.sent == sink.statistics.failed == 1
            assert len(attempts) == 2
            assert not delivery_active.get()
        assert "error callback failed: RuntimeError" in capsys.readouterr().err

    run(scenario())


@pytest.mark.parametrize("stderr", ["absent", "closed", "io_error"])
@pytest.mark.parametrize("callback_fails", [False, True])
def test_reporting_failures_do_not_stop_delivery(
    stderr: str,
    callback_fails: bool,
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
) -> None:
    async def scenario() -> None:
        attempts = []

        async def execute(webhook: Webhook, **options: Any) -> None:
            attempts.append(webhook.content)
            if len(attempts) == 1:
                raise ValueError("Delivery failed")

        callback = Mock(side_effect=RuntimeError("Callback failed"))
        monkeypatch.setattr(Webhook, "execute_async", execute)
        stream = None
        if stderr == "closed":
            stream = StringIO()
            stream.close()
        elif stderr == "io_error":
            stream = Mock(write=Mock(side_effect=OSError("Stderr unavailable")))

        async with AsyncDiscordSink(
            webhook_url, on_error=callback if callback_fails else None
        ) as sink:
            add_sink(sink)
            with monkeypatch.context() as patch:
                patch.setattr("loguru_discord.async_sink.sys.stderr", stream)
                logger.info("Failed record")
                await sink.complete()
                assert sink.statistics.failed == 1
                assert sink._worker_task is not None
                assert not sink._worker_task.done()
                logger.info("Record after reporting failure")
                await sink.complete()
                assert sink.statistics.sent == 1
                assert sink.statistics.pending == sink.statistics.buffered_bytes == 0
                assert len(attempts) == 2
                assert not delivery_active.get()
            if callback_fails:
                callback.assert_called_once()
            else:
                callback.assert_not_called()
        await sink.aclose()

    run(scenario())


def test_worker_cancellation_closes_admission(
    webhook_url: str, monkeypatch: pytest.MonkeyPatch, add_sink: Callable[..., int]
) -> None:
    async def scenario() -> None:
        async def execute(webhook: Webhook, **options: Any) -> None:
            raise asyncio.CancelledError

        monkeypatch.setattr(Webhook, "execute_async", execute)
        async with AsyncDiscordSink(webhook_url) as sink:
            add_sink(sink)
            logger.info("Cancelled delivery")
            logger.info("Queued delivery")
            await sink.complete()
            assert sink.statistics.failed == 2
            assert sink.statistics.pending == sink.statistics.buffered_bytes == 0
            assert sink._worker_task is not None
            assert sink._worker_task.cancelled()
            with pytest.raises(RuntimeError, match="accepting records"):
                logger.info("No worker to deliver this record")
        await sink.complete()

    run(scenario())


@pytest.mark.parametrize(
    "options",
    [
        {"max_pending": 0},
        {"max_pending": True},
        {"max_pending": 1.5},
        {"max_buffer_bytes": -1},
        {"max_buffer_bytes": "1"},
        {"shutdown_timeout": 0},
        {"shutdown_timeout": float("inf")},
        {"shutdown_timeout": True},
        {"shutdown_timeout": "1"},
    ],
)
def test_invalid_limits(webhook_url: str, options: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        AsyncDiscordSink(webhook_url, **options)


@pytest.mark.parametrize("options", [{"on_error": 1}, {"request_policy": 1}])
def test_invalid_callback_or_policy(webhook_url: str, options: dict[str, Any]) -> None:
    with pytest.raises(TypeError):
        AsyncDiscordSink(webhook_url, **options)


def test_invalid_lifecycle_and_closing_before_start(
    webhook_url: str, add_sink: Callable[..., int]
) -> None:
    async def scenario() -> None:
        sink = AsyncDiscordSink(webhook_url)
        add_sink(sink)
        with pytest.raises(RuntimeError, match="must be started"):
            logger.info("Too early")
        with pytest.raises(RuntimeError, match="starting event loop"):
            await sink.complete()
        sink.stop()
        sink.stop()
        await sink.aclose()
        await sink.aclose()
        with pytest.raises(RuntimeError, match="closing or closed"):
            await sink.start()

    run(scenario())


def test_single_owning_loop(webhook_url: str, async_deliveries: list[Webhook]) -> None:
    sink = AsyncDiscordSink(webhook_url)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(sink.start())
        with pytest.raises(RuntimeError, match="starting event loop"):
            asyncio.run(sink.start())
        with pytest.raises(RuntimeError, match="starting event loop"):
            asyncio.run(sink.aclose())
        loop.run_until_complete(sink.aclose())
    finally:
        loop.close()


def test_concurrent_start_and_close(
    webhook_url: str, async_deliveries: list[Webhook]
) -> None:
    async def scenario() -> None:
        sink = AsyncDiscordSink(webhook_url)
        assert await asyncio.gather(sink.start(), sink.start()) == [sink, sink]
        assert await sink.start() is sink
        await asyncio.gather(sink.aclose(), sink.aclose())
        with pytest.raises(RuntimeError, match="closing or closed"):
            await sink.start()

    run(scenario())


@pytest.mark.parametrize("cancel", [False, True])
def test_failed_or_cancelled_initialization(
    cancel: bool, webhook_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        entered, cleaned = asyncio.Event(), asyncio.Event()

        async def modify(webhook: Webhook, **options: Any) -> None:
            assert delivery_active.get()
            entered.set()
            try:
                if cancel:
                    await asyncio.Event().wait()
                raise ValueError("Invalid avatar")
            finally:
                cleaned.set()

        monkeypatch.setattr(Webhook, "modify_async", modify)
        sink = AsyncDiscordSink(webhook_url, avatar=None)
        task = asyncio.create_task(sink.start())
        await entered.wait()
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else ValueError):
            await task
        assert cleaned.is_set()
        assert sink._worker_task is None
        await sink.aclose()
        assert not delivery_active.get()

    run(scenario())


def test_stop_during_initialization(
    webhook_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        sink = AsyncDiscordSink(webhook_url, avatar=None)

        async def modify(webhook: Webhook, **options: Any) -> None:
            sink.stop()

        monkeypatch.setattr(Webhook, "modify_async", modify)
        with pytest.raises(RuntimeError, match="stopped during startup"):
            await sink.start()
        await sink.aclose()
        assert sink._worker_task is None

    run(scenario())


def test_suppression_and_closed_loop_admission(
    webhook_url: str,
    async_deliveries: list[Webhook],
    add_sink: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        class SuppressedError(ValueError):
            pass

        async with AsyncDiscordSink(webhook_url, suppress=[ValueError]) as sink:
            add_sink(sink)
            try:
                raise SuppressedError("Suppressed")
            except SuppressedError:
                logger.exception("Skip subclass")
            assert sink.statistics.pending == 0
            logger.info("Not suppressed")
            await sink.complete()
            assert sink.statistics.sent == 1
            loop = asyncio.get_running_loop()
            with monkeypatch.context() as patch:
                patch.setattr(loop, "is_closed", lambda: True)
                with pytest.raises(RuntimeError, match="event loop is closed"):
                    logger.info("Invalid owner")

    run(scenario())


def test_default_reporting_and_cancelled_waiter_notification(
    webhook_url: str,
    monkeypatch: pytest.MonkeyPatch,
    add_sink: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Separate the default reporter from the cancellation race, then drive
    # cancellation from the failure callback before the worker releases waiters.
    async def scenarios() -> None:
        async def fail(webhook: Webhook, **options: Any) -> None:
            raise ValueError("Reported failure")

        monkeypatch.setattr(Webhook, "execute_async", fail)
        async with AsyncDiscordSink(webhook_url) as default_sink:
            handler = logger.add(default_sink, catch=False, format="{message}")
            logger.info("Fail")
            await default_sink.complete()
            logger.remove(handler)
        assert (
            "AsyncDiscordSink: ValueError: Reported failure" in capsys.readouterr().err
        )

        entered, release = asyncio.Event(), asyncio.Event()

        async def execute(webhook: Webhook, **options: Any) -> None:
            entered.set()
            await release.wait()
            raise ValueError("Cancelled drain")

        def callback(error: Exception) -> None:
            sink._waiters[0][1].cancel()

        monkeypatch.setattr(Webhook, "execute_async", execute)
        async with AsyncDiscordSink(webhook_url, on_error=callback) as sink:
            add_sink(sink)
            logger.info("Fail again")
            await entered.wait()
            drain = asyncio.create_task(sink.complete())
            await asyncio.sleep(0)
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await drain
            assert sink.statistics.failed == 1
            assert not sink._waiters

    run(scenarios())


def test_close_while_startup_is_pending(
    webhook_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        entered, cleaned = asyncio.Event(), asyncio.Event()

        async def modify(webhook: Webhook, **options: Any) -> None:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0)
                cleaned.set()

        monkeypatch.setattr(Webhook, "modify_async", modify)
        sink = AsyncDiscordSink(webhook_url, avatar=None)
        startup = asyncio.create_task(sink.start())
        await entered.wait()
        await sink.aclose()
        with pytest.raises(asyncio.CancelledError):
            await startup
        assert cleaned.is_set()
        assert sink._worker_task is None
        await sink.aclose()

    run(scenario())


@pytest.mark.parametrize("rich", [False, True])
@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("character", ["x", "é", "🚀"])
def test_async_format_boundaries(
    rich: bool,
    offset: int,
    character: str,
    webhook_url: str,
    async_deliveries: list[Webhook],
    add_sink: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "loguru_discord.async_sink.datetime", Mock(now=Mock(return_value=timestamp))
    )
    footer = f"-# {Timestamp.long_date_time(timestamp)} ({Timestamp.relative_time(timestamp)})"
    budget = 4000 - len("### INFO") - len(footer) if rich else 2000
    text = character * (budget - len("```\n\n```") + offset)

    async def scenario() -> None:
        async with AsyncDiscordSink(webhook_url, rich=rich) as sink:
            add_sink(sink)
            logger.opt(raw=True).info(text)
            await sink.complete()
            payload = async_deliveries[0]
            if offset > 0:
                assert payload._attachments[0].content == text.encode()
            else:
                assert not payload._attachments
                if rich:
                    assert isinstance(payload.components, list)
                    container = payload.components[0]
                    assert isinstance(container, Container)
                    body = container.components[1]
                    assert isinstance(body, TextDisplay)
                    assert body.content == Markdown.code_block(text)
                else:
                    assert payload.content == Markdown.code_block(text)

    run(scenario())


def test_thread_burst_has_one_notification_and_drops_newest(
    webhook_url: str,
    async_deliveries: list[Webhook],
    add_sink: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        errors = []
        async with AsyncDiscordSink(
            webhook_url, max_pending=4, on_error=errors.append
        ) as sink:
            add_sink(sink)
            loop = asyncio.get_running_loop()
            schedule = Mock(wraps=loop.call_soon_threadsafe)
            monkeypatch.setattr(loop, "call_soon_threadsafe", schedule)
            thread = Thread(
                target=lambda: [logger.info(f"Record {index}") for index in range(100)]
            )
            thread.start()
            # The loop is deliberately paused until admission finishes, so this
            # checks bounds before any scheduled callback can run.
            thread.join(5)
            assert not thread.is_alive()
            assert schedule.call_count == 1
            assert sink.statistics.pending == 4 and sink.statistics.dropped == 96
            await sink.complete()
            assert [payload.content for payload in async_deliveries] == [
                Markdown.code_block(f"Record {index}\n") for index in range(4)
            ]
            assert isinstance(errors[0], BufferOverflowError)
            assert errors[0].dropped == 96

    run(scenario())
