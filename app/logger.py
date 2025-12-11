"""
Structured Logging Configuration

This module sets up structured logging for the application using
Python's logging module with JSON formatting for production.
"""

import logging
import logging.config
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime,timezone

from app.config import settings


# ============================================================================
# JSON FORMATTER (Simple Implementation)
# ============================================================================

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Formats log records as JSON objects with consistent structure.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.

        Args:
            record: Log record to format

        Returns:
            str: JSON-formatted log message
        """
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        return json.dumps(log_data)


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
) -> None:
    """
    Configure application logging.

    Sets up console and file handlers with appropriate formatters.
    Uses settings from config if parameters not provided.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        log_format: Format type ('json' or 'text')
    """
    # Use settings as defaults
    log_level = log_level or settings.log_level
    log_file = log_file or settings.log_file
    log_format = log_format or settings.log_format

    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # FORMATTERS
    # ========================================================================

    # Text formatter (human-readable)
    text_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # JSON formatter (structured)
    json_formatter = JSONFormatter()

    # Choose formatter based on log_format setting
    formatter = json_formatter if log_format == "json" else text_formatter

    # ========================================================================
    # HANDLERS
    # ========================================================================

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # File handler (rotating)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Keep 5 backup files
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(json_formatter)  # Always use JSON for file

    # ========================================================================
    # ROOT LOGGER CONFIGURATION
    # ========================================================================

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add our handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # ========================================================================
    # THIRD-PARTY LOGGER LEVELS
    # ========================================================================

    # Reduce verbosity of third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Log initialization
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "log_level": log_level,
            "log_file": log_file,
            "log_format": log_format,
        },
    )


# ============================================================================
# LOGGING HELPERS
# ============================================================================

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)


def log_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    extra: Optional[dict] = None,
) -> None:
    """
    Log HTTP request with consistent format.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        extra: Additional fields to log
    """
    logger = get_logger("app.requests")

    log_data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }

    if extra:
        log_data.update(extra)

    # Log level based on status code
    if status_code >= 500:
        logger.error(f"{method} {path} - {status_code}", extra=log_data)
    elif status_code >= 400:
        logger.warning(f"{method} {path} - {status_code}", extra=log_data)
    else:
        logger.info(f"{method} {path} - {status_code}", extra=log_data)


def log_agent_action(
    agent_name: str,
    action: str,
    conversation_id: str,
    success: bool,
    duration_ms: float,
    extra: Optional[dict] = None,
) -> None:
    """
    Log agent action with consistent format.

    Args:
        agent_name: Name of the agent
        action: Action performed
        conversation_id: Conversation ID
        success: Whether action succeeded
        duration_ms: Action duration in milliseconds
        extra: Additional fields to log
    """
    logger = get_logger(f"app.agents.{agent_name}")

    log_data = {
        "agent": agent_name,
        "action": action,
        "conversation_id": conversation_id,
        "success": success,
        "duration_ms": duration_ms,
    }

    if extra:
        log_data.update(extra)

    if success:
        logger.info(f"Agent {agent_name} - {action}", extra=log_data)
    else:
        logger.error(f"Agent {agent_name} - {action} FAILED", extra=log_data)


def log_database_query(
    operation: str,
    table: str,
    duration_ms: float,
    rows_affected: int = 0,
    extra: Optional[dict] = None,
) -> None:
    """
    Log database query with consistent format.

    Args:
        operation: Operation type (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration_ms: Query duration in milliseconds
        rows_affected: Number of rows affected
        extra: Additional fields to log
    """
    logger = get_logger("app.database")

    log_data = {
        "operation": operation,
        "table": table,
        "duration_ms": duration_ms,
        "rows_affected": rows_affected,
    }

    if extra:
        log_data.update(extra)

    logger.debug(f"DB {operation} {table}", extra=log_data)


# ============================================================================
# TESTING/DEBUG
# ============================================================================

if __name__ == "__main__":
    # Setup logging
    setup_logging(log_level="DEBUG", log_format="text")

    # Test logging at different levels
    logger = get_logger(__name__)

    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")

    # Test helper functions
    log_request("GET", "/api/v1/health", 200, 15.5)
    log_agent_action("intent_classifier", "classify", "conv-123", True, 50.2)
    log_database_query("SELECT", "customers", 5.3, 1)

    # Test with exception
    try:
        raise ValueError("Test exception")
    except Exception:
        logger.exception("Exception occurred")

    print("\n✅ Logging test complete. Check logs/app.log")
