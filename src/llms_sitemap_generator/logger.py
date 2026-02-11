"""
Centralized logging configuration for llms-sitemap-generator
统一日志配置模块
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

# Global logger instance
_logger: Optional[logging.Logger] = None


def get_logger(name: str = "llms_sitemap_generator") -> logging.Logger:
    """
    Get or create the global logger instance.
    
    Args:
        name: Logger name, defaults to "llms_sitemap_generator"
        
    Returns:
        Configured logger instance
    """
    global _logger
    
    if _logger is None:
        _logger = logging.getLogger(name)
        _logger.setLevel(logging.INFO)
        
        # Avoid adding handlers multiple times
        if not _logger.handlers:
            # Console handler with formatted output
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            # Format: [LEVEL] message
            formatter = logging.Formatter(
                "[%(levelname)s] %(message)s",
                datefmt="%H:%M:%S"
            )
            console_handler.setFormatter(formatter)
            
            _logger.addHandler(console_handler)
    
    return _logger


def set_log_level(level: int | str) -> None:
    """
    Set the global log level.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               or integer level
    """
    logger = get_logger()
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
