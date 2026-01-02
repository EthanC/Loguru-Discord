from logging import Handler, LogRecord

from clyde import Webhook

class DiscordSink(Handler):
    webhook_url: str
    username: str | None
    avatar_url: str | None
    rich: bool
    intercept: bool
    intercept_level_map: dict[str, str] | None
    suppress: list[type[BaseException]] | None
    webhook: Webhook

    def __init__(
        self,
        webhook_url: str,
        *,
        username: str | None = None,
        avatar_url: str | None = None,
        rich: bool = False,
        intercept: bool = False,
        intercept_level_map: dict[str, str] | None = None,
        suppress: list[type[BaseException]] | None = None,
    ) -> None: ...
    def emit(self, record: LogRecord) -> None: ...
