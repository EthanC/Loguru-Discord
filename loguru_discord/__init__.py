"""
A lightweight sink for Loguru that forwards logs to Discord via the Webhook API.

https://github.com/EthanC/Loguru-Discord
"""

from loguru_discord.sink import DiscordSink

__all__: list[str] = ["DiscordSink"]
