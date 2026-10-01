import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from clyde import RequestPolicy
from loguru import Message
from msgspec import UNSET, UnsetType

from loguru_discord._payload import DeliveryRecord, PayloadConfig

@dataclass(frozen=True, slots=True)
class DeliveryStatistics:
    sent: int
    failed: int
    dropped: int
    pending: int
    buffered_bytes: int

class BufferOverflowError(Exception):
    dropped: int
    def __init__(self, dropped: int) -> None: ...

class AsyncDiscordSink(PayloadConfig):
    max_pending: int
    max_buffer_bytes: int
    shutdown_timeout: float
    on_error: Callable[[Exception], None] | None
    _queue: deque[tuple[int, DeliveryRecord, int]]
    _worker_task: asyncio.Task[None] | None
    _waiters: list[tuple[int, asyncio.Future[None]]]

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
    ) -> None: ...
    @property
    def statistics(self) -> DeliveryStatistics: ...
    async def start(self) -> Self: ...
    def write(self, message: Message) -> None: ...
    async def complete(self) -> None: ...
    def stop(self) -> None: ...
    async def aclose(self) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc_info: object) -> None: ...
