"""
Lightweight sink for Loguru that sends logs to Discord via webhook.

https://github.com/EthanC/Loguru-Discord
"""

from .sink import DiscordSink

__all__: list[str] = ["DiscordSink"]
