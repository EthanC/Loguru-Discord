import logging
import traceback
from logging import Handler, LogRecord
from typing import Optional, Self

from discord_webhook import DiscordEmbed, DiscordWebhook


class DiscordSink(Handler):
    """Logging handler that enables sending logs to a Discord Webhook."""

    def __init__(
        self: Self,
        webhookUrl: str,
        *,
        username: Optional[str] = None,
        avatarUrl: Optional[str] = None,
        embed: bool = False,
        trace: bool = True,
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
            `trace` (`bool`, optional): A toggle to include tracebacks in the log message.
                Default is `True`.
        """

        super().__init__()

        self.webhookUrl: str = webhookUrl
        self.username: Optional[str] = username
        self.avatarUrl: Optional[str] = avatarUrl
        self.embed: bool = embed
        self.trace: bool = trace

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

        Ars:
            `record` (`logging.LogRecord`): Log record to send.
        """

        message: str = record.getMessage()
        details: str = "".join(traceback.format_exception(*record.exc_info))

        if (self.trace) and (record.exc_info):
            message += f"\n\n{details}"

        if not self.embed:
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

            embed.set_title(record.levelname)
            embed.set_description(f"```py\n{message[:4086]}\n```")
            embed.set_footer(
                text=f"{record.filename}:{record.lineno}",
                icon_url="https://i.imgur.com/7xeGMSf.png",
            )
            embed.set_timestamp(record.created)

            self.webhook.add_embed(embed)

        self.webhook.execute()
