# Vị trí: /webgrabber/webgrabber/core/orchestrator.py

import asyncio
import threading
from pathlib import Path
from typing import Optional

from .audit_logger import log_audit
from .config_manager import ConfigManager
from .platform_detector import PlatformDetector
from .session_manager import SessionManager
# Import strategy classes
from ..strategies.git_strategy import GitStrategy
from ..strategies.paas_strategy import PaasStrategy
from ..strategies.ssh_strategy import SshStrategy
from ..strategies.website_strategy import WebsiteCaptureStrategy

# Defines the mapping from platform type to strategy class
STRATEGY_MAP = {
    'git_hosting': GitStrategy,
    'paas': PaasStrategy,
    'ssh_hosting': SshStrategy,
}

async def run_intelligent_capture(
    url: str,
    output_dir: str,
    log_callback,
    token_callback,
    # FIX: Use Optional[threading.Event] to allow the default value of None.
    cancel_event: Optional[threading.Event] = None
):
    """
    The main orchestrator function that runs the Detect -> Strategize -> Execute pipeline.
    """
    log_callback("Initializing...")
    config_manager = ConfigManager()
    config = config_manager.get_config()
    log_callback("Configuration loaded.")

    output_path = Path(output_dir)
    session_manager = SessionManager(url, log_callback)
    
    log_callback(f"Analyzing URL: {url}...")
    platform_info = PlatformDetector.detect(url)
    platform_name = platform_info.get('name', 'Unknown')
    platform_type = platform_info.get('type', 'unknown')
    log_callback(f"Detected Platform: {platform_name}")

    # Select the appropriate strategy, or fall back to WebsiteCaptureStrategy
    StrategyClass = STRATEGY_MAP.get(platform_type, WebsiteCaptureStrategy)
    log_callback(f"Selected Strategy: {StrategyClass.__name__}")

    try:
        # Initialize the strategy with necessary resources
        strategy_instance = StrategyClass(
            url=url,
            output_dir=output_path,
            config=config,
            session_manager=session_manager,
            log_callback=log_callback,
            token_callback=token_callback,
            cancel_event=cancel_event  # Pass the cancellation event
        )
        
        log_callback(f"Executing {StrategyClass.__name__}...")
        file_tree = await strategy_instance.download()
        
        return file_tree

    except asyncio.CancelledError:
        log_callback("Download was cancelled.")
        return {}
    except Exception as e:
        log_callback(f"Execution failed in strategy {StrategyClass.__name__}: {e}")
        raise  # Re-raise the exception for the GUI to handle
    finally:
        # FIX: Call the new close_browser method to clean up any open Playwright sessions.
        await session_manager.close_browser()
