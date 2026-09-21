"""Reverse download-only config identity before retained baseline hashes."""
import re

def normalize_config(text: str) -> str:
    return re.sub(
        r'\nstatic constexpr char RWLOG_DOWNLOAD_REVISION\[\] = "[^"]+";',
        '',
        text,
    )

def normalize_file(path: str, text: str) -> str:
    if path == "src/config.h":
        return normalize_config(text)
    return text
