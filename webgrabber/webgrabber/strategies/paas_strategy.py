#webgrabber/webgrabber/strategies/paas_strategy.py

import os
import subprocess
import asyncio
import aiohttp
import requests
from pathlib import Path
from urllib.parse import urlparse
from typing import Callable, Optional
import threading

from ..core.audit_logger import log_audit
from ..core.secure_storage import SecureTokenStorage
from ..core.environment_checker import EnvironmentChecker
from ..core.session_manager import SessionManager

class PaasStrategy:
    """Strategy for downloading source code from PaaS platforms using their CLI or API."""

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
        self.config = config.get('paas_strategy', {})
        self.session_manager = session_manager
        self.log_callback = log_callback
        self.token_callback = token_callback
        self.cancel_event = cancel_event
        
        from ..core.platform_detector import PlatformDetector
        self.platform_info = PlatformDetector.detect(url)
        self.platform = self.platform_info.get('id', 'unknown').lower()
        self.token_storage = SecureTokenStorage()

    def _check_cancel(self):
        if self.cancel_event and self.cancel_event.is_set():
            raise asyncio.CancelledError("Download cancelled by user.")

    async def download(self) -> dict:
        """Executes the download process using the platform-specific CLI or API."""
        self.log_callback(f"Executing PaasStrategy for {self.platform}...")

        token = self.token_storage.load_token(self.platform)
        if not token and self.token_callback:
            self.log_callback(f"No saved token for {self.platform}. Requesting from user.")
            token = self.token_callback(self.platform)
            if token:
                self.token_storage.save_token(self.platform, token)
            else:
                self.log_callback(f"No token provided for {self.platform}. Operation might fail if auth is needed.")

        if self.platform == 'vercel':
            return await self._download_vercel(token)
        elif self.platform == 'netlify':
            return await self._download_netlify(token)
        elif self.platform == 'render':
            return await self._download_render(token)
        elif self.platform == 'heroku':
            return await self._download_heroku(token)
        else:
            raise NotImplementedError(f"The PaasStrategy for platform '{self.platform}' has not been implemented.")

    # FIX: Change type hint to Optional[str] to allow token to be None.
    async def _download_vercel(self, token: Optional[str]) -> dict:
        self._check_cancel()
        if not token:
            raise ValueError("Vercel API access requires a Personal Access Token.")

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            hostname = urlparse(self.url).netloc
            deploy_url = f"https://api.vercel.com/v13/deployments/{hostname}"
            
            async with session.get(deploy_url, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to get Vercel deployment info: {await resp.text()}")
                data = await resp.json()
                deploy_id = data['id']
                self.log_callback(f"Retrieved Vercel deployment ID: {deploy_id}")

            files_url = f"https://api.vercel.com/v6/deployments/{deploy_id}/files"
            async with session.get(files_url, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to list Vercel files: {await resp.text()}")
                files = await resp.json()
            
            tree = {}
            tasks = [self._download_vercel_file(item, deploy_id, session, headers) for item in files]
            results = await asyncio.gather(*tasks)
            for result in results:
                if result:
                    tree[result[0]] = result[1]
            return tree

    async def _download_vercel_file(self, file_info, deploy_id, session, headers):
        self._check_cancel()
        file_path = file_info['name']
        file_uid = file_info['uid']
        file_url = f"https://api.vercel.com/v6/deployments/{deploy_id}/files/{file_uid}"
        
        async with session.get(file_url, headers=headers) as resp:
            if resp.status != 200:
                self.log_callback(f"Failed to download {file_path}: {resp.status}")
                return None
            content = await resp.read()
        
        save_path = self.output_dir / file_path.lstrip('/')
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(content)
        
        self.log_callback(f"Downloaded {file_path}")
        return str(file_path.lstrip('/')), "Downloaded via Vercel API"

    # FIX: Change type hint to Optional[str] to allow token to be None.
    async def _download_netlify(self, token: Optional[str]) -> dict:
        self._check_cancel()
        if not token:
            raise ValueError("Netlify API access requires a Personal Access Token.")

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            sites_url = "https://api.netlify.com/api/v1/sites"
            
            async with session.get(sites_url, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to list Netlify sites: {await resp.text()}")
                sites = await resp.json()
                
            target_netloc = urlparse(self.url).netloc
            site_info = next((s for s in sites if urlparse(s.get('url')).netloc == target_netloc), None)
            if not site_info:
                raise ValueError(f"Could not find a Netlify site matching the URL: {self.url}")
            site_id = site_info['id']
            self.log_callback(f"Found Netlify site ID: {site_id}")

            deploys_url = f"https://api.netlify.com/api/v1/sites/{site_id}/deploys"
            async with session.get(deploys_url, headers=headers) as resp:
                 if resp.status != 200:
                    raise Exception(f"Failed to get deploys: {await resp.text()}")
                 deploys = await resp.json()
                 latest_deploy_id = deploys[0]['id'] # Get the most recent deploy
            
            deploy_files_url = f"https://api.netlify.com/api/v1/deploys/{latest_deploy_id}/files"
            async with session.get(deploy_files_url, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to list files: {await resp.text()}")
                files = await resp.json()
            
            tree = {}
            for file_info in files:
                self._check_cancel()
                file_path = file_info['path']
                public_url = f"{self.url.rstrip('/')}{file_path}"
                async with session.get(public_url) as file_resp: # Public files don't need auth
                    if file_resp.status == 200:
                        content = await file_resp.read()
                        save_path = self.output_dir / file_path.lstrip('/')
                        save_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(save_path, 'wb') as f:
                            f.write(content)
                        tree[str(file_path.lstrip('/'))] = "Downloaded via Netlify API"
                        self.log_callback(f"Downloaded {file_path}")
                    else:
                        self.log_callback(f"Could not download {file_path} (Status: {file_resp.status})")
            return tree

    # This function is synchronous in the original, should be async or run in thread
    async def _download_render(self, token: Optional[str]) -> dict:
        # Render's API doesn't support file downloads, it links to a Git repo.
        # This function finds the repo and hands off to GitStrategy.
        self._check_cancel()
        if not token:
            raise ValueError("Render API access requires an API Key.")

        def run_sync_requests():
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            services_url = "https://api.render.com/v1/services"
            response = requests.get(services_url, headers=headers)
            response.raise_for_status()
            services = response.json()
            
            service_details = next((s['service'] for s in services if s['service'].get('serviceDetails', {}).get('url') == self.url), None)
            if not service_details:
                raise ValueError(f"Could not find a Render service matching the URL: {self.url}")

            repo_url = service_details.get('repo')
            if not repo_url:
                raise NotImplementedError("Render service is not connected to a Git repository.")
            return repo_url

        try:
            loop = asyncio.get_running_loop()
            repo_url = await loop.run_in_executor(None, run_sync_requests)
        except requests.HTTPError as e:
             raise Exception(f"Failed to query Render API: {e.response.text}")

        self.log_callback(f"Found linked Git repo for Render service: {repo_url}. Using GitStrategy.")
        from .git_strategy import GitStrategy
        git_strategy = GitStrategy(
            url=repo_url,
            output_dir=self.output_dir,
            config=self.config,
            log_callback=self.log_callback,
            token_callback=self.token_callback, # Pass token callback for private repos
            cancel_event=self.cancel_event
        )
        return await git_strategy.download()

    async def _download_heroku(self, token: Optional[str]) -> dict:
        self._check_cancel()
        cli_tool = 'heroku'
        if not EnvironmentChecker.is_tool_installed(cli_tool):
            raise EnvironmentError(EnvironmentChecker.get_missing_tool_message(cli_tool))
        
        app_name = urlparse(self.url).hostname.split('.')[0]
        self.log_callback(f"Determined Heroku app name: {app_name}")
        
        target_dir = self.output_dir / app_name
        
        env = os.environ.copy()
        if token:
            env['HEROKU_API_KEY'] = token
            
        cmd = [cli_tool, 'git:clone', '-a', app_name, str(target_dir)]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"Heroku CLI command failed: {stderr.decode()}")
            
        self.log_callback("Heroku app source cloned successfully.")
        
        tree = {}
        for root, _, files in os.walk(target_dir):
            if '.git' in Path(root).parts:
                continue
            for file in files:
                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(self.output_dir))
                tree[rel_path] = "Downloaded via Heroku CLI"
        return tree
