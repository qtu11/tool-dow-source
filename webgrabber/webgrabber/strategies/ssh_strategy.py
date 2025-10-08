# Vị trí: webgrabber/webgrabber/strategies/ssh_strategy.py

import os
import shutil
from pathlib import Path
from typing import Callable, Optional
import threading
import pygit2
from urllib.parse import urlparse

from ..core.audit_logger import log_audit

class SshStrategy:
    """Strategy for downloading source code from Git-over-SSH URLs."""

    def __init__(self,
                 url: str,
                 output_dir: Path,
                 config: dict,
                 log_callback: Callable[[str], None],
                 session_manager=None,  # Keep for compatibility
                 # FIX: Use Optional[Callable[...]] for arguments with a default of None.
                 token_callback: Optional[Callable[[str], str]] = None,
                 cancel_event: Optional[threading.Event] = None):
        self.url = url
        self.output_dir = output_dir
        self.config = config.get('ssh_strategy', {})
        self.log_callback = log_callback
        self.cancel_event = cancel_event
        self.token_callback = token_callback

    def _check_cancel(self):
        if self.cancel_event and self.cancel_event.is_set():
            raise InterruptedError("Download was cancelled by the user.")

    async def download(self) -> dict:
        """Executes the download process using Git clone over SSH."""
        self.log_callback(f"Executing SshStrategy for {self.url}")
        self._check_cancel()

        # Handle SSH URL format like 'git@github.com:user/repo.git'
        if '@' in self.url and ':' in self.url:
             repo_path_part = self.url.split(':')[-1]
        else:
             repo_path_part = urlparse(self.url).path

        target_dir = self.output_dir / Path(repo_path_part).name.replace('.git', '')
        
        if target_dir.exists():
            self.log_callback(f"Output directory '{target_dir}' already exists. Removing it.")
            shutil.rmtree(target_dir)
        
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.log_callback(f"Cloning Git repository from {self.url} via SSH...")
            # pygit2 handles SSH keys automatically if they are in the standard location.
            repo = pygit2.clone_repository(self.url, str(target_dir))
            repo.free()
            self.log_callback("Clone successful.")
        except pygit2.GitError as e:
            error_message = f"Failed to clone Git repository via SSH: {e}. Ensure your SSH keys are configured correctly."
            self.log_callback(error_message)
            raise ConnectionError(error_message) from e

        self._check_cancel()
        return self._build_tree_from_dir(target_dir)

    def _build_tree_from_dir(self, directory: Path) -> dict:
        """Builds a dictionary representing the file tree of the downloaded source."""
        tree = {}
        for root, _, files in os.walk(directory):
            if '.git' in Path(root).parts:
                continue
            for file in files:
                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(self.output_dir))
                tree[rel_path] = "Downloaded via SSH (Git Clone)"
        self.log_callback(f"Built file tree with {len(tree)} files.")
        return tree
