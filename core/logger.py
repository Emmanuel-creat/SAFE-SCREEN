import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class Logger:
    _instance: "Logger | None" = None
    _logger: logging.Logger | None = None

    def __new__(cls, log_dir: Path | None = None) -> "Logger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._setup(log_dir or Path.home() / ".screenguard")
        return cls._instance

    @classmethod
    def _setup(cls, log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        cls._logger = logging.getLogger("screenguard")
        cls._logger.setLevel(logging.DEBUG)
        if not cls._logger.handlers:
            handler = RotatingFileHandler(
                log_dir / "screenguard.log",
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setLevel(logging.DEBUG)
            fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(fmt)
            cls._logger.addHandler(handler)

    @classmethod
    def get(cls) -> logging.Logger:
        if cls._logger is None:
            cls()
        return cls._logger  # type: ignore
