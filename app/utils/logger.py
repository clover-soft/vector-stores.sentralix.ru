import logging
import os
from pathlib import Path

from config import Config
from utils.request_context import get_request_id


_log_record_factory_configured = False


def _configure_log_record_factory() -> None:
    global _log_record_factory_configured

    if _log_record_factory_configured:
        return

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = get_request_id()
        return record

    logging.setLogRecordFactory(record_factory)
    _log_record_factory_configured = True


def configure_logging(config: Config) -> logging.Logger:
    _configure_log_record_factory()

    handlers: list[logging.Handler] = []

    formatter = logging.Formatter(config.log_format)

    if config.log_file:
        log_path = Path(config.log_file)
        if log_path.parent:
            os.makedirs(log_path.parent, exist_ok=True)
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    if config.log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(config.log_level.upper())

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    for handler in handlers:
        root_logger.addHandler(handler)

    return logging.getLogger("vector-stores")
