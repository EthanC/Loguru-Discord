"""Deliver Loguru messages through one bounded, native async webhook worker."""

from __future__ import annotations

import asyncio
import sys
from collections import deque
from collections.abc import Callable
from contextvars import Context
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Self

from clyde import RequestPolicy
from msgspec import UNSET, UnsetType

from loguru_discord._delivery import delivery_active
from loguru_discord._payload import DeliveryRecord, PayloadConfig
from loguru_discord.intercept import Intercept

if TYPE_CHECKING:
    from loguru import Message


@dataclass(frozen=True, slots=True)
class DeliveryStatistics:
    """Expose a consistent snapshot of terminal and pending record counts.

    Pending records include the active delivery. Failed records include accepted
    records abandoned during shutdown. Buffered bytes count UTF-8 text and level
    names of all pending records, including the active delivery.
    """

    sent: int
    failed: int
    dropped: int
    pending: int
    buffered_bytes: int


class BufferOverflowError(Exception):
    """Report a batch of newest records rejected by the admission limits."""

    def __init__(self, dropped: int) -> None:
        """Retain the number of drops since the previous overflow notification."""
        self.dropped = dropped
        super().__init__(
            f"AsyncDiscordSink buffer full: dropped {dropped} newest records"
        )


class AsyncDiscordSink(PayloadConfig):
    """Admit Loguru records without waiting for HTTP or queue capacity.

    Start with ``await sink.start()`` or an async context manager before adding
    the sink to Loguru. Use ``logger.add(sink, enqueue=False)``. One worker sends
    accepted messages in order; the newest message is dropped at either limit.
    ``logger.remove()`` initiates shutdown. Await ``aclose()`` to finish cleanup.

    Configuration shared with DiscordSink has the same formatting, suppression,
    thread, username, avatar, and request-policy semantics. The constructor does
    no network I/O or avatar file reads; avatar modification happens in start().
    Lifecycle coroutines must run on the starting event loop. Logging and stop()
    can be called from other threads.
    """

    def __init__(
        self,
        webhook_url: str,
        *,
        thread_id: str | None = None,
        username: str | None = None,
        avatar_url: str | None = None,
        avatar: UnsetType | None | str | bytes | Path = UNSET,
        rich: bool = False,
        critical_color: str | int | None = "000000",
        error_color: str | int | None = "D22D39",
        warning_color: str | int | None = "CE9C5C",
        success_color: str | int | None = "43A25A",
        info_color: str | int | None = "FFFFFF",
        debug_color: str | int | None = "5865F2",
        trace_color: str | int | None = None,
        intercept: bool = False,
        intercept_level_map: dict[str, str] | None = None,
        suppress: list[type[BaseException]] | None = None,
        request_policy: RequestPolicy | None = None,
        max_pending: int = 1000,
        max_buffer_bytes: int = 16 * 1024 * 1024,
        shutdown_timeout: float = 30.0,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Validate configuration and allocate the bounded admission buffer.

        Args:
            webhook_url: Discord webhook URL.
            thread_id: Override the URL's thread target.
            username: Per-message webhook display name.
            avatar_url: Per-message hosted avatar URL.
            avatar: Default avatar to modify asynchronously during startup.
            rich: Send Components V2 output instead of plain code blocks.
            critical_color: CRITICAL accent color, or None for no accent.
            error_color: ERROR accent color, or None for no accent.
            warning_color: WARNING accent color, or None for no accent.
            success_color: SUCCESS accent color, or None for no accent.
            info_color: INFO accent color, or None for no accent.
            debug_color: DEBUG accent color, or None for no accent.
            trace_color: TRACE accent color, or None for no accent.
            intercept: Set up standard-library interception after startup.
            intercept_level_map: Standard-library to Loguru level mapping.
            suppress: Skip records carrying these exception types or subclasses.
            request_policy: Clyde policy for delivery and avatar modification.
                None selects 5-second connection and 10-second read timeouts,
                three retries, and a 30-second transport budget. Startup also
                applies its total_timeout to avatar preparation.
            max_pending: Maximum accepted but unfinished records, including the
                active request. Must be a positive integer.
            max_buffer_bytes: Maximum UTF-8 text and level-name bytes retained
                by pending records. Must be a positive integer.
            shutdown_timeout: Positive finite graceful-shutdown budget in seconds.
                Transport cleanup is awaited after cancellation.
            on_error: Optional synchronous, out-of-band error callback, invoked
                on the owning loop outside locks. Keep it short and non-blocking.
                Drops are aggregated; delivery exceptions retain Clyde's types.
                Callback failures are reported to stderr. None reports errors
                directly to stderr.
        """
        super().__init__(
            webhook_url,
            thread_id=thread_id,
            username=username,
            avatar_url=avatar_url,
            avatar=avatar,
            rich=rich,
            critical_color=critical_color,
            error_color=error_color,
            warning_color=warning_color,
            success_color=success_color,
            info_color=info_color,
            debug_color=debug_color,
            trace_color=trace_color,
            intercept=intercept,
            intercept_level_map=intercept_level_map,
            suppress=suppress,
            request_policy=request_policy,
        )
        for name, value in (
            ("max_pending", max_pending),
            ("max_buffer_bytes", max_buffer_bytes),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (
            isinstance(shutdown_timeout, bool)
            or not isinstance(shutdown_timeout, (int, float))
            or not isfinite(shutdown_timeout)
            or shutdown_timeout <= 0
        ):
            raise ValueError("shutdown_timeout must be a finite positive number")
        if on_error is not None and not callable(on_error):
            raise TypeError("on_error must be callable or None")
        self.max_pending = max_pending
        self.max_buffer_bytes = max_buffer_bytes
        self.shutdown_timeout = shutdown_timeout
        self.on_error = on_error
        self._lock = Lock()
        self._queue: deque[tuple[int, DeliveryRecord, int]] = deque()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._state = "new"
        self._wake = asyncio.Event()
        self._start_task: asyncio.Task[None] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._abort_requested = False
        self._notify_pending = False
        self._overflow = 0
        self._accepted = self._completed = 0
        self._sent = self._failed = self._dropped = self._bytes = 0
        self._waiters: list[tuple[int, asyncio.Future[None]]] = []

    @property
    def statistics(self) -> DeliveryStatistics:
        """Return read-only counters without exposing mutable worker state."""
        with self._lock:
            return DeliveryStatistics(
                self._sent,
                self._failed,
                self._dropped,
                self._accepted - self._completed,
                self._bytes,
            )

    def _owning_loop(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            raise RuntimeError(
                "AsyncDiscordSink lifecycle requires its starting event loop"
            )
        return loop

    async def start(self) -> Self:
        """Initialize the avatar and worker, sharing concurrent startup calls.

        Startup failures and cancellation close the sink and propagate to the
        caller. A closed sink cannot be restarted.
        """
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._loop is None:
                self._loop = loop
            self._owning_loop()
            initialize = self._state == "new"
            if initialize:
                self._state = "starting"
            elif self._state not in {"starting", "running"}:
                raise RuntimeError("AsyncDiscordSink is closing or closed")
            task = self._start_task
        # Task factories can execute coroutines immediately. Do not create a
        # task under the admission lock, which initialization also needs.
        if initialize:
            task = self._start_task = loop.create_task(
                self._initialize(), context=Context()
            )
        assert task is not None
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            self._cancel_delivery()
            await self.aclose()
            raise
        return self

    async def _initialize(self) -> None:
        token = delivery_active.set(True)
        try:
            if self.avatar is not UNSET:
                async with asyncio.timeout(self.request_policy.total_timeout):
                    await self.webhook.modify_async(
                        avatar=self.avatar, request_policy=self.request_policy
                    )
            if self.intercept:
                Intercept.setup(self.intercept_level_map)
            with self._lock:
                if self._state != "starting":
                    raise RuntimeError("AsyncDiscordSink stopped during startup")
                self._state = "running"
            self._worker_task = self._owning_loop().create_task(
                self._worker(), context=Context()
            )
        except BaseException:
            with self._lock:
                self._state = "closed"
            raise
        finally:
            delivery_active.reset(token)

    def write(self, message: Message) -> None:
        """Accept a formatted Loguru message or drop the newest on overload."""
        if delivery_active.get():
            return
        raw = message.record
        exception = raw["exception"]
        if self._suppressed(exception.value if exception else None):
            return
        record = DeliveryRecord(
            str(message), raw["level"].name, raw["level"].no, datetime.now()
        )
        size = len(record.text.encode()) + len(record.level_name.encode())
        with self._lock:
            if self._state != "running":
                raise RuntimeError(
                    "AsyncDiscordSink must be started and accepting records"
                )
            loop = self._loop
            assert loop is not None
            if loop.is_closed():
                raise RuntimeError("AsyncDiscordSink owning event loop is closed")
            if (
                self._accepted - self._completed >= self.max_pending
                or self._bytes + size > self.max_buffer_bytes
            ):
                self._dropped += 1
                self._overflow += 1
            else:
                self._accepted += 1
                self._bytes += size
                self._queue.append((self._accepted, record, size))
            self._schedule_notification(loop)

    def _schedule_notification(self, loop: asyncio.AbstractEventLoop) -> None:
        # Called under the admission lock. At most one callback is queued.
        if not self._notify_pending:
            self._notify_pending = True
            loop.call_soon_threadsafe(self._notify, context=Context())

    def _notify(self) -> None:
        with self._lock:
            self._notify_pending = False
            overflow, self._overflow = self._overflow, 0
            closing = self._state == "closing"
        self._wake.set()
        if overflow:
            self._report(BufferOverflowError(overflow))
        if closing:
            self._begin_close()

    def _report(self, error: Exception) -> None:
        token = delivery_active.set(True)
        try:
            if self.on_error is None:
                message = f"AsyncDiscordSink: {type(error).__name__}: {error}\n"
            else:
                try:
                    self.on_error(error)
                except Exception as callback_error:
                    message = f"AsyncDiscordSink error callback failed: {type(callback_error).__name__}\n"
                else:
                    return
            stream = sys.stderr
            if stream is not None:
                stream.write(message)
        except Exception:
            # Diagnostic formatting and stderr writes are best-effort. They
            # must not stop delivery or prevent shutdown and completion.
            pass
        finally:
            delivery_active.reset(token)

    async def _worker(self) -> None:
        try:
            while True:
                await self._wake.wait()
                self._wake.clear()
                while True:
                    with self._lock:
                        if self._abort_requested:
                            return
                        if not self._queue:
                            if self._state == "closing":
                                return
                            break
                        sequence, record, size = self._queue.popleft()
                    token = delivery_active.set(True)
                    succeeded = False
                    try:
                        await self._payload(record).execute_async(
                            request_policy=self.request_policy
                        )
                        succeeded = True
                    except Exception as error:
                        self._report(error)
                    finally:
                        delivery_active.reset(token)
                    with self._lock:
                        self._sent += int(succeeded)
                        self._failed += int(not succeeded)
                        self._completed = sequence
                        self._bytes -= size
                    self._release_waiters()
                    del record
                    # Let producers, notifications, and drain waiters run even
                    # when a mocked or cached transport completes immediately.
                    await asyncio.sleep(0)
        finally:
            record = None
            with self._lock:
                self._state = "closed"
                self._failed += self._accepted - self._completed
                self._completed = self._accepted
                self._bytes = 0
                self._queue.clear()
            self._release_waiters()

    def _release_waiters(self) -> None:
        with self._lock:
            ready = [
                future
                for boundary, future in self._waiters
                if boundary <= self._completed
            ]
            self._waiters = [
                (boundary, future)
                for boundary, future in self._waiters
                if boundary > self._completed
            ]
        for future in ready:
            if not future.done():
                future.set_result(None)

    async def complete(self) -> None:
        """Wait for records accepted before this call starts awaiting.

        Later producers do not extend this completion boundary. Failures and
        shutdown abandonment count as terminal deliveries. Cancelling a drain
        waiter does not cancel the delivery worker.
        """
        loop = self._owning_loop()
        with self._lock:
            boundary = self._accepted
            if boundary <= self._completed:
                return
            future = loop.create_future()
            waiter = (boundary, future)
            self._waiters.append(waiter)
        try:
            await future
        finally:
            with self._lock:
                if waiter in self._waiters:
                    self._waiters.remove(waiter)

    def stop(self) -> None:
        """Stop accepting records and initiate shutdown without blocking."""
        with self._lock:
            if self._state == "new":
                self._state = "closed"
            elif self._state in {"starting", "running"}:
                self._state = "closing"
                assert self._loop is not None
                self._schedule_notification(self._loop)

    def _begin_close(self) -> None:
        if self._close_task is None:
            self._close_task = self._owning_loop().create_task(
                self._shutdown(), context=Context()
            )

    async def _shutdown(self) -> None:
        try:
            if self._start_task is not None and not self._start_task.done():
                self._cancel_task(self._start_task)
                await asyncio.gather(self._start_task, return_exceptions=True)
            if self._worker_task is not None:
                self._wake.set()
                try:
                    async with asyncio.timeout(self.shutdown_timeout):
                        await asyncio.shield(
                            asyncio.gather(self._worker_task, return_exceptions=True)
                        )
                except TimeoutError:
                    self._report(
                        TimeoutError(
                            f"Shutdown budget expired with {self.statistics.pending} pending records"
                        )
                    )
        finally:
            self._cancel_delivery()
            if self._worker_task is not None:
                await asyncio.gather(self._worker_task, return_exceptions=True)
            with self._lock:
                self._state = "closed"

    def _cancel_delivery(self) -> None:
        # Clyde may already be handling its own deadline cancellation. Keep
        # forced shutdown separate so its cleanup cannot resume queued sends.
        self._abort_requested = True
        for task in (self._start_task, self._worker_task):
            self._cancel_task(task)

    @staticmethod
    def _cancel_task(task: asyncio.Task[None] | None) -> None:
        # Repeated close/cancellation requests must not interrupt an operation
        # that is already unwinding and awaiting its transport cleanup.
        if task is not None and not task.cancelling():
            task.cancel()

    async def aclose(self) -> None:
        """Await shutdown; cancellation cancels delivery and awaits its cleanup."""
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        self._owning_loop()
        self.stop()
        if self._state == "closing":
            self._begin_close()
        if self._close_task is not None:
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError:
                self._cancel_delivery()
                await asyncio.shield(self._close_task)
                raise

    async def __aenter__(self) -> Self:
        """Start the sink on entry to an async context manager."""
        return await self.start()

    async def __aexit__(self, *exc_info: object) -> None:
        """Drain and close the sink on exit from an async context manager."""
        await self.aclose()
