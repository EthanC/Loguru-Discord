"""Route standard-library logging records through Loguru."""

import logging
from logging import Handler, LogRecord
from types import FrameType
from typing import Self

from loguru import logger

from loguru_discord._delivery import delivery_active


class Intercept(Handler):
    """Forward standard-library logging records to Loguru's configured sinks.

    Recognized Loguru level names are used directly after applying
    ``level_map``. Unrecognized names fall back to the record's numeric level.
    Caller location and exception information are preserved. Records emitted
    during webhook delivery are ignored to prevent recursive logging.

    Attributes:
        level_map (dict[str, str] | None): Mapping from standard-library level
            names to Loguru level names. None leaves level names unchanged.
    """

    level_map: dict[str, str] | None

    def __init__(self: Self, level_map: dict[str, str] | None) -> None:
        """Initialize a handler with an optional level-name mapping.

        Args:
            level_map (dict[str, str] | None): Mapping from standard-library
                level names to Loguru level names. Pass None for no mapping.
        """
        super().__init__()

        self.level_map: dict[str, str] | None = level_map

    def handle(self: Self, record: LogRecord) -> bool:
        """Ignore delivery logs before acquiring the standard-library handler lock."""
        if delivery_active.get():
            return False
        return super().handle(record)

    def emit(self: Self, record: LogRecord) -> None:
        """Forward a record to Loguru unless webhook delivery is active.

        Args:
            record (LogRecord): Standard-library logging record to forward.
        """
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

        while frame and (
            depth == 0 or frame.f_code.co_filename in {logging.__file__, __file__}
        ):
            frame = frame.f_back

            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

    @staticmethod
    def setup(level_map: dict[str, str] | None = None) -> None:
        """Replace the root logging handlers with an Intercept handler.

        Calls logging.basicConfig() with force=True, removing and closing
        existing root handlers, and sets the root logging level to 0. Named
        loggers retain their own levels and handlers; their records must
        propagate to the root logger to reach this handler. Configure this
        once during application startup.

        Args:
            level_map (dict[str, str] | None): Mapping from standard-library
                level names to Loguru level names. Unrecognized names fall
                back to numeric levels. Default is None.
        """
        logging.basicConfig(handlers=[Intercept(level_map)], level=0, force=True)
