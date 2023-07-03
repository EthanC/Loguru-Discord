import logging
import sys
import unittest
from logging import LogRecord
from typing import Optional, Self
from unittest import TestCase

from loguru_discord import DiscordSink


class TestSink(TestCase):
    """Test case for the DiscordSink class."""

    def setUp(self) -> None:
        """Prepare to run tests."""

        self.webhookUrl: str = "https://discord.com/api/webhooks/000000000000000000/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        self.testMessage: str = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."

    def test_emit(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.CRITICAL`
        Format: Default
        """

        sink: DiscordSink = DiscordSink(self.webhookUrl)
        record: Optional[LogRecord] = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit",
                logging.CRITICAL,
                "/tests/test_sink.py",
                1,
                self.testMessage,
                None,
                sys.exc_info(),
            )

        sink.emit(record)

    def test_emit_critical_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.CRITICAL`
        Embed: Enabled
        """

        sink: DiscordSink = DiscordSink(self.webhookUrl, embed=True)
        record: Optional[LogRecord] = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_critical_embed",
                logging.CRITICAL,
                "/tests/test_sink.py",
                1,
                self.testMessage,
                None,
                sys.exc_info(),
            )

        sink.emit(record)

    def test_emit_error_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.ERROR`
        Username: Modified
        Embed: Enabled
        """

        sink: DiscordSink = DiscordSink(
            self.webhookUrl, username="Custom Username", embed=True
        )
        record: Optional[LogRecord] = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_error_embed",
                logging.ERROR,
                "/tests/test_sink.py",
                1,
                self.testMessage,
                None,
                sys.exc_info(),
            )

        sink.emit(record)

    def test_emit_warning_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.WARNING`
        Username: Modified
        Avatar URL: Modified
        Embed: Enabled
        """

        sink: DiscordSink = DiscordSink(
            self.webhookUrl,
            username="Custom Avatar",
            avatarUrl="https://i.imgur.com/7xeGMSf.png",
            embed=True,
        )
        record: Optional[LogRecord] = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_warning_embed",
                logging.WARNING,
                "/tests/test_sink.py",
                1,
                self.testMessage,
                None,
                sys.exc_info(),
            )

        sink.emit(record)

    def test_emit_info_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.INFO`
        Embed: Enabled
        """

        sink: DiscordSink = DiscordSink(self.webhookUrl, embed=True)
        record: Optional[LogRecord] = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_info_embed",
                logging.INFO,
                "/tests/test_sink.py",
                1,
                self.testMessage,
                None,
                sys.exc_info(),
            )

        sink.emit(record)

    def test_emit_debug_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.DEBUG`
        Embed: Enabled
        """

        sink: DiscordSink = DiscordSink(self.webhookUrl, embed=True)
        record: Optional[LogRecord] = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_debug_embed",
                logging.DEBUG,
                "/tests/test_sink.py",
                1,
                self.testMessage,
                None,
                sys.exc_info(),
            )

        sink.emit(record)


if __name__ == "__main__":
    unittest.main()
