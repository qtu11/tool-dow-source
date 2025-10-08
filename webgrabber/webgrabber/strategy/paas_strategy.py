#webgrabber/webgrabber/strategy/paas_strategy.py
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from ..core.audit_logger import log_audit
from ..core.secure_storage import SecureTokenStorage

class PaaSStrategy:
    """Handles downloading source from Platform-as-a-Service providers."""

    def __init__(self, url: str, output_dir: Path, platform_info: dict, token_callback=None):
        self.url = url
        self.output_dir = output_dir
        self.platform = platform_info.get('platform')
        self.token_callback = token_callback
        self.storage = SecureTokenStorage()

    async def download(self):
        """Selects and runs the appropriate PaaS download method."""
        if self.platform == 'heroku':
            return await self._download_heroku()
        # Thêm các nền tảng PaaS khác ở đây
        # elif self.platform == 'render':
        #     return await self._download_render()
        else:
            raise NotImplementedError(f"Download strategy for PaaS platform '{self.platform}' is not implemented.")

    async def _download_heroku(self):
        """Downloads a Heroku app's source code using the Heroku CLI."""
        log_audit("Executing Heroku CLI strategy.")
        
        # Heroku app name thường là subdomain của herokuapp.com
        app_name = urlparse(self.url).netloc.split('.')[0]
        
        # Heroku CLI sử dụng biến môi trường HEROKU_API_KEY
        api_key = self.storage.load_token('heroku')
        if not api_key and self.token_callback:
            api_key = self.token_callback('heroku_api_key', "Vui lòng nhập Heroku API Key của bạn:")
            if api_key:
                self.storage.save_token('heroku', api_key)
            else:
                raise Exception("Heroku API Key is required.")

        env = os.environ.copy()
        env['HEROKU_API_KEY'] = api_key
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = ['heroku', 'git:clone', '-a', app_name, str(self.output_dir)]
        log_audit(f"Running command: heroku git:clone -a {app_name} ...")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            err_message = stderr.decode('utf-8', errors='ignore')
            raise Exception(f"Heroku CLI failed. Is it installed and are you logged in? Error: {err_message}")

        log_audit("Heroku clone completed successfully.")
        return self._build_tree_from_dir()

    def _build_tree_from_dir(self):
        tree = {}
        for root, _, files in os.walk(self.output_dir):
            for file in files:
                # Bỏ qua thư mục .git
                if '.git' in root.split(os.sep):
                    continue
                full_path = Path(root) / file
                rel_path = full_path.relative_to(self.output_dir)
                tree[str(rel_path)] = "Cloned from Heroku"
        return tree
