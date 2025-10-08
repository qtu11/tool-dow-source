#webgrabber/webgrabber/strategies/container_strategy.py
import os
import subprocess
from pathlib import Path
from typing import Callable, Optional
import threading
import tarfile
from urllib.parse import urlparse  # FIX: Import the missing 'urlparse' function.

from ..core.audit_logger import log_audit
from ..core.secure_storage import SecureTokenStorage
from ..core.environment_checker import EnvironmentChecker
from ..core.session_manager import SessionManager

class ContainerStrategy:
    """Strategy for downloading container images and extracting source (e.g., Dockerfile)."""

    def __init__(self,
                 url: str,
                 output_dir: Path,
                 config: dict,
                 session_manager: SessionManager,
                 log_callback: Callable[[str], None],
                 token_callback: Callable[[str], str],
                 cancel_event: Optional[threading.Event] = None):
        
        self.url = url
        self.output_dir = output_dir
        self.config = config.get('container_strategy', {})
        self.session_manager = session_manager
        self.log_callback = log_callback
        self.token_callback = token_callback
        self.cancel_event = cancel_event
        from ..core.platform_detector import PlatformDetector
        self.platform_info = PlatformDetector.detect(url)
        self.platform = self.platform_info.get('id', 'unknown')
        self.token_storage = SecureTokenStorage()

    async def download(self) -> dict:
        """Pulls container image and extracts layers/source."""
        self.log_callback(f"Executing ContainerStrategy for {self.platform}...")

        cli_tool = self.platform_info.get('cli_tool', 'docker')
        if not EnvironmentChecker.is_tool_installed(cli_tool):
            raise EnvironmentError(EnvironmentChecker.get_missing_tool_message(cli_tool))
        
        self.log_callback(f"Verified that '{cli_tool}' is installed.")

        image_name = self._get_image_name_from_url()
        token = self.token_storage.load_token(self.platform)
        if not token and self.token_callback and self.platform in ['aws_ecr', 'azure_acr', 'gcp_gcr']:
            token = self.token_callback(self.platform)
            if token:
                self.token_storage.save_token(self.platform, token)

        await self._login_if_needed(token)

        try:
            subprocess.run([cli_tool, 'pull', image_name], check=True, capture_output=True, text=True)
            self.log_callback(f"Pulled image {image_name} successfully.")
        except subprocess.CalledProcessError as e:
            self.log_callback(f"Failed to pull image: {e.stderr}")
            raise

        tar_path = self.output_dir / 'image.tar'
        subprocess.run([cli_tool, 'save', '-o', str(tar_path), image_name], check=True)
        with tarfile.open(tar_path) as tar:
            tar.extractall(path=self.output_dir)
        os.remove(tar_path)

        tree = self._build_tree_from_dir(self.output_dir)
        self.log_callback(f"Extracted {len(tree)} files from container image.")
        return tree

    # FIX: Change type hint to Optional[str] to allow token to be None.
    async def _login_if_needed(self, token: Optional[str]):
        """Logs into a private registry if a token is provided."""
        if not token:
            return  # Can't log in without a token

        if self.platform == 'aws_ecr':
            self.log_callback("AWS ECR login required. Please ensure your AWS CLI is configured.")
            # This logic is a placeholder and would need full implementation.
            # E.g., subprocess.run(['aws', 'ecr', 'get-login-password', ...], ...)
        # Add logic for other container registries like GCP, Azure, etc.

    def _get_image_name_from_url(self) -> str:
        """Extracts image name from URL (e.g., hub.docker.com/r/user/repo -> user/repo:latest)."""
        path = urlparse(self.url).path
        # A simple heuristic for Docker Hub URLs
        if '/r/' in path:
            return path.split('/r/')[-1] + ':latest'
        return path.lstrip('/') + ':latest'

    def _build_tree_from_dir(self, directory: Path) -> dict:
        tree = {}
        for root, _, files in os.walk(directory):
            for file in files:
                full_path = Path(root) / file
                try:
                    rel_path = str(full_path.relative_to(self.output_dir))
                    tree[rel_path] = "Extracted from container image"
                except ValueError:
                    continue
        return tree
