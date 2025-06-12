import sys
from pathlib import Path
from loguru import logger


def setup_logging(
    log_path: str = "logs", retention: str = "1 week", rotation: str = "100 MB"
):
    """Configure Loguru logging with advanced settings.

    Args:
        log_path (str): Directory path for log files
        retention (str): How long to keep log files
        rotation (str): When to rotate log files
    """
    # Ensure log directory exists
    Path(log_path).mkdir(exist_ok=True)

    # Remove default handler
    logger.remove()

    # Add console handler with custom format
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # Add file handler for all logs
    logger.add(
        f"{log_path}/app.log",
        rotation=rotation,
        retention=retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        encoding="utf-8",
    )

    # Add file handler for errors only
    logger.add(
        f"{log_path}/error.log",
        rotation=rotation,
        retention=retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        encoding="utf-8",
    )

    # Configure exception handling
    logger.add(
        f"{log_path}/critical.log",
        rotation=rotation,
        retention=retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="CRITICAL",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    return logger


# Context manager for timing operations
from contextlib import contextmanager
from time import time


@contextmanager
def log_time(name: str = "Operation"):
    """Context manager to log operation execution time.

    Args:
        name (str): Name of the operation being timed

    Example:
        with log_time("Data Processing"):
            process_data()
    """
    start = time()
    try:
        yield
    finally:
        elapsed = time() - start
        logger.info(f"{name} completed in {elapsed:.2f} seconds")


# Custom exception handler
import functools


def log_exceptions(func):
    """Decorator to automatically log exceptions.

    Example:
        @log_exceptions
        def risky_operation():
            ...
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Exception in {func.__name__}: {str(e)}")
            raise

    return wrapper
