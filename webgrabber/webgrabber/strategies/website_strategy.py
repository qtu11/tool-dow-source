# Vị trí: webgrabber/webgrabber/strategies/website_strategy.py
import json
from pathlib import Path
from typing import Callable, Optional
import threading
import aiohttp

from ..core.audit_logger import log_audit
from ..core.session_manager import SessionManager
from ..core.download_cache import DownloadCache
from ..crawler.resource_collector import capture_website_full
from ..crawler.path_rewriter import PathRewriter


class WebsiteCaptureStrategy:
    """
    Fallback strategy: Deep crawl website to extract all source code.

    Pipeline hoàn chỉnh:
    1. Download Cache check (incremental download)
    2. UltraCollectorV11 — Network Interception + API Interception + Source Map + SPA Routes
    3. PathRewriter — Chuyển absolute URLs → relative paths → chạy offline
    4. Cache save → incremental download lần sau
    """

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
        """Executes the deep website crawling pipeline."""
        self.log_callback(f"🌐 Executing WebsiteCaptureStrategy for {self.url}")

        try:
            # Get session cookies
            session_cookies = await self.session_manager.get_cookies()
            if session_cookies:
                self.log_callback(f"🍪 Using {len(session_cookies)} saved session cookies")

            # Get config
            ws_config = self.config.get('website_strategy', {})
            max_pages = ws_config.get('max_pages', 50)

            # ===== PHASE 0: Download Cache =====
            cache = DownloadCache(self.output_dir, self.url)
            if cache.has_previous_download:
                self.log_callback(f"📦 Previous download found ({cache.last_download_time})")
                self.log_callback(f"   Only downloading new/changed files...")

            # ===== PHASE 1: Deep Crawl + Network Interception =====
            self.log_callback("📡 Phase 1: Deep crawling with network interception...")
            resources = await capture_website_full(
                url=self.url,
                output_dir=self.output_dir,
                file_callback=self.log_callback,
                session_cookies=session_cookies,
                cancel_event=self.cancel_event,
                max_pages=max_pages,
            )

            if self.cancel_event and self.cancel_event.is_set():
                return {}

            # ===== PHASE 2: Path Rewriting =====
            self.log_callback("🔄 Phase 2: Rewriting URLs for offline access...")
            rewriter = PathRewriter(
                output_dir=self.output_dir,
                base_url=self.url,
                resources=resources,
                log_fn=self.log_callback,
            )
            rewriter.rewrite_all()

            # ===== PHASE 3: Save Download Cache =====
            for url_key, res in resources.items():
                if res.data:
                    cache.should_download(url_key, res.data)
            cache.save_cache()
            self.log_callback(cache.get_summary())

            if self.cancel_event and self.cancel_event.is_set():
                return {}

            source_count = 0

            # ===== PHASE 4: Source Map Brute-force =====
            try:
                from ..crawler.source_map_bruteforcer import SourceMapBruteforcer
                js_urls = [url_key for url_key, res in resources.items()
                           if res.type in ('js',) and url_key.startswith('http')]
                if js_urls:
                    bruteforcer = SourceMapBruteforcer(
                        output_dir=self.output_dir,
                        base_url=self.url,
                        log_fn=self.log_callback,
                    )
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    }
                    connector = aiohttp.TCPConnector(ssl=False, limit=10)
                    async with aiohttp.ClientSession(headers=headers, connector=connector) as bf_session:
                        recovered_sources = await bruteforcer.bruteforce_all(js_urls, bf_session)
                        source_count += len(recovered_sources)
            except Exception as e:
                self.log_callback(f"⚠️ Source Map Brute-force warning: {e}")

            if self.cancel_event and self.cancel_event.is_set():
                return {}

            # ===== PHASE 5: Webpack Debundling =====
            try:
                from ..crawler.js_debundler import WebpackDebundler
                debundler = WebpackDebundler(
                    output_dir=self.output_dir,
                    base_url=self.url,
                    log_fn=self.log_callback,
                )
                debundled_modules = await debundler.debundle_all()
            except Exception as e:
                self.log_callback(f"⚠️ Webpack Debundler warning: {e}")

            if self.cancel_event and self.cancel_event.is_set():
                return {}

            # ===== PHASE 6: Next.js Recon =====
            try:
                from ..crawler.js_debundler import NextJsRecon
                nextjs = NextJsRecon(
                    output_dir=self.output_dir,
                    base_url=self.url,
                    log_fn=self.log_callback,
                )
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                }
                connector = aiohttp.TCPConnector(ssl=False, limit=10)
                async with aiohttp.ClientSession(headers=headers, connector=connector) as nj_session:
                    nextjs_results = await nextjs.reconn(nj_session)
            except Exception as e:
                self.log_callback(f"⚠️ Next.js Recon warning: {e}")

            if self.cancel_event and self.cancel_event.is_set():
                return {}

            # ===== PHASE 7: Git Repo Discovery =====
            try:
                from ..crawler.js_debundler import GitRepoDiscovery
                git_disco = GitRepoDiscovery(
                    output_dir=self.output_dir,
                    base_url=self.url,
                    log_fn=self.log_callback,
                )
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                }
                connector = aiohttp.TCPConnector(ssl=False, limit=5)
                async with aiohttp.ClientSession(headers=headers, connector=connector) as git_session:
                    repo_url = await git_disco.discover(git_session)
                    if repo_url:
                        self.log_callback(f"🎯 Public Git repo found: {repo_url}")
                        self.log_callback(f"   💡 Tip: Use this URL directly for 100% source code!")
            except Exception as e:
                self.log_callback(f"⚠️ Git Repo Discovery warning: {e}")

            # ===== BUILD FILE TREE =====
            tree = {}

            for url_key, res in resources.items():
                if res.save_path and res.save_path.exists():
                    try:
                        rel_path = str(res.save_path.relative_to(self.output_dir))
                        tree[rel_path] = f"Downloaded ({res.type}, {res.size} bytes)"
                    except ValueError:
                        tree[str(res.save_path)] = f"Downloaded ({res.type})"

                if res.original_sources:
                    source_count += len(res.original_sources)

            # Add all recovered directories to tree
            for special_dir in ['_source_maps', '_recovered_source', '_debundled',
                                '_nextjs_recon', '_api_data']:
                dir_path = self.output_dir / special_dir
                if dir_path.exists():
                    for file_path in dir_path.rglob('*'):
                        if file_path.is_file():
                            rel_path = str(file_path.relative_to(self.output_dir))
                            tree[rel_path] = f"Recovered ({special_dir})"

            self.log_callback(f"✅ Website capture complete!")
            self.log_callback(f"   📁 Total files: {len(tree)}")
            self.log_callback(f"   📦 Original sources recovered: {source_count}")
            self.log_callback(f"   🔗 URLs rewritten: {rewriter.rewrite_count}")
            self.log_callback(f"   💡 Check _source_maps/ and _recovered_source/ for original code!")

            return tree

        except Exception as e:
            self.log_callback(f"❌ Error during website capture: {e}")
            import traceback
            log_audit(traceback.format_exc())
            raise
