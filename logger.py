"""Logging configuration for the Quiz Generator application."""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_to_file: bool = True) -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file in addition to console
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("quiz_generator")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Prevent duplicate handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_to_file:
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / f"quiz_generator_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
        except Exception as e:
            logger.warning(f"Could not set up file logging: {e}")
    
    return logger


def log_function_call(func):
    """Decorator to log function calls with parameters and execution time."""
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger("quiz_generator")
        start_time = time.time()
        
        # Log function call
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.2f}s: {str(e)}")
            raise
    
    return wrapper
