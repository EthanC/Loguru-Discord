"""Define the DiscordSink class and its associates."""

import logging
from datetime import datetime
from logging import Handler, LogRecord
from typing import Self

from clyde import Markdown, Timestamp, Webhook
from clyde.components import Container, Seperator, SeperatorSpacing, TextDisplay

from loguru_discord.intercept import Intercept


class DiscordSink(Handler):
    """Represent a DiscordSink object."""

    def __init__(
        self: Self,
        webhook_url: str,
        *,
        username: str | None = None,
        avatar_url: str | None = None,
        rich: bool = False,
        intercept: bool = False,
        suppress: list[type[BaseException]] | None = None,
    ) -> None:
        """
        Initialize a DiscordSink object.

        Arguments:
            webhook_url (str): Discord Webhook to forward log events to.

            username (str | None): String to use for the Webhook username.
                Default is determined by Discord.

            avatar_url (str | None): Image URL to use for the Webhook avatar.
                Default is determined by Discord.

            rich (bool): Toggle whether to use Discord Components.
                Default is False.

            suppress (list[type[BaseException]] | None): List of Exception]
                types to not forward to Discord. Default is None.
        """
        super().__init__()

        self.webhook_url: str = webhook_url

        self.username: str | None = username
        self.avatar_url: str | None = avatar_url
        self.rich: bool = rich
        self.intercept: bool = intercept
        self.suppress: list[type[BaseException]] | None = suppress
        self.webhook: Webhook = Webhook(url=self.webhook_url)

        if self.username:
            self.webhook.set_username(self.username)

        if self.avatar_url:
            self.webhook.set_avatar_url(self.avatar_url)

        if self.intercept:
            Intercept.setup()

    def emit(self: Self, record: LogRecord) -> None:
        """
        Emit the log record to the Discord Webhook instance.

        Arguments:
            record (LogRecord): Log record to forward to the Webhook.
        """
        if self.suppress and record.exc_info:
            if isinstance(record.exc_info[1], tuple(self.suppress)):
                return

        body: str = Markdown.code_block(record.getMessage())

        if self.rich:
            timestamp: datetime = datetime.now()
            container: Container = Container(
                components=[
                    TextDisplay(content=Markdown.header_3(record.levelname)),
                    TextDisplay(content=body),
                    Seperator(divider=True, spacing=SeperatorSpacing.SMALL),
                    TextDisplay(
                        content=Markdown.subtext(
                            f"{Timestamp.long_date_time(timestamp)} ({Timestamp.relative_time(timestamp)})"
                        )
                    ),
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

            self.webhook.add_component(container)
        else:
            self.webhook.set_content(
                Markdown.code_block(record.getMessage()), fallback=True
            )

        self.webhook.execute()
