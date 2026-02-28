# webgrabber/webgrabber/core/batch_processor.py
import asyncio
from typing import List, Callable, Optional
from pathlib import Path
from urllib.parse import urlparse
import threading

from .orchestrator import run_intelligent_capture
from .history_db import HistoryDB

class BatchProcessor:
    """Process multiple URLs in sequence."""

    def __init__(self, 
                 urls: List[str], 
                 base_output_dir: Path, 
                 log_callback: Callable[[str], None], 
                 token_callback: Callable[[str], str] = None,
                 cancel_event: Optional[threading.Event] = None):
        self.urls = urls
        self.base_output_dir = base_output_dir
        self.log_callback = log_callback
        self.token_callback = token_callback
        self.cancel_event = cancel_event
        self.history_db = HistoryDB(self.base_output_dir)

    async def run(self):
        """Execute the batch process."""
        self.log_callback(f"🚀 Starting Batch Process for {len(self.urls)} URLs...")
        
        success_count = 0
        failure_count = 0
        
        for index, url in enumerate(self.urls, 1):
            if self.cancel_event and self.cancel_event.is_set():
                self.log_callback("⏹️ Batch process aborted by user.")
                break
                
            self.log_callback(f"\n[{index}/{len(self.urls)}] Processing: {url}")
            
            # Create a safe directory name based on URL
            parsed_url = urlparse(url)
            safe_dirname = f"{parsed_url.netloc.replace(':', '_')}{parsed_url.path.replace('/', '_')}"
            if not safe_dirname or safe_dirname == "_":
                safe_dirname = f"site_{index}"
            
            target_out_dir = self.base_output_dir / safe_dirname
            
            try:
                # Run complete orchestrator on the URL without auto-preview
                file_tree = await run_intelligent_capture(
                    url=url,
                    output_dir=str(target_out_dir),
                    log_callback=self.log_callback,
                    token_callback=self.token_callback,
                    cancel_event=self.cancel_event,
                    generate_report=True,
                    auto_preview=False
                )
                
                # Check cancellation again
                if self.cancel_event and self.cancel_event.is_set():
                    break
                    
                files_count = len(file_tree) if file_tree else 0
                framework = None
                
                # Try to extract framework info if available
                fw_info_path = target_out_dir / 'framework_info.json'
                if fw_info_path.exists():
                    import json
                    try:
                        with open(fw_info_path, 'r', encoding='utf-8') as f:
                            fw_data = json.load(f)
                            framework = fw_data.get('primary_name') or fw_data.get('primary')
                    except Exception:
                        pass

                self.history_db.record_download(url, str(target_out_dir), "SUCCESS", files_count, framework)
                success_count += 1
                
            except Exception as e:
                self.log_callback(f"❌ Failed to process {url}: {e}")
                self.history_db.record_download(url, str(target_out_dir), "FAILED", error_message=str(e))
                failure_count += 1
                
        self.log_callback(f"\n📊 Batch Update Completed: {success_count} Success | {failure_count} Failed.")
