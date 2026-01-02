"""Define the Intercept class and its associates."""

import logging
from logging import Handler, LogRecord
from types import FrameType
from typing import Self

from loguru import logger


class Intercept(Handler):
    """Handler to intercept logging messages and redirect to Loguru."""

    level_map: dict[str, str] | None

    def __init__(self: Self, level_map: dict[str, str] | None) -> None:
        """Initialize an Intercept handler."""
        super().__init__()

        self.level_map: dict[str, str] = level_map

    def emit(self: Self, record: LogRecord):
        """Log emitter."""
        level: int | str = record.levelno
        frame: FrameType | None = logging.currentframe()
        depth: int = 2

        try:
            if self.level_map:
                for key, value in self.level_map.items():
                    if record.levelname == key:
                        record.levelname = value

            level = logger.level(record.levelname).name
        except Exception as e:
            logger.opt(exception=e).trace("Failed to determine logger intercept level")

        while (frame) and (frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back

            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

    @staticmethod
    def setup(level_map: dict[str, str] | None = None) -> None:
        """Reroute standard library logging to Loguru."""
        logging.basicConfig(handlers=[Intercept(level_map)], level=0, force=True)
