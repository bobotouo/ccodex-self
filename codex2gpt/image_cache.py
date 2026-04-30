"""File-based image cache with TTL cleanup for generated images."""

import hashlib
import os
import time
import threading
from pathlib import Path
from typing import Optional


class ImageCache:
    def __init__(self, cache_dir: str, ttl_seconds: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def save(self, image_data: bytes, extension: str = "png") -> str:
        """Save image bytes to cache, return the relative URL path."""
        with self._lock:
            file_hash = hashlib.md5(image_data).hexdigest()
            timestamp = int(time.time())
            filename = f"{timestamp}_{file_hash}.{extension}"
            rel_dir = Path(time.strftime("%Y"), time.strftime("%m"), time.strftime("%d"))
            file_path = self.cache_dir / rel_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(image_data)
            return f"/images/{rel_dir.as_posix()}/{filename}"

    def get_path(self, relative_url: str) -> Optional[Path]:
        """Resolve a relative URL to a file path."""
        clean = relative_url.lstrip("/")
        if clean.startswith("images/"):
            clean = clean[len("images/"):]
        file_path = self.cache_dir / clean
        if file_path.exists() and file_path.is_file():
            return file_path
        return None

    def cleanup_expired(self) -> int:
        """Remove images older than TTL. Returns number of files removed."""
        if self.ttl_seconds <= 0:
            return 0
        cutoff = time.time() - self.ttl_seconds
        removed = 0
        with self._lock:
            for dirpath, _, filenames in os.walk(self.cache_dir):
                for filename in filenames:
                    file_path = Path(dirpath) / filename
                    try:
                        if file_path.stat().st_mtime < cutoff:
                            file_path.unlink()
                            removed += 1
                    except OSError:
                        continue
        return removed
