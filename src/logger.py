"""Centralized logging configuration for TissueAgent.

Provides a color-coded console formatter and a single ``setup_logging``
function that configures the root logger with optional terminal and file
handlers.  Logging destinations are controlled by the ``LOG_TO_TERMINAL``
and ``LOG_TO_FILE`` settings in :mod:`config`.

Usage::

    from logger import logger

    logger.info("Processing dataset %s", dataset_name)

The module calls ``setup_logging()`` at import time so that any module
importing ``logger`` gets a fully configured logger instance.
"""

import logging
from pathlib import Path
import colorama
from colorama import Fore, Style
from typing import Optional, Union

from config import LOG_TO_TERMINAL, LOG_TO_FILE

colorama.init(autoreset=True)


class LoggingFormatter(logging.Formatter):
    """A :class:`logging.Formatter` that colorizes output by log level.

    Each log level is mapped to a ``colorama`` foreground color (e.g. green
    for INFO, red for ERROR).  The formatted line has the structure::

        <timestamp> | <LEVEL>   | <message>
    """

    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def __init__(self, datefmt: Optional[str] = None) -> None:
        """Create a new color-coded formatter.

        Args:
            datefmt: Optional :func:`time.strftime` format string for
                timestamps.  Defaults to the parent class behaviour when
                ``None``.
        """
        super().__init__(fmt=None, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format *record* with a colored level name and timestamp header.

        Args:
            record: The log record to format.

        Returns:
            A string containing the colorized, timestamped log line with a
            trailing newline.
        """
        ts = self.formatTime(record, self.datefmt)
        lvl = record.levelname
        color = self.COLORS.get(record.levelno, "")
        reset = Style.RESET_ALL if color else ""
        padded_lvl = f"{color}{lvl}{reset}" + " " * (8 - len(lvl))
        header = f"{ts} | {padded_lvl} | "
        msg = record.getMessage()
        out = header + msg
        if record.exc_info:
            out = out.rstrip("\n") + "\n" + self.formatException(record.exc_info)
        return out + "\n"


def setup_logging(
    *,
    level: int = logging.INFO,
    datefmt: str = "%Y-%m-%d %H:%M:%S",
    log_to_terminal: bool = LOG_TO_TERMINAL,
    log_to_file: Optional[Union[Path, str]] = LOG_TO_FILE,
) -> None:
    """Configure the root logger with console and/or file handlers.

    Clears any existing handlers on the root logger and attaches new ones
    based on the provided flags.

    Args:
        level: Minimum logging level (e.g. ``logging.INFO``).
        datefmt: :func:`time.strftime` format string for log timestamps.
        log_to_terminal: If ``True``, attach a :class:`~logging.StreamHandler`
            that writes colorized output to stderr.
        log_to_file: If not ``None``, attach a :class:`~logging.FileHandler`
            that writes to the given path.  Parent directories are created
            automatically.
    """
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    formatter = LoggingFormatter(datefmt=datefmt)

    if log_to_terminal:
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

    if log_to_file:
        path = Path(log_to_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_h = logging.FileHandler(path)
        file_h.setLevel(level)
        file_h.setFormatter(formatter)
        root.addHandler(file_h)


setup_logging()
logger = logging.getLogger(__name__)
