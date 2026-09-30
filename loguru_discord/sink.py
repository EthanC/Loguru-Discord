"""Send Loguru records to Discord webhooks."""

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
    """Forward Loguru records to a Discord webhook.

    Add an instance to Loguru with ``logger.add(sink)``. Records are sent
    synchronously as Markdown code blocks, or as Components V2 containers
    when ``rich=True``. Use ``enqueue=True`` on ``logger.add()`` to queue
    delivery in a background thread.

    Records exceeding Discord's text limits are sent as UTF-8 ``message.txt``
    attachments containing the complete formatted record, including any
    traceback, without Markdown fences. Oversized rich records use a plain
    payload; subsequent records retain rich formatting.
    """

    def __init__(
        self: Self,
        webhook_url: str,
        *,
        thread_id: str | None = None,
        username: str | None = None,
        avatar_url: str | None = None,
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
    ) -> None:
        """
        Initialize a Discord webhook sink.

        Args:
            webhook_url (str): Discord webhook URL to forward log records to.

            thread_id (str | None): Thread within the Webhook's channel to forward log events to.
                Overrides the thread_id query parameter in the Webhook URL.
                When None, any thread_id in the URL is used. Default is None.

            username (str | None): String to use for the Webhook username.
                Default is determined by Discord.

            avatar_url (str | None): Image URL to use for the Webhook avatar.
                Default is determined by Discord.

            rich (bool): Use Discord Components V2 with a level heading,
                accent color, and timestamps instead of a plain message.
                Default is False.

            critical_color (str | int | None): CRITICAL accent color when rich is True.
                Hexadecimal string or integer; None disables the accent. Default is "000000".

            error_color (str | int | None): ERROR accent color when rich is True.
                Hexadecimal string or integer; None disables the accent. Default is "D22D39".

            warning_color (str | int | None): WARNING accent color when rich is True.
                Hexadecimal string or integer; None disables the accent. Default is "CE9C5C".

            success_color (str | int | None): SUCCESS accent color when rich is True.
                Hexadecimal string or integer; None disables the accent. Default is "43A25A".

            info_color (str | int | None): INFO accent color when rich is True.
                Hexadecimal string or integer; None disables the accent. Default is "FFFFFF".

            debug_color (str | int | None): DEBUG accent color when rich is True.
                Hexadecimal string or integer; None disables the accent. Default is "5865F2".

            trace_color (str | int | None): TRACE accent color when rich is True.
                Hexadecimal string or integer; None disables the accent. Default is None.

            intercept (bool): Route standard-library logging through Loguru by
                calling Intercept.setup(). Replaces and closes existing root
                logging handlers and sets the root logging level to 0.
                Default is False.

            intercept_level_map (dict[str, str] | None): Mapping of standard-library
                level names to Loguru level names. Used only when intercept is True.
                Unrecognized names fall back to the record's numeric level.
                Default is None.

            suppress (list[type[BaseException]] | None): Exception types whose
                records are skipped by this sink, including subclasses. Only
                records with exception information are checked; other Loguru
                sinks are unaffected. Default is None.
        """
        super().__init__()

        self.webhook_url: str = webhook_url

        self.thread_id: str | None = thread_id
        self.username: str | None = username
        self.avatar_url: str | None = avatar_url
        self.rich: bool = rich
        self.critical_color: str | int | None = critical_color
        self.error_color: str | int | None = error_color
        self.warning_color: str | int | None = warning_color
        self.success_color: str | int | None = success_color
        self.info_color: str | int | None = info_color
        self.debug_color: str | int | None = debug_color
        self.trace_color: str | int | None = trace_color
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
        Deliver a formatted record to the Discord webhook.

        Plain output allows 2,000 characters including code-block fences.
        Rich output allows 4,000 characters across the body, level heading,
        and timestamps, including Markdown formatting. Longer records become
        attachments. Matching exception types are skipped before delivery.

        Args:
            record (LogRecord): Record formatted by Loguru for webhook delivery.
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
                case logging.CRITICAL if self.critical_color is not None:
                    container.set_accent_color(self.critical_color)
                case logging.ERROR if self.error_color is not None:
                    container.set_accent_color(self.error_color)
                case logging.WARNING if self.warning_color is not None:
                    container.set_accent_color(self.warning_color)
                case 25 if self.success_color is not None:  # Loguru SUCCESS
                    container.set_accent_color(self.success_color)
                case logging.INFO if self.info_color is not None:
                    container.set_accent_color(self.info_color)
                case logging.DEBUG if self.debug_color is not None:
                    container.set_accent_color(self.debug_color)
                case 5 if self.trace_color is not None:  # Loguru TRACE
                    container.set_accent_color(self.trace_color)
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
