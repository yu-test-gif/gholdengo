import logging
from typing import Optional

_bot: Optional[object] = None

def set_ghouldengo_bot(bot) -> None:
    """Store bot reference for potential future use."""
    global _bot
    _bot = bot

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

_logger = logging.getLogger("ghouldengo")
if not _logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s", "%H:%M:%S")
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)

# Optional simple colorization (safe if terminal supports ANSI)
_COLORS = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[41m",
}
_RESET = "\033[0m"

def pretty_log(level: str, message: str) -> None:
    """Log a message with pretty formatting and colors."""
    lvl = _LEVELS.get(level.lower(), logging.INFO)
    color = _COLORS.get(lvl, "")
    reset = _RESET if color else ""
    _logger.log(lvl, f"{color}{message}{reset}")

__all__ = ["pretty_log", "set_ghouldengo_bot"]