from logging import Handler, LogRecord
from typing import Any

from discord_webhook import DiscordWebhook

class DiscordSink(Handler):
    webhookUrl: str
    username: str | None
    avatarUrl: str | None
    embed: bool
    truncate: bool
    suppress: list[Any]
    webhook: DiscordWebhook

    def __init__(
        self,
        webhookUrl: str,
        *,
        username: str | None = None,
        avatarUrl: str | None = None,
        embed: bool = False,
        truncate: bool = False,
        suppress: list[Any] = [],
    ) -> None: ...
    def emit(self, record: LogRecord) -> None: ...
