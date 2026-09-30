"""Define the DiscordSink class and its associates."""

import logging
from copy import deepcopy
from datetime import datetime
from logging import Handler, LogRecord
from typing import Final, Self

from clyde import Markdown, Timestamp, Webhook
from clyde.components import Container, Seperator, SeperatorSpacing, TextDisplay
from clyde.webhook import MessageFlags
from msgspec import UNSET

from loguru_discord._delivery import delivery_active
from loguru_discord.intercept import Intercept

_PLAIN_TEXT_LIMIT: Final[int] = 2000
_RICH_TEXT_LIMIT: Final[int] = 4000


class DiscordSink(Handler):
    """Represent a DiscordSink object."""

    def __init__(
        self: Self,
        webhook_url: str,
        *,
        thread_id: str | None = None,
        username: str | None = None,
        avatar_url: str | None = None,
        rich: bool = False,
        intercept: bool = False,
        intercept_level_map: dict[str, str] | None = None,
        suppress: list[type[BaseException]] | None = None,
    ) -> None:
        """
        Initialize a DiscordSink object.

        Arguments:
            webhook_url (str): Discord Webhook to forward log events to.

            thread_id (str | None): Thread within the Webhook's channel to forward log events to.
                Overrides the thread_id query parameter in the Webhook URL.
                Default is None.

            username (str | None): String to use for the Webhook username.
                Default is determined by Discord.

            avatar_url (str | None): Image URL to use for the Webhook avatar.
                Default is determined by Discord.

            rich (bool): Toggle whether to use Discord Components.
                Default is False.

            intercept (bool): Toggle whether to intercept the standard logging library.
                Default is False.

            intercept_level_map (dict[str, str] | None): Mapping of custom levels to Loguru levels.
                Default is None.

            suppress (list[type[BaseException]] | None): List of Exception]
                types to not forward to Discord. Default is None.
        """
        super().__init__()

        self.webhook_url: str = webhook_url

        self.thread_id: str | None = thread_id
        self.username: str | None = username
        self.avatar_url: str | None = avatar_url
        self.rich: bool = rich
        self.intercept: bool = intercept
        self.intercept_level_map: dict[str, str] | None = intercept_level_map
        self.suppress: list[type[BaseException]] | None = suppress
        self.webhook: Webhook = Webhook(url=self.webhook_url)

        if self.thread_id is not None:
            self.webhook.set_thread_id(self.thread_id)

        if self.username:
            self.webhook.set_username(self.username)

        if self.avatar_url:
            self.webhook.set_avatar_url(self.avatar_url)

        if self.intercept:
            Intercept.setup(self.intercept_level_map)

    def emit(self: Self, record: LogRecord) -> None:
        """
        Emit the log record to the Discord Webhook instance.

        Arguments:
            record (LogRecord): Log record to forward to the Webhook.
        """
        if self.suppress and record.exc_info:
            if isinstance(record.exc_info[1], tuple(self.suppress)):
                return

        message: str = record.getMessage()
        body: str = Markdown.code_block(message)
        webhook: Webhook = deepcopy(self.webhook)

        if self.rich:
            timestamp: datetime = datetime.now()
            heading: str = Markdown.header_3(record.levelname)
            footer: str = Markdown.subtext(
                f"{Timestamp.long_date_time(timestamp)} ({Timestamp.relative_time(timestamp)})"
            )
            container: Container = Container(
                components=[
                    TextDisplay(content=heading),
                    TextDisplay(content=body),
                    Seperator(divider=True, spacing=SeperatorSpacing.SMALL),
                    TextDisplay(content=footer),
                ]
            )

            match record.levelno:
                case logging.CRITICAL:
                    container.set_accent_color("000000")
                case logging.ERROR:
                    container.set_accent_color("D22D39")
                case logging.WARNING:
                    container.set_accent_color("CE9C5C")
                case 25:  # Loguru SUCCESS
                    container.set_accent_color("43A25A")
                case logging.INFO:
                    container.set_accent_color("FFFFFF")
                case logging.DEBUG:
                    container.set_accent_color("5865F2")
                case _:
                    pass

            if len(heading) + len(body) + len(footer) <= _RICH_TEXT_LIMIT:
                webhook.add_component(container)
            else:
                webhook.components = UNSET
                webhook.set_flag(MessageFlags.IS_COMPONENTS_V2, None)
                webhook._remove_query_param("with_components")
                webhook.add_attachment("message.txt", message.encode())
        elif len(body) > _PLAIN_TEXT_LIMIT:
            webhook.add_attachment("message.txt", message.encode())
        else:
            webhook.set_content(body)

        token = delivery_active.set(True)
        try:
            webhook.execute()
        finally:
            delivery_active.reset(token)
