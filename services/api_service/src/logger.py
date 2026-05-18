# Structured logging setup

import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4

import flask


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging
    
    Useful for:
    - Log aggregation systems (ELK, Splunk, DataDog)
    - Searching and filtering logs
    - Metrics and alerting
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Convert log record to JSON string"""
        
        # Build log object
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields (from logger.info(..., extra={...}))
        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id
        
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        
        # Add any additional extra fields
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        
        return json.dumps(log_obj)


class TextFormatter(logging.Formatter):
    """Format log records as human-readable text"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Convert log record to formatted text string"""
        
        # Base message
        msg = super().format(record)
        
        # Add correlation ID if available
        correlation_id = getattr(record, "correlation_id", None)
        request_id = getattr(record, "request_id", None)
        
        prefix_parts = []
        if correlation_id:
            prefix_parts.append(f"[{correlation_id}]")
        if request_id:
            prefix_parts.append(f"[{request_id}]")
        
        prefix = " ".join(prefix_parts)
        if prefix:
            msg = f"{prefix} {msg}"
        
        return msg


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structured logging for the application
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format (json or text)
    
    Example:
        >>> setup_logging(log_level="DEBUG", log_format="json")
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started", extra={"correlation_id": "123"})
    """
    
    # Convert string level to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Formatter
    if log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Set Flask logger level
    flask_logger = logging.getLogger("flask")
    flask_logger.setLevel(level)
    
    # Suppress noisy loggers
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.LoggerAdapter:
    """Get logger with support for correlation IDs
    
    Returns logger adapter that injects correlation_id from Flask context
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        logging.LoggerAdapter with context injection
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("User created", extra={"user_id": "123"})
    """
    
    logger = logging.getLogger(name)
    
    class ContextAwareAdapter(logging.LoggerAdapter):
        """Logger adapter that injects request context"""
        
        def process(self, msg: str, kwargs: Dict[str, Any]):
            """Add context to every log message"""
            
            # Try to get from Flask request context
            try:
                correlation_id = flask.g.get("correlation_id")
                request_id = flask.g.get("request_id")
                user_id = flask.g.get("user_id")
                
                # Add to extra fields
                if "extra" not in kwargs:
                    kwargs["extra"] = {}
                
                if correlation_id:
                    kwargs["extra"]["correlation_id"] = correlation_id
                if request_id:
                    kwargs["extra"]["request_id"] = request_id
                if user_id:
                    kwargs["extra"]["user_id"] = user_id
            
            except (RuntimeError, AttributeError):
                # No Flask context available (outside request)
                pass
            
            return msg, kwargs
    
    return ContextAwareAdapter(logger, {})
