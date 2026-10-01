"""Send Loguru records to Discord webhooks."""

from datetime import datetime
from logging import Handler, LogRecord
from pathlib import Path
from typing import Self

from clyde import RequestPolicy
from msgspec import UNSET, UnsetType

from loguru_discord._delivery import delivery_active
from loguru_discord._payload import DeliveryRecord, PayloadConfig
from loguru_discord.intercept import Intercept


class DiscordSink(PayloadConfig, Handler):
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

            avatar_url (str | None): Image URL to override the avatar on each log
                message. Takes precedence over the Webhook's default avatar.
                None uses the default avatar. Default is None.

            avatar (UnsetType | None | str | bytes | Path): Default Webhook avatar
                as an image data URI, PNG/JPEG/GIF bytes, or pathlib.Path to an
                image file. Passed to Clyde's Webhook.modify() once during
                initialization, making an HTTP request that changes the Webhook
                for all senders. None clears the default avatar; UNSET leaves
                it unchanged. Default is UNSET.

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

            request_policy (RequestPolicy | None): Clyde transport limits for
                delivery and avatar modification. None selects five-second
                connection and ten-second read timeouts, three rate-limit retries,
                and a 30-second transport budget.
        """
        Handler.__init__(self)
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

        if self.avatar is not UNSET:
            token = delivery_active.set(True)
            try:
                self.webhook.modify(
                    avatar=self.avatar, request_policy=self.request_policy
                )
            finally:
                delivery_active.reset(token)

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
        if self._suppressed(record.exc_info[1] if record.exc_info else None):
            return
        webhook = self._payload(
            DeliveryRecord(
                record.getMessage(), record.levelname, record.levelno, datetime.now()
            )
        )

        token = delivery_active.set(True)
        try:
            webhook.execute(request_policy=self.request_policy)
        finally:
            delivery_active.reset(token)
