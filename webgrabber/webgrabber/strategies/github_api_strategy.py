# webgrabber/webgrabber/strategies/github_api_strategy.py
"""
GitHub/GitLab/Bitbucket API Strategy — Download source code qua REST API.

Ưu điểm so với git clone:
- Không cần cài git
- Nhanh hơn (download archive tar.gz)
- Hỗ trợ download specific branch/tag/commit
- Hỗ trợ private repos qua Personal Access Token
- Hỗ trợ download specific subdirectory (GitHub Trees API)
"""

import asyncio
import io
import os
import re
import tarfile
import zipfile
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse
import threading

import aiohttp

from ..core.audit_logger import log_audit
from ..core.secure_storage import SecureTokenStorage
from ..core.session_manager import SessionManager


class GitHostingAPIStrategy:
    """
    Download source code từ Git hosting platforms qua REST API.
    Hỗ trợ: GitHub, GitLab, Bitbucket, Codeberg, Gitea.
    """

    # API base URLs
    API_MAP = {
        'github': 'https://api.github.com',
        'gitlab': 'https://gitlab.com/api/v4',
        'bitbucket': 'https://api.bitbucket.org/2.0',
        'codeberg': 'https://codeberg.org/api/v1',
        'gitea': 'https://try.gitea.io/api/v1',
    }

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
        self.config = config.get('git_strategy', {})
        self.log_callback = log_callback
        self.token_callback = token_callback
        self.cancel_event = cancel_event
        self.token_storage = SecureTokenStorage()

        # Parse URL to extract owner, repo, branch, path
        self._parse_url()

    def _parse_url(self):
        """Extract owner, repo, branch, and subpath from URL."""
        parsed = urlparse(self.url)
        hostname = parsed.netloc.lower()

        # Detect platform
        if 'github.com' in hostname:
            self.platform = 'github'
        elif 'gitlab.com' in hostname:
            self.platform = 'gitlab'
        elif 'bitbucket.org' in hostname:
            self.platform = 'bitbucket'
        elif 'codeberg.org' in hostname:
            self.platform = 'codeberg'
        else:
            self.platform = 'gitea'

        # Parse path: /owner/repo/tree/branch/path or /owner/repo
        path_parts = [p for p in parsed.path.strip('/').split('/') if p]

        self.owner = path_parts[0] if len(path_parts) > 0 else ''
        self.repo = path_parts[1].rstrip('.git') if len(path_parts) > 1 else ''
        self.branch = self.config.get('branch', 'main')
        self.subpath = ''

        # Detect branch from URL pattern: /tree/branch-name/...
        if len(path_parts) > 3 and path_parts[2] == 'tree':
            self.branch = path_parts[3]
            if len(path_parts) > 4:
                self.subpath = '/'.join(path_parts[4:])
        elif len(path_parts) > 3 and path_parts[2] == 'blob':
            self.branch = path_parts[3]
            if len(path_parts) > 4:
                self.subpath = '/'.join(path_parts[4:])

    def _check_cancel(self):
        if self.cancel_event and self.cancel_event.is_set():
            raise asyncio.CancelledError("Download cancelled by user.")

    async def download(self) -> dict:
        """Download source code via platform API."""
        self.log_callback(f"📦 Using API Strategy for {self.platform}: {self.owner}/{self.repo}")

        # Get or request token
        token = self.token_storage.load_token(self.platform)
        if not token and self.token_callback:
            self.log_callback(f"🔑 Requesting token for {self.platform} (optional for public repos)...")
            token = self.token_callback(self.platform)
            if token:
                self.token_storage.save_token(self.platform, token)

        try:
            if self.platform == 'github':
                return await self._download_github(token)
            elif self.platform == 'gitlab':
                return await self._download_gitlab(token)
            elif self.platform == 'bitbucket':
                return await self._download_bitbucket(token)
            elif self.platform in ('codeberg', 'gitea'):
                return await self._download_gitea(token)
            else:
                raise NotImplementedError(f"API strategy for {self.platform} not implemented.")
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                self.log_callback(f"❌ Repository not found: {self.owner}/{self.repo}")
                self.log_callback("   Tip: This might be a private repo — provide a token.")
            elif e.status == 401:
                self.log_callback(f"❌ Authentication failed. Token may be invalid.")
            elif e.status == 403:
                self.log_callback(f"❌ Access denied. Rate limit or permissions issue.")
            raise

    # ========== GitHub ==========

    async def _download_github(self, token: str = None) -> dict:
        """Download from GitHub via archive API."""
        self._check_cancel()
        headers = {'Accept': 'application/vnd.github+json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        # Try to detect default branch
        async with aiohttp.ClientSession(headers=headers) as session:
            # Get repo info to find default branch
            repo_url = f"{self.API_MAP['github']}/repos/{self.owner}/{self.repo}"
            async with session.get(repo_url) as resp:
                if resp.status == 200:
                    repo_info = await resp.json()
                    if not self.branch or self.branch == 'main':
                        self.branch = repo_info.get('default_branch', 'main')
                    self.log_callback(f"📊 Repo: {repo_info.get('full_name')} (⭐{repo_info.get('stargazers_count', 0)})")
                    self.log_callback(f"📌 Branch: {self.branch}")
                elif resp.status == 404:
                    # Try 'master' as fallback
                    self.log_callback("⚠️ Could not fetch repo info. Trying download directly...")

            # Download archive
            archive_url = f"{self.API_MAP['github']}/repos/{self.owner}/{self.repo}/tarball/{self.branch}"
            self.log_callback(f"📥 Downloading archive from GitHub...")

            async with session.get(archive_url) as resp:
                resp.raise_for_status()
                data = await resp.read()
                self.log_callback(f"📦 Archive size: {len(data) / 1024 / 1024:.1f} MB")

        return self._extract_tarball(data)

    # ========== GitLab ==========

    async def _download_gitlab(self, token: str = None) -> dict:
        """Download from GitLab via archive API."""
        self._check_cancel()
        headers = {}
        if token:
            headers['PRIVATE-TOKEN'] = token

        # GitLab project ID is URL-encoded path
        project_path = f"{self.owner}%2F{self.repo}"

        async with aiohttp.ClientSession(headers=headers) as session:
            archive_url = f"{self.API_MAP['gitlab']}/projects/{project_path}/repository/archive.tar.gz"
            if self.branch:
                archive_url += f"?sha={self.branch}"

            self.log_callback(f"📥 Downloading archive from GitLab...")
            async with session.get(archive_url) as resp:
                resp.raise_for_status()
                data = await resp.read()
                self.log_callback(f"📦 Archive size: {len(data) / 1024 / 1024:.1f} MB")

        return self._extract_tarball(data)

    # ========== Bitbucket ==========

    async def _download_bitbucket(self, token: str = None) -> dict:
        """Download from Bitbucket via download API."""
        self._check_cancel()
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        async with aiohttp.ClientSession(headers=headers) as session:
            archive_url = f"https://bitbucket.org/{self.owner}/{self.repo}/get/{self.branch}.zip"
            self.log_callback(f"📥 Downloading archive from Bitbucket...")

            async with session.get(archive_url) as resp:
                resp.raise_for_status()
                data = await resp.read()
                self.log_callback(f"📦 Archive size: {len(data) / 1024 / 1024:.1f} MB")

        return self._extract_zipball(data)

    # ========== Gitea/Codeberg ==========

    async def _download_gitea(self, token: str = None) -> dict:
        """Download from Gitea/Codeberg via archive API."""
        self._check_cancel()
        headers = {}
        if token:
            headers['Authorization'] = f'token {token}'

        base = self.API_MAP.get(self.platform, f'https://{urlparse(self.url).netloc}/api/v1')

        async with aiohttp.ClientSession(headers=headers) as session:
            archive_url = f"{base}/repos/{self.owner}/{self.repo}/archive/{self.branch}.tar.gz"
            self.log_callback(f"📥 Downloading archive from {self.platform}...")

            async with session.get(archive_url) as resp:
                resp.raise_for_status()
                data = await resp.read()
                self.log_callback(f"📦 Archive size: {len(data) / 1024 / 1024:.1f} MB")

        return self._extract_tarball(data)

    # ========== Archive Extraction ==========

    def _extract_tarball(self, data: bytes) -> dict:
        """Extract tar.gz archive, flattening the top-level directory."""
        self._check_cancel()
        self.log_callback("📂 Extracting archive...")
        tree = {}

        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
            members = tar.getmembers()
            # GitHub/GitLab archives have a top-level dir like "owner-repo-commitsha/"
            prefix = ''
            if members and members[0].isdir():
                prefix = members[0].name + '/'

            for member in members:
                self._check_cancel()
                if member.isfile():
                    # Strip the top-level prefix
                    clean_path = member.name
                    if prefix and clean_path.startswith(prefix):
                        clean_path = clean_path[len(prefix):]

                    if not clean_path:
                        continue

                    # Filter by subpath if specified
                    if self.subpath and not clean_path.startswith(self.subpath):
                        continue

                    save_path = self.output_dir / clean_path
                    save_path.parent.mkdir(parents=True, exist_ok=True)

                    f = tar.extractfile(member)
                    if f:
                        save_path.write_bytes(f.read())
                        tree[clean_path] = f"Downloaded via {self.platform} API"
                        self.log_callback(f"   📄 {clean_path}")

        self.log_callback(f"✅ Extracted {len(tree)} files")
        return tree

    def _extract_zipball(self, data: bytes) -> dict:
        """Extract ZIP archive, flattening the top-level directory."""
        self._check_cancel()
        self.log_callback("📂 Extracting archive...")
        tree = {}

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            # Find common prefix
            prefix = ''
            dirs = [n for n in names if n.endswith('/')]
            if dirs:
                prefix = dirs[0]

            for name in names:
                self._check_cancel()
                if not name.endswith('/'):
                    clean_path = name
                    if prefix and clean_path.startswith(prefix):
                        clean_path = clean_path[len(prefix):]

                    if not clean_path:
                        continue

                    if self.subpath and not clean_path.startswith(self.subpath):
                        continue

                    save_path = self.output_dir / clean_path
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(zf.read(name))
                    tree[clean_path] = f"Downloaded via {self.platform} API"

        self.log_callback(f"✅ Extracted {len(tree)} files")
        return tree
