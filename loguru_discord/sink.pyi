from logging import Handler, LogRecord
from pathlib import Path

from clyde import Webhook
from msgspec import UNSET, UnsetType

class DiscordSink(Handler):
    webhook_url: str
    thread_id: str | None
    username: str | None
    avatar_url: str | None
    avatar: UnsetType | None | str | bytes | Path
    rich: bool
    critical_color: str | int | None
    error_color: str | int | None
    warning_color: str | int | None
    success_color: str | int | None
    info_color: str | int | None
    debug_color: str | int | None
    trace_color: str | int | None
    intercept: bool
    intercept_level_map: dict[str, str] | None
    suppress: list[type[BaseException]] | None
    webhook: Webhook

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
    ) -> None: ...
    def emit(self, record: LogRecord) -> None: ...
