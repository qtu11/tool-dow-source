# Vị trí: webgrabber/webgrabber/strategies/website_strategy.py
from pathlib import Path
from typing import Callable, Optional
import threading

from ..core.audit_logger import log_audit
from ..core.session_manager import SessionManager
# Assuming a function 'capture_website_full' exists and works as expected
from ..crawler.resource_collector import capture_website_full 

class WebsiteCaptureStrategy:
    """The fallback strategy: captures a website by crawling it."""

    def __init__(self,
                 url: str,
                 output_dir: Path,
                 config: dict,
                 session_manager: SessionManager,
                 log_callback: Callable[[str], None],
                 token_callback: Optional[Callable[[str], str]] = None,
                 cancel_event: Optional[threading.Event] = None):
        self.url = url
        self.output_dir = output_dir
        self.config = config
        self.session_manager = session_manager
        self.log_callback = log_callback
        self.cancel_event = cancel_event

    async def download(self) -> dict:
        """Executes the website crawling process."""
        self.log_callback(f"Executing fallback WebsiteCaptureStrategy for {self.url}")
        try:
            # Use the get_cookies method from SessionManager
            session_cookies = await self.session_manager.get_cookies()

            # Call the main crawling function
            # Note: The original code had a note about changing 'log_callback' to 'file_callback'.
            # This depends on the signature of 'capture_website_full'. We assume it expects 'file_callback'.
            resources = await capture_website_full(
                url=self.url,
                output_dir=self.output_dir,
                file_callback=self.log_callback,
                session_cookies=session_cookies,
                cancel_event=self.cancel_event
            )
            
            self.log_callback(f"Website capture completed. Found {len(resources)} resources.")
            
            tree = {
                str(res.save_path.relative_to(self.output_dir)): "Downloaded resource" 
                for res in resources.values() 
                if res.save_path
            }
            return tree
        except Exception as e:
            self.log_callback(f"An error occurred during website capture: {e}")
            import traceback
            log_audit(traceback.format_exc())
            raise
