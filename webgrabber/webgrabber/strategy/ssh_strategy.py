#webgrabber/webgrabber/strategy/ssh_strategy.py
import asyncio
import os
from pathlib import Path

from ..core.audit_logger import log_audit
from ..core.secure_storage import SecureTokenStorage

class SSHStrategy:
    """Handles downloading source code from servers via SCP."""

    def __init__(self, url: str, output_dir: Path, platform_info: dict, token_callback=None):
        self.url = url
        self.output_dir = output_dir
        self.token_callback = token_callback
        self.storage = SecureTokenStorage(storage_file="ssh_credentials.dat")
        # Giả định URL có dạng ssh://user@host:/remote/path
        self.user, self.host, self.remote_path = self._parse_ssh_url()

    def _parse_ssh_url(self):
        """Extracts user, host, and path from an SSH-like URL."""
        # Simple parser, can be made more robust
        user_host, path = self.url.replace("ssh://", "").split(":", 1)
        user, host = user_host.split("@")
        return user, host, path

    async def download(self):
        """Executes the SCP download process."""
        log_audit(f"Executing SSHStrategy for {self.user}@{self.host}")

        # Lấy đường dẫn key SSH từ người dùng
        ssh_key_path = self.storage.load_token(self.host)
        if not ssh_key_path and self.token_callback:
            ssh_key_path = self.token_callback("ssh_key", f"Vui lòng nhập đường dẫn tới file Private Key (.pem, .key) cho {self.host}:")
            if ssh_key_path and Path(ssh_key_path).exists():
                self.storage.save_token(self.host, ssh_key_path)
            else:
                raise Exception("Valid SSH key path is required.")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Lệnh scp: -r (đệ quy), -i (identity file/key)
        cmd = [
            'scp',
            '-r',
            '-i', ssh_key_path,
            f"{self.user}@{self.host}:{self.remote_path}", # Nguồn
            str(self.output_dir) # Đích
        ]

        log_audit(f"Running command: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.PIPE)
        _, stderr = await process.communicate()

        if process.returncode != 0:
            err_message = stderr.decode('utf-8', errors='ignore')
            raise Exception(f"SCP failed. Error: {err_message}")

        log_audit("SCP download completed successfully.")
        return self._build_tree_from_dir()

    def _build_tree_from_dir(self):
        # This method can be shared via a base class, but is duplicated for clarity
        tree = {}
        # SCP tải nội dung vào thư mục output, nên ta cần vào một cấp nữa
        source_base_name = Path(self.remote_path).name
        downloaded_content_path = self.output_dir / source_base_name
        
        if not downloaded_content_path.exists():
             downloaded_content_path = self.output_dir

        for root, _, files in os.walk(downloaded_content_path):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(downloaded_content_path)
                tree[str(rel_path)] = "Copied via SCP"
        return tree
