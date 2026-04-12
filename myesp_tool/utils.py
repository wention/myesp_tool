import functools
import logging
import os
from logging.handlers import RotatingFileHandler

from PyQt5.QtCore import QStandardPaths

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def setup_file_logging():
    """在 root logger 上添加 RotatingFileHandler，同步写入日志文件。

    必须在 QApplication 创建之后调用（QStandardPaths 依赖 QCoreApplication）。
    """
    log_path = "myesp_tool.log"

    try:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(handler)
        logging.getLogger().info("Log file: %s", log_path)
    except (OSError, PermissionError):
        logging.getLogger().warning("Could not create log file at %s", log_path)


def log_exception(func):
    """装饰器：捕获异常并记录完整 traceback 到日志，然后重新抛出。"""
    logger = logging.getLogger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("Unhandled exception in %s", func.__qualname__)
            raise

    return wrapper
