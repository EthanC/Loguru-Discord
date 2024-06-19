import logging
import sys
import unittest
from logging import LogRecord
from time import sleep
from typing import Self
from unittest import TestCase

from loguru_discord import DiscordSink


class TestSink(TestCase):
    """Test case for the DiscordSink class."""

    def setUp(self: Self) -> None:
        """Prepare to run tests."""

        self.webhookUrl: str = "https://discord.com/api/webhooks/000000000000000000/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        self.testMessage: str = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."

    def test_emit(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.CRITICAL`
        Format: Default
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl)
        record: LogRecord | None = None

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

        if record:
            sink.emit(record)

    def test_emit_critical_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.CRITICAL`
        Embed: Enabled
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl, embed=True)
        record: LogRecord | None = None

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

        if record:
            sink.emit(record)

    def test_emit_error_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.ERROR`
        Username: Modified
        Embed: Enabled
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(
            self.webhookUrl, username="Custom Username", embed=True
        )
        record: LogRecord | None = None

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

        if record:
            sink.emit(record)

    def test_emit_warning_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.WARNING`
        Username: Modified
        Avatar URL: Modified
        Embed: Enabled
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(
            self.webhookUrl,
            username="Custom Avatar",
            avatarUrl="https://i.imgur.com/7xeGMSf.png",
            embed=True,
        )
        record: LogRecord | None = None

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

        if record:
            sink.emit(record)

    def test_emit_info_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.INFO`
        Embed: Enabled
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl, embed=True)
        record: LogRecord | None = None

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

        if record:
            sink.emit(record)

    def test_emit_debug_embed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.DEBUG`
        Embed: Enabled
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl, embed=True)
        record: LogRecord | None = None

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

        if record:
            sink.emit(record)

    def test_emit_embed_long(self: Self) -> None:
        """
        Test the emit method with the following conditions

        Message: Exceeds length limit
        Embed: Enabled
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl, embed=True)
        record: LogRecord | None = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_embed_long",
                logging.ERROR,
                "/tests/test_sink.py",
                1,
                self.testMessage * 25,
                None,
                sys.exc_info(),
            )

        if record:
            sink.emit(record)

    def test_emit_embed_long_truncate(self: Self) -> None:
        """
        Test the emit method with the following conditions

        Message: Exceeds length limit
        Embed: Enabled
        Truncate: Enabled
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl, embed=True, truncate=True)
        record: LogRecord | None = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_embed_long_truncate",
                logging.ERROR,
                "/tests/test_sink.py",
                1,
                self.testMessage * 25,
                None,
                sys.exc_info(),
            )

        if record:
            sink.emit(record)

    def test_emit_long(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Message: Exceeds length limit
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl)
        record: LogRecord | None = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_long",
                logging.ERROR,
                "/tests/test_sink.py",
                1,
                self.testMessage * 25,
                None,
                sys.exc_info(),
            )

        if record:
            sink.emit(record)

    def test_emit_long_truncate(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Message: Exceeds length limit
        Truncate: Enabled
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl, truncate=True)
        record: LogRecord | None = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_long_truncate",
                logging.ERROR,
                "/tests/test_sink.py",
                1,
                self.testMessage * 25,
                None,
                sys.exc_info(),
            )

        if record:
            sink.emit(record)

    def test_emit_suppressed(self: Self) -> None:
        """
        Test the emit method with the following conditions.

        Level: `logging.CRITICAL`
        Format: Default
        Suppress: ZeroDevisionError
        """

        sleep(3)

        sink: DiscordSink = DiscordSink(self.webhookUrl, suppress=[ZeroDivisionError])
        record: LogRecord | None = None

        try:
            _: float = 1 / 0
        except ZeroDivisionError:
            record = LogRecord(
                "test_emit_suppressed",
                logging.CRITICAL,
                "/tests/test_sink.py",
                1,
                "ZeroDivisionError: This Exception should not be sent to Discord.",
                None,
                sys.exc_info(),
            )

        if record:
            sink.emit(record)


if __name__ == "__main__":
    unittest.main()
