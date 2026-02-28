# webgrabber/webgrabber/core/download_cache.py
"""
Download Cache — Hash-based incremental download.

Lần đầu download: lưu hash tất cả files.
Lần sau download cùng URL: chỉ download files đã thay đổi.
Tiết kiệm bandwidth + thời gian.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Set
from datetime import datetime


class DownloadCache:
    """Hash-based download cache for incremental updates."""

    CACHE_FILE = '.webgrabber_cache.json'

    def __init__(self, output_dir: Path, source_url: str):
        self.output_dir = Path(output_dir)
        self.source_url = source_url
        self.cache_path = self.output_dir / self.CACHE_FILE
        self.cache = self._load_cache()
        self.current_hashes: Dict[str, str] = {}
        self.stats = {
            'new': 0,
            'changed': 0,
            'unchanged': 0,
            'deleted': 0,
        }

    def _load_cache(self) -> Dict:
        """Load existing cache from disk."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {'url': self.source_url, 'files': {}, 'last_download': None}
        return {'url': self.source_url, 'files': {}, 'last_download': None}

    def should_download(self, url: str, content: bytes) -> bool:
        """
        Check if file needs to be saved (new or changed).
        Returns True if file should be saved, False if unchanged.
        """
        content_hash = hashlib.sha256(content).hexdigest()
        self.current_hashes[url] = content_hash

        old_hash = self.cache.get('files', {}).get(url)

        if old_hash is None:
            self.stats['new'] += 1
            return True
        elif old_hash != content_hash:
            self.stats['changed'] += 1
            return True
        else:
            self.stats['unchanged'] += 1
            return False

    def save_cache(self):
        """Save current hashes to cache file."""
        # Merge with existing: add new, update changed
        existing_files = self.cache.get('files', {})
        existing_files.update(self.current_hashes)

        self.cache = {
            'url': self.source_url,
            'files': existing_files,
            'last_download': datetime.now().isoformat(),
            'total_files': len(existing_files),
        }

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2)

    def get_deleted_files(self) -> Set[str]:
        """Find files that existed in previous download but not current."""
        old_files = set(self.cache.get('files', {}).keys())
        new_files = set(self.current_hashes.keys())
        deleted = old_files - new_files
        self.stats['deleted'] = len(deleted)
        return deleted

    def get_summary(self) -> str:
        """Human-readable summary of cache comparison."""
        total = sum(self.stats.values())
        if total == 0:
            return "📦 First download (no cache)"

        parts = []
        if self.stats['new']:
            parts.append(f"🆕 {self.stats['new']} new")
        if self.stats['changed']:
            parts.append(f"🔄 {self.stats['changed']} changed")
        if self.stats['unchanged']:
            parts.append(f"✅ {self.stats['unchanged']} unchanged")
        if self.stats['deleted']:
            parts.append(f"🗑️ {self.stats['deleted']} deleted")

        return f"📊 Incremental: {', '.join(parts)}"

    @property
    def has_previous_download(self) -> bool:
        """Check if there's a previous download cache."""
        return bool(self.cache.get('files'))

    @property
    def last_download_time(self) -> str:
        """Get last download timestamp."""
        return self.cache.get('last_download', 'Never')
