import logging
import sys
import unittest
from logging import LogRecord
from typing import Final
from unittest import TestCase

from environs import env
from loguru import logger

from loguru_discord import DiscordSink

TEST_MESSAGE: Final[str] = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
)
TESTS_WEBHOOK_URL: Final[str] = env.url("TESTS_WEBHOOK_URL").geturl()


def test_emit() -> None:
    """
    A test-case to validate a critical log is caught and forwarded to Discord.
    """
    handler_id: int = logger.add(DiscordSink(TESTS_WEBHOOK_URL), backtrace=False)

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).critical(TEST_MESSAGE)

    logger.remove(handler_id)


def test_emit_critical_rich() -> None:
    """
    A test-case to validate a critical log is caught and forwarded to Discord
    with rich formatting.
    """
    handler_id: int = logger.add(
        DiscordSink(TESTS_WEBHOOK_URL, rich=True), backtrace=False
    )

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).critical(TEST_MESSAGE)

    logger.remove(handler_id)


def test_emit_error_rich() -> None:
    """
    A test-case to validate an error log is caught and forwarded to Discord
    with rich formatting.
    """
    handler_id: int = logger.add(
        DiscordSink(TESTS_WEBHOOK_URL, username="Custom Username", rich=True),
        backtrace=False,
    )

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).error(TEST_MESSAGE)

    logger.remove(handler_id)


def test_emit_warning_rich() -> None:
    """
    A test-case to validate a warning log is caught and forwarded to Discord
    with rich formatting.
    """
    handler_id: int = logger.add(
        DiscordSink(
            TESTS_WEBHOOK_URL,
            username="Custom Avatar",
            avatar_url="https://i.imgur.com/7xeGMSf.png",
            rich=True,
        ),
        backtrace=False,
    )

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).warning(TEST_MESSAGE)

    logger.remove(handler_id)


def test_emit_info_rich() -> None:
    """
    A test-case to validate an info log is caught and forwarded to Discord
    with rich formatting.
    """
    handler_id: int = logger.add(
        DiscordSink(TESTS_WEBHOOK_URL, rich=True), backtrace=False
    )

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).info(TEST_MESSAGE)

    logger.remove(handler_id)


def test_emit_debug_rich() -> None:
    """
    A test-case to validate a debug log is caught and forwarded to Discord
    with rich formatting.
    """
    handler_id: int = logger.add(
        DiscordSink(TESTS_WEBHOOK_URL, rich=True), backtrace=False
    )

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).debug(TEST_MESSAGE)

    logger.remove(handler_id)


def test_emit_rich_long() -> None:
    """
    A test-case to validate an excessively-long log is caught and forwarded to
    Discord with rich formatting.
    """
    handler_id: int = logger.add(
        DiscordSink(TESTS_WEBHOOK_URL, rich=True), backtrace=False
    )

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).error(TEST_MESSAGE * 5)

    logger.remove(handler_id)


def test_emit_long() -> None:
    """
    A test-case to validate an excessively-long log is caught and forwarded to
    Discord.
    """
    handler_id: int = logger.add(DiscordSink(TESTS_WEBHOOK_URL), backtrace=False)

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).error(TEST_MESSAGE * 25)

    logger.remove(handler_id)


def test_emit_suppressed() -> None:
    """
    A test-case to validate an Exception of a suppressed type is not forwarded
    to Discord.
    """
    handler_id: int = logger.add(
        DiscordSink(TESTS_WEBHOOK_URL, suppress=[ZeroDivisionError]), backtrace=False
    )

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logger.opt(exception=e).critical("Exception should not be forwarded to Discord")

    logger.remove(handler_id)


def test_emit_intercept() -> None:
    """
    A test-case to validate the use of standard logging library interception
    catches and forwards an event to Discord.
    """
    handler_id: int = logger.add(
        DiscordSink(TESTS_WEBHOOK_URL, intercept=True), backtrace=False
    )

    try:
        _: float = 1 / 0
    except ZeroDivisionError as e:
        logging.error(TEST_MESSAGE)

    logger.remove(handler_id)
