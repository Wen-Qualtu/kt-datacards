"""Path utility functions"""
from pathlib import Path
from typing import Union


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
