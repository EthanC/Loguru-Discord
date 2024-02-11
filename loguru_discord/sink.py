import logging
from logging import Handler, LogRecord
from typing import Any, Self

from discord_webhook import DiscordEmbed, DiscordWebhook


class DiscordSink(Handler):
    """Logging handler that enables sending logs to a Discord Webhook."""

    def __init__(
        self: Self,
        webhookUrl: str,
        *,
        username: str | None = None,
        avatarUrl: str | None = None,
        embed: bool = False,
        suppress: list[Any] = [],
    ) -> None:
        """
        Initialize a DiscordSink instance.

        Args:
            webhookUrl (str): Discord Webhook URL to write log messages to.

            `username` (`str`, optional): Username to use for the Webhook message.
                Default is `None` (determined by Discord.)
            `avatarUrl` (`str`, optional): Image URL to use for the Webhook avatar.
                Default is `None` (determined by Discord.)
            `embed` (`bool`, optional): A toggle to use the Discord Embed format.
                Default is `False`.
            `suppress` (`list`, optional): An array of Exception types to ignore.
                Default is empty.
        """

        super().__init__()

        self.webhookUrl: str = webhookUrl
        self.username: str | None = username
        self.avatarUrl: str | None = avatarUrl
        self.embed: bool = embed
        self.suppress: list[Any] = suppress

        self.webhook: DiscordWebhook = DiscordWebhook(
            self.webhookUrl,
            username=self.username,
            avatar_url=self.avatarUrl,
            rate_limit_retry=True,
        )

    def emit(self: Self, record: LogRecord) -> None:
        """
        Override the emit method of the logging handler, sends the log
        to a Discord Webhook.

        Log message length will be trimmed according to limitations
        imposed by Discord. See documentation for more information.
        - Messages: https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params
        - Embeds: https://discord.com/developers/docs/resources/channel#embed-object-embed-limits

        Args:
            `record` (`logging.LogRecord`): Log record to send.
        """

        try:
            # Get Exception type from exc_info tuple
            if record.exc_info[0] in self.suppress:
                return
        except Exception:
            pass

        message: str = record.getMessage()

        if not self.embed:
            # Content value is restricted to defined character limit.
            self.webhook.set_content(f"```py\n{message[:1990]}\n```")
        else:
            embed: DiscordEmbed = DiscordEmbed()

            match record.levelno:
                case logging.CRITICAL:
                    embed.set_color("000000")
                case logging.ERROR:
                    embed.set_color("F23F42")
                case logging.WARNING:
                    embed.set_color("BF861C")
                case 25:  # Loguru SUCCESS
                    embed.set_color("23A559")
                case logging.INFO:
                    embed.set_color("FFFFFF")
                case logging.DEBUG:
                    embed.set_color("5865F2")
                case _:
                    pass

            # Field values are restricted to defined character limits.
            # https://discord.com/developers/docs/resources/channel#embed-object-embed-limits
            embed.set_title(record.levelname[:256])
            embed.set_description(f"```py\n{message[:4086]}\n```")
            embed.set_footer(
                text=f"{record.filename[:2040]}:{record.lineno:,}",
                icon_url="https://i.imgur.com/7xeGMSf.png",
            )
            embed.set_timestamp(record.created)

            self.webhook.add_embed(embed)

        self.webhook.execute()
