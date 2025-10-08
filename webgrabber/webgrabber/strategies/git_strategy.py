# Vị trí: webgrabber/strategies/git_strategy.py

import os
import shutil
from pathlib import Path
from typing import Callable, Optional
import threading
import pygit2
from urllib.parse import urlparse

from ..core.audit_logger import log_audit
from ..core.secure_storage import SecureTokenStorage

class GitStrategy:
    """Strategy for downloading source code from Git hosting platforms like GitHub, GitLab."""

    def __init__(self,
                 url: str,
                 output_dir: Path,
                 config: dict,
                 log_callback: Callable[[str], None],
                 token_callback: Callable[[str], str],
                 session_manager=None, # Keep for compatibility
                 cancel_event: Optional[threading.Event] = None):
        self.url = url
        self.output_dir = output_dir
        self.config = config.get('git_strategy', {})
        self.log_callback = log_callback
        self.token_callback = token_callback
        self.cancel_event = cancel_event
        self.token_storage = SecureTokenStorage()

    def _check_cancel(self):
        if self.cancel_event and self.cancel_event.is_set():
            raise InterruptedError("Download was cancelled by the user.")

    async def download(self) -> dict:
        """Executes the download process using Git clone."""
        self.log_callback(f"Executing GitStrategy for {self.url}")
        self._check_cancel()
        
        target_dir = self.output_dir / Path(urlparse(self.url).path).name.replace('.git', '')
        
        if target_dir.exists():
            self.log_callback(f"Output directory '{target_dir}' already exists. Removing it.")
            shutil.rmtree(target_dir)
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.log_callback(f"Cloning Git repository from {self.url} into {target_dir}...")
            repo = pygit2.clone_repository(self.url, str(target_dir))
            repo.free()
            self.log_callback("Clone successful.")
        except pygit2.GitError as e:
            error_message = f"Failed to clone Git repository: {e}. If this is a private repository, a token might be required."
            self.log_callback(error_message)
            raise ConnectionError(error_message) from e

        self._check_cancel()
        return self._build_tree_from_dir(target_dir)

    def _build_tree_from_dir(self, directory: Path) -> dict:
        """Builds a dictionary representing the file tree of the cloned repo."""
        tree = {}
        for root, _, files in os.walk(directory):
            if '.git' in root.split(os.sep):
                continue
            for file in files:
                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(self.output_dir))
                tree[rel_path] = "Downloaded via Git Clone"
        self.log_callback(f"Built file tree with {len(tree)} files.")
        return tree
