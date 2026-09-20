import os
import uuid
import json
from datetime import datetime
from app.utils.time import utcnow
from pathlib import Path

def generate_id() -> str:
    return str(uuid.uuid4())

def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def validate_file_extension(filename: str, allowed_extensions: list[str]) -> bool:
    return any(filename.lower().endswith(ext) for ext in allowed_extensions)

def validate_file_size(file_size: int, max_size: int) -> bool:
    return file_size <= max_size

def ensure_directory(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def sanitize_filename(filename: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)

def current_timestamp() -> str:
    return utcnow().isoformat() + "Z"

def truncate(str: str, max_len: int) -> str:
    return str[:max_len] + "..." if len(str) > max_len else str
