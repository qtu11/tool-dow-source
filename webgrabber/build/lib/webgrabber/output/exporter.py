# webgrabber/webgrabber/output/exporter.py
"""
Exporter Component — Export source code to different formats.

Features:
- ZIP Archive (nén toàn bộ source code lại thành 1 file .zip)
- Git Repo Init (tạo một local git repository chứa source code vừa được phục dựng)
"""

import os
import shutil
import subprocess
from pathlib import Path

class Exporter:
    def __init__(self, output_dir: Path, log_fn=None):
        self.output_dir = output_dir
        self.log_fn = log_fn or (lambda x: None)

    def export_as_zip(self) -> Path:
        """Compress the entire output directory into a ZIP file."""
        import zipfile
        zip_path = self.output_dir.parent / f"{self.output_dir.name}.zip"
        
        self.log_fn(f"🗜️ Archiving project to {zip_path.name}...")
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.output_dir):
                    # Bỏ qua thư mục .git nếu có
                    if '.git' in dirs:
                        dirs.remove('.git')
                        
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(self.output_dir)
                        zipf.write(file_path, arcname)
            self.log_fn(f"✅ Created ZIP archive: {zip_path}")
            return zip_path
        except Exception as e:
            self.log_fn(f"❌ Failed to archive to ZIP: {e}")
            return None

    def init_git_repo(self) -> bool:
        """Initialize a local git repository to track the downloaded code."""
        self.log_fn("🔧 Initializing local git repository...")
        try:
            # Check if git is installed
            subprocess.run(['git', '--version'], capture_output=True, check=True)
            
            # Check if already a git repo
            if (self.output_dir / '.git').exists():
                self.log_fn("📦 Target is already a git repository.")
                return True
                
            # Run git init
            subprocess.run(['git', 'init'], cwd=self.output_dir, capture_output=True, check=True)
            subprocess.run(['git', 'add', '.'], cwd=self.output_dir, capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', "Initial commit: Source code extracted by WebGrabber"], 
                           cwd=self.output_dir, capture_output=True, check=True)
                           
            self.log_fn("✅ Local git repository initialized and initial commit created.")
            return True
        except FileNotFoundError:
            self.log_fn("⚠️ Git is not installed or not in PATH. Skipping git init.")
            return False
        except subprocess.CalledProcessError as e:
            self.log_fn(f"⚠️ Git operation failed: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
            return False
        except Exception as e:
            self.log_fn(f"❌ Unexpected error in git initialization: {e}")
            return False
