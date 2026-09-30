"""Define the Intercept class and its associates."""

import logging
from logging import Handler, LogRecord
from types import FrameType
from typing import Self

from loguru import logger

from loguru_discord._delivery import delivery_active


class Intercept(Handler):
    """Handler to intercept logging messages and redirect to Loguru."""

    level_map: dict[str, str] | None

    def __init__(self: Self, level_map: dict[str, str] | None) -> None:
        """Initialize an Intercept handler."""
        super().__init__()

        self.level_map: dict[str, str] | None = level_map

    def emit(self: Self, record: LogRecord) -> None:
        """Log emitter."""
        if delivery_active.get():
            return

        level_name: str = (
            self.level_map.get(record.levelname, record.levelname)
            if self.level_map
            else record.levelname
        )
        level: int | str
        frame: FrameType | None = logging.currentframe()
        depth: int = 0

        try:
            level = logger.level(level_name).name
        except ValueError:
            level = record.levelno

        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back

            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

    @staticmethod
    def setup(level_map: dict[str, str] | None = None) -> None:
        """Reroute standard library logging to Loguru."""
        logging.basicConfig(handlers=[Intercept(level_map)], level=0, force=True)
