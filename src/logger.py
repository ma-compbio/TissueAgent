import logging
from pathlib import Path
import colorama
from colorama import Fore, Style
from typing import Optional, Union

from config import LOG_TO_TERMINAL, LOG_TO_FILE

colorama.init(autoreset=True)

class LoggingFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG:    Fore.CYAN,
        logging.INFO:     Fore.GREEN,
        logging.WARNING:  Fore.YELLOW,
        logging.ERROR:    Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def __init__(self, datefmt: Optional[str] = None):
        super().__init__(fmt=None, datefmt=datefmt)

    def format(self, record):
        ts    = self.formatTime(record, self.datefmt)
        lvl   = record.levelname
        color = self.COLORS.get(record.levelno, "")
        reset = Style.RESET_ALL if color else ""
        padded_lvl = f"{color}{lvl}{reset}" + " " * (8 - len(lvl))
        header = f"{ts} | {padded_lvl} | "
        msg    = record.getMessage()
        out    = header + msg
        if record.exc_info:
            out = out.rstrip("\n") + "\n" + self.formatException(record.exc_info)
        return out

def setup_logging(
    *,
    level: int = logging.INFO,
    datefmt: str = '%Y-%m-%d %H:%M:%S',
    log_to_terminal: bool = LOG_TO_TERMINAL,
    log_to_file: Optional[Union[Path, str]] = LOG_TO_FILE,
):
    root = logging.getLogger()
    root.setLevel(level)
    # clear any pre-existing handlers
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
