"""
A lightweight sink for Loguru that forwards logs to Discord via the Webhook API.

https://github.com/EthanC/Loguru-Discord
"""

from loguru_discord.async_sink import (
    AsyncDiscordSink,
    BufferOverflowError,
    DeliveryStatistics,
)
from loguru_discord.intercept import Intercept
from loguru_discord.sink import DiscordSink

__all__: list[str] = [
    "Intercept",
    "DiscordSink",
    "AsyncDiscordSink",
    "BufferOverflowError",
    "DeliveryStatistics",
]
