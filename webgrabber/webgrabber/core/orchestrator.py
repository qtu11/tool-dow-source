# Vị trí: /webgrabber/webgrabber/core/orchestrator.py

import asyncio
import json
import threading
from pathlib import Path
from typing import Optional, Callable

from .audit_logger import log_audit
from .config_manager import ConfigManager
from .platform_detector import PlatformDetector
from .framework_detector import FrameworkDetector
from .session_manager import SessionManager
from .preview_server import PreviewServer
# Import strategy classes
from ..strategies.git_strategy import GitStrategy
from ..strategies.github_api_strategy import GitHostingAPIStrategy
from ..strategies.paas_strategy import PaasStrategy
from ..strategies.ssh_strategy import SshStrategy
from ..strategies.website_strategy import WebsiteCaptureStrategy

# Defines the mapping from platform type to strategy class
STRATEGY_MAP = {
    'git_hosting': GitHostingAPIStrategy,  # API download thay vì git clone
    'paas': PaasStrategy,
    'ssh_hosting': SshStrategy,
}


async def run_intelligent_capture(
    url: str,
    output_dir: str,
    log_callback: Callable[[str], None],
    token_callback: Callable[[str], str],
    cancel_event: Optional[threading.Event] = None,
    generate_report: bool = True,
    auto_preview: bool = False,
):
    """
    The main orchestrator — Detect → Strategize → Execute → Report → Preview.

    Args:
        url: Target URL to capture source code from.
        output_dir: Directory to save downloaded files.
        log_callback: Function to send log messages to (GUI/CLI).
        token_callback: Function to request authentication tokens.
        cancel_event: Threading event to signal cancellation.
        generate_report: Generate manifest and tree report after download.
        auto_preview: Start local preview server after download.
    """
    log_callback("🚀 Initializing WebGrabber v1.0...")
    config_manager = ConfigManager()
    config = config_manager.get_config()

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    session_manager = SessionManager(url, log_callback)

    # ===== PHASE 1: Platform Detection =====
    log_callback(f"🔍 Analyzing URL: {url}")
    platform_info = PlatformDetector.detect(url)
    platform_name = platform_info.get('name', 'Unknown')
    platform_type = platform_info.get('type', 'unknown')
    log_callback(f"🎯 Detected Platform: {platform_name} ({platform_type})")

    # ===== PHASE 2: Strategy Selection =====
    StrategyClass = STRATEGY_MAP.get(platform_type, WebsiteCaptureStrategy)
    log_callback(f"⚙️ Strategy: {StrategyClass.__name__}")

    try:
        strategy_instance = StrategyClass(
            url=url,
            output_dir=output_path,
            config=config,
            session_manager=session_manager,
            log_callback=log_callback,
            token_callback=token_callback,
            cancel_event=cancel_event,
        )

        # ===== PHASE 3: Execute Download =====
        log_callback(f"📥 Downloading...")
        try:
            file_tree = await strategy_instance.download()
        except Exception as strategy_error:
            # Fallback: nếu strategy chuyên biệt fail → dùng WebsiteCaptureStrategy
            if StrategyClass is not WebsiteCaptureStrategy:
                log_callback(f"⚠️ {StrategyClass.__name__} failed: {strategy_error}")
                log_callback(f"🔄 Falling back to WebsiteCaptureStrategy...")
                fallback = WebsiteCaptureStrategy(
                    url=url,
                    output_dir=output_path,
                    config=config,
                    session_manager=session_manager,
                    log_callback=log_callback,
                    token_callback=token_callback,
                    cancel_event=cancel_event,
                )
                file_tree = await fallback.download()
            else:
                raise

        if cancel_event and cancel_event.is_set():
            log_callback("⏹️ Download cancelled.")
            return file_tree or {}

        # ===== PHASE 4: Framework Detection =====
        framework_result = _detect_framework(output_path, log_callback)

        # ===== PHASE 5: Project Reconstruction =====
        _reconstruct_project(output_path, url, framework_result, log_callback)

        # ===== PHASE 6: Export Data (ZIP / Git) =====
        # Optional: We initialize git repo if configured
        export_config = config.get('export', {})
        if export_config.get('init_git', False):
            from ..output.exporter import Exporter
            Exporter(output_path, log_callback).init_git_repo()
            
        if export_config.get('export_zip', False):
            from ..output.exporter import Exporter
            Exporter(output_path, log_callback).export_as_zip()

        # ===== PHASE 7: Generate Report =====
        if generate_report and file_tree:
            _generate_download_report(url, output_path, file_tree, log_callback)

        # ===== PHASE 8: Auto Preview =====
        if auto_preview and file_tree:
            preview = PreviewServer(output_path, log_callback=log_callback)
            preview.start()
            preview.open_browser()
            log_callback(f"🌐 Preview: {preview.url}")
            
        # Record successful download
        from .history_db import HistoryDB
        try:
            db = HistoryDB(output_path.parent)
            fw_name = framework_result.get('primary_name') if framework_result else None
            db.record_download(url, str(output_path), "SUCCESS", len(file_tree) if file_tree else 0, fw_name)
        except Exception as _e:
            pass

        return file_tree

    except asyncio.CancelledError:
        log_callback("⏹️ Download cancelled.")
        return {}
    except Exception as e:
        log_callback(f"❌ Error: {e}")
        # Record failed download
        from .history_db import HistoryDB
        try:
            db = HistoryDB(Path(output_dir).parent)
            db.record_download(url, str(output_dir), "FAILED", error_message=str(e))
        except Exception:
            pass
        raise
    finally:
        await session_manager.close_browser()


def _detect_framework(output_path: Path, log_callback):
    """Detect framework from downloaded HTML files."""
    try:
        index_html = output_path / 'index.html'
        if not index_html.exists():
            html_files = list(output_path.rglob('*.html'))
            if html_files:
                index_html = html_files[0]
            else:
                return {}

        html_content = index_html.read_text(encoding='utf-8', errors='ignore')
        result = FrameworkDetector.detect_from_html(html_content)
        summary = FrameworkDetector.get_summary(result)
        log_callback(f"🔬 Framework detected: {summary}")

        json_result = {
            'primary': result['primary']['id'] if result.get('primary') else None,
            'primary_name': result['primary'].get('name') if result.get('primary') else None,
            'confidence': result['primary'].get('confidence') if result.get('primary') else 0,
            'build_tool': result.get('build_tool'),
            'all_detected': [
                {'id': d['id'], 'confidence': d['confidence']}
                for d in result.get('detected', [])
            ]
        }

        detection_path = output_path / 'framework_info.json'
        with open(detection_path, 'w', encoding='utf-8') as f:
            json.dump(json_result, f, indent=2)

        return json_result

    except Exception as e:
        log_callback(f"⚠️ Framework detection: {e}")
        return {}


def _reconstruct_project(output_path: Path, source_url: str, framework_info: dict, log_callback):
    """Generate runnable project config (package.json, README, serve.json)."""
    try:
        from ..output.project_reconstructor import ProjectReconstructor
        framework_info = framework_info or {}
        framework_info['source_url'] = source_url

        reconstructor = ProjectReconstructor(
            output_dir=output_path,
            framework_info=framework_info,
            log_fn=log_callback,
        )
        reconstructor.reconstruct()
    except Exception as e:
        log_callback(f"⚠️ Project reconstruction: {e}")


def _generate_download_report(url: str, output_path: Path, file_tree: dict, log_callback):
    """Generate summary reports after download."""
    try:
        tree_path = output_path / "file_tree.json"
        with open(tree_path, 'w', encoding='utf-8') as f:
            json.dump(file_tree, f, indent=2, ensure_ascii=False)

        summary = {
            "source_url": url,
            "total_files": len(file_tree),
            "output_dir": str(output_path),
        }
        summary_path = output_path / "download_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        log_callback(f"📊 Report: {len(file_tree)} files → {summary_path.name}")
    except Exception as e:
        log_callback(f"⚠️ Report generation: {e}")

