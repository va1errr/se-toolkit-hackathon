"""Structured logging configuration using structlog.

Configures structlog to output JSON-formatted logs with:
- Timestamp
- Log level
- Logger name
- All contextual key-value pairs

Usage:
    from app.services.logging import setup_logging
    setup_logging()

    import structlog
    logger = structlog.get_logger()
    logger.info("Something happened", user_id="abc", action="login")
"""

import logging
import sys

import structlog


def setup_logging() -> None:
    """Configure structlog for the entire application.

    In development: pretty-printed colored output
    In production: JSON format for log aggregation tools
    """
    # Determine if we're in production
    is_prod = __import__("os").environ.get("APP_ENV") == "production"

    if is_prod:
        # Production: JSON output
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: pretty console output with colors
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure the standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
