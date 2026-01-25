"""Utility functions for logging and path management"""
import logging
import sys
from pathlib import Path
from typing import Optional, Union


def setup_logger(
    name: str = "kt-datacards",
    level: int = logging.INFO,
    log_file: Optional[Path] = None
) -> logging.Logger:
    """
    Set up a logger with console and optional file output
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Optional path to log file
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler with simple format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # More detailed in file
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def resolve_path(path: Union[str, Path], base_dir: Path = Path.cwd()) -> Path:
    """
    Resolve a path relative to base directory if not absolute
    
    Args:
        path: Path to resolve
        base_dir: Base directory for relative paths
        
    Returns:
        Resolved absolute path
    """
    path = Path(path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def ensure_dir(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary
    
    Args:
        path: Directory path
        
    Returns:
        The directory path
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    """
    Convert a string to a safe filename
    
    Args:
        name: Original name
        
    Returns:
        Safe filename
    """
    # Replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        name = name.replace(char, '-')
    
    # Remove multiple hyphens
    while '--' in name:
        name = name.replace('--', '-')
    
    # Strip leading/trailing hyphens and whitespace
    name = name.strip('- ')
    
    return name
