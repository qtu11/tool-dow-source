#webgrabber/webgrabber/strategy/git_strategy.py
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from ..core.audit_logger import log_audit
from ..core.secure_storage import SecureTokenStorage
from ..core.platform_detector import PlatformDetector

class GitStrategy:
    """Handles downloading source code from Git-based platforms."""

    def __init__(self, url: str, output_dir: Path, platform_info: dict, token_callback=None):
        self.url = url
        self.output_dir = output_dir
        self.platform = platform_info.get('platform', 'unknown')
        self.token_callback = token_callback
        self.storage = SecureTokenStorage()

    async def download(self):
        """Executes the git clone process."""
        log_audit(f"Executing GitStrategy for {self.platform} at {self.url}")
        
        token = self.storage.load_token(self.platform)
        if not token and self.token_callback:
            log_audit(f"No saved token for {self.platform}. Requesting from user.")
            token = self.token_callback(self.platform, f"Vui lòng nhập Personal Access Token cho {self.platform.capitalize()}:")
            if token:
                self.storage.save_token(self.platform, token)
            else:
                raise Exception("Token is required for private repositories but was not provided.")

        clone_url = self._get_authenticated_url(token)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = ['git', 'clone', '--depth', '1', clone_url, str(self.output_dir)]
        log_audit(f"Running command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            err_message = stderr.decode('utf-8', errors='ignore')
            log_audit(f"Git clone failed. Stderr: {err_message}")
            raise Exception(f"Git clone failed for {self.url}. Error: {err_message}")
            
        log_audit("Git clone completed successfully.")
        return self._build_tree_from_dir()

    def _get_authenticated_url(self, token: str) -> str:
        """Constructs a clone URL with the token embedded."""
        if not token:
            return self.url
            
        parsed_url = urlparse(self.url)
        # Example: https://<token>@github.com/user/repo.git
        clone_url = f"{parsed_url.scheme}://{token}@{parsed_url.netloc}{parsed_url.path}"
        return clone_url

    def _build_tree_from_dir(self):
        """Builds a dictionary representing the file structure of the downloaded code."""
        tree = {}
        for root, _, files in os.walk(self.output_dir):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(self.output_dir)
                tree[str(rel_path)] = "Cloned file"
        return tree
