# webgrabber/webgrabber/crawler/resource_collector.py
"""
UltraCollector v11 — Deep Website Source Code Extractor

Khả năng chính:
1. Network Interception — bắt MỌI request/response qua Playwright (JS, CSS, fonts, images, API calls)
2. Source Map Reconstruction — parse .map files để lấy source code gốc (.tsx, .jsx, .vue, .scss, etc.)
3. Deep HTML/CSS Parsing — phát hiện tài nguyên ẩn trong inline styles, data attributes, meta tags
4. Webpack/Vite Chunk Discovery — phát hiện JS chunks được lazy load
5. Multi-page Crawl — follow internal links để crawl toàn bộ site
6. Proper File Organization — giữ cấu trúc thư mục gốc của website
"""

import asyncio
import aiofiles
import aiohttp
import hashlib
import json
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set, List, Callable
from urllib.parse import urljoin, urlparse, unquote, parse_qs
from playwright.async_api import (
    async_playwright, Page, Response as PlaywrightResponse,
    TimeoutError as PlaywrightTimeoutError
)

try:
    from ..core.audit_logger import log_audit
except (ImportError, ModuleNotFoundError):
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    def log_audit(msg): logging.info(msg)


# ========== Data Models ==========

@dataclass
class Resource:
    url: str
    type: str
    data: Optional[bytes] = None
    status: int = 0
    source: str = ''
    save_path: Optional[Path] = None
    content_type: str = ''
    size: int = 0
    is_source_map: bool = False
    original_sources: List[str] = field(default_factory=list)


# ========== Source Map Extractor ==========

class SourceMapExtractor:
    """Parse .map files và extract source code gốc."""

    @staticmethod
    async def extract_from_map_data(map_data: bytes, output_dir: Path, base_url: str,
                                     log_fn: Callable = None) -> Dict[str, Path]:
        """
        Parse source map JSON, extract sourcesContent → save original source files.
        Returns dict mapping source path → saved file path.
        """
        extracted = {}
        try:
            map_json = json.loads(map_data.decode('utf-8', errors='ignore'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return extracted

        sources = map_json.get('sources', [])
        sources_content = map_json.get('sourcesContent', [])
        source_root = map_json.get('sourceRoot', '')

        if not sources_content:
            return extracted

        source_map_dir = output_dir / '_source_maps'

        for i, source_path in enumerate(sources):
            if i >= len(sources_content) or sources_content[i] is None:
                continue

            content = sources_content[i]

            # Clean up webpack:// or similar prefixes
            clean_path = source_path
            for prefix in ['webpack://', 'webpack-internal:///', 'turbopack://[project]/',
                           'file://', '///', './', '../']:
                clean_path = clean_path.replace(prefix, '')

            # Remove query strings and fragments
            clean_path = clean_path.split('?')[0].split('#')[0]

            # Skip node_modules content (too large, not user code)
            if 'node_modules' in clean_path:
                continue

            # Skip empty/null paths
            if not clean_path or clean_path.startswith('('):
                continue

            # Build save path
            clean_path = clean_path.lstrip('/')
            if source_root:
                clean_path = source_root.strip('/') + '/' + clean_path

            save_path = source_map_dir / clean_path

            try:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(save_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
                extracted[clean_path] = save_path
                if log_fn:
                    log_fn(f"📦 Extracted source: {clean_path}")
            except Exception as e:
                if log_fn:
                    log_fn(f"⚠️ Failed to extract {clean_path}: {e}")

        return extracted


# ========== Main Collector ==========

class UltraCollectorV11:
    """
    Deep website source code collector using Playwright network interception.
    Bắt MỌI tài nguyên website load, bao gồm cả lazy-loaded chunks.
    """

    # Resource types by content-type
    CONTENT_TYPE_MAP = {
        'text/html': 'html', 'application/xhtml+xml': 'html',
        'text/css': 'css',
        'application/javascript': 'js', 'text/javascript': 'js', 'application/x-javascript': 'js',
        'application/json': 'json', 'text/json': 'json',
        'image/png': 'image', 'image/jpeg': 'image', 'image/gif': 'image',
        'image/svg+xml': 'svg', 'image/webp': 'image', 'image/avif': 'image', 'image/x-icon': 'icon',
        'font/woff': 'font', 'font/woff2': 'font', 'application/font-woff': 'font',
        'application/font-woff2': 'font', 'font/ttf': 'font', 'font/otf': 'font',
        'application/octet-stream': 'binary',
        'text/xml': 'xml', 'application/xml': 'xml',
        'text/plain': 'text',
        'application/manifest+json': 'manifest',
        'application/wasm': 'wasm',
    }

    # Extensions mapping for fallback
    EXT_TYPE_MAP = {
        '.js': 'js', '.mjs': 'js', '.cjs': 'js',
        '.css': 'css', '.scss': 'css', '.less': 'css',
        '.html': 'html', '.htm': 'html',
        '.json': 'json', '.jsonp': 'json',
        '.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.gif': 'image',
        '.svg': 'svg', '.webp': 'image', '.avif': 'image', '.ico': 'icon',
        '.woff': 'font', '.woff2': 'font', '.ttf': 'font', '.otf': 'font', '.eot': 'font',
        '.map': 'sourcemap',
        '.xml': 'xml', '.txt': 'text', '.md': 'text',
        '.mp4': 'video', '.webm': 'video', '.ogg': 'audio', '.mp3': 'audio',
        '.wasm': 'wasm', '.pdf': 'binary',
    }

    # Patterns to discover source map URLs in JS/CSS files
    SOURCEMAP_PATTERNS = [
        re.compile(rb'//[#@]\s*sourceMappingURL=(.+?)[\s\n\r]', re.MULTILINE),
        re.compile(rb'/\*[#@]\s*sourceMappingURL=(.+?)\s*\*/', re.MULTILINE),
    ]

    # Patterns to discover additional resources in JS
    JS_RESOURCE_PATTERNS = [
        re.compile(rb'''["']([^"']+\.(?:js|css|json|png|jpg|svg|woff2?|ttf|html))["']'''),
        re.compile(rb'import\s*\(\s*["\']([^"\']+)["\']'),  # dynamic import()
        re.compile(rb'__webpack_require__\.\w+\(["\']([^"\']+)["\']\)'),  # webpack
    ]

    def __init__(self, base_url: str, output_dir: Path, config: dict,
                 file_callback: Callable = None, proxy: str = None,
                 cancel_event: threading.Event = None,
                 session_cookies: list = None,
                 max_pages: int = 50):
        self.base_url = base_url.rstrip('/')
        self.base_domain = urlparse(base_url).netloc.lower()
        self.output_dir = output_dir
        self.config = config
        self.file_callback = file_callback
        self.proxy = proxy
        self.cancel_event = cancel_event or threading.Event()
        self.session_cookies = session_cookies or []
        self.max_pages = max_pages

        # State
        self.resources: Dict[str, Resource] = {}
        self.seen_urls: Set[str] = set()
        self.pages_crawled: Set[str] = set()
        self.pages_queue: asyncio.Queue = asyncio.Queue()
        self.source_maps_found: Dict[str, str] = {}  # js_url → map_url
        self.stats = defaultdict(int)

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def _log(self, msg: str):
        if self.file_callback:
            self.file_callback(msg)
        log_audit(msg)

    # ========== Network Interception ==========

    async def _on_response(self, response: PlaywrightResponse):
        """Callback cho MỌI response từ browser — bắt tất cả tài nguyên."""
        if self._is_cancelled():
            return

        url = response.url
        status = response.status

        # Skip data URLs, blob URLs
        if url.startswith(('data:', 'blob:', 'about:')):
            return

        # Skip already captured
        if url in self.resources:
            return

        # Skip non-success
        if status < 200 or status >= 400:
            return

        try:
            body = await response.body()
        except Exception:
            return

        if not body:
            return

        content_type = response.headers.get('content-type', '')
        res_type = self._detect_type(url, content_type)

        # Save resource
        save_path = await self._save_resource(url, body, res_type)
        resource = Resource(
            url=url, type=res_type, data=body, status=status,
            source='network_intercept', save_path=save_path,
            content_type=content_type, size=len(body),
            is_source_map=(res_type == 'sourcemap')
        )
        self.resources[url] = resource
        self.stats[res_type] += 1

        # Check for source maps in JS/CSS
        if res_type in ('js', 'css'):
            await self._discover_sourcemap(url, body)
            if res_type == 'js':
                self._discover_js_resources(url, body)

        # Check for source maps (auto-captured .map files)
        if res_type == 'sourcemap' and body:
            extracted = await SourceMapExtractor.extract_from_map_data(
                body, self.output_dir, url, self._log
            )
            resource.original_sources = list(extracted.keys())
            self.stats['source_extracted'] += len(extracted)

    async def _discover_sourcemap(self, source_url: str, content: bytes):
        """Tìm sourceMappingURL trong JS/CSS content."""
        for pattern in self.SOURCEMAP_PATTERNS:
            match = pattern.search(content)
            if match:
                map_ref = match.group(1).decode('utf-8', errors='ignore').strip()
                # Skip inline base64 source maps
                if map_ref.startswith('data:'):
                    # Extract inline source map
                    try:
                        b64_data = map_ref.split(',', 1)[1]
                        import base64
                        map_data = base64.b64decode(b64_data)
                        extracted = await SourceMapExtractor.extract_from_map_data(
                            map_data, self.output_dir, source_url, self._log
                        )
                        self.stats['source_extracted'] += len(extracted)
                    except Exception:
                        pass
                    return

                map_url = urljoin(source_url, map_ref)
                if map_url not in self.seen_urls:
                    self.seen_urls.add(map_url)
                    self.source_maps_found[source_url] = map_url
                break

    def _discover_js_resources(self, source_url: str, content: bytes):
        """Phát hiện thêm tài nguyên được reference trong JS (chunks, assets)."""
        for pattern in self.JS_RESOURCE_PATTERNS:
            for match in pattern.finditer(content):
                ref = match.group(1).decode('utf-8', errors='ignore')
                if ref.startswith(('http', '//', '/')):
                    full_url = urljoin(source_url, ref)
                elif not ref.startswith(('.', 'node_modules', '@')):
                    full_url = urljoin(source_url, ref)
                else:
                    continue
                if full_url not in self.seen_urls and self._is_same_domain(full_url):
                    self.seen_urls.add(full_url)

    # ========== Page Crawling ==========

    async def _crawl_page(self, page: Page, url: str):
        """Crawl một page: navigate, chờ load, extract links."""
        if self._is_cancelled() or url in self.pages_crawled:
            return
        if len(self.pages_crawled) >= self.max_pages:
            return

        self.pages_crawled.add(url)
        self._log(f"🔍 Crawling page: {url}")

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
        except PlaywrightTimeoutError:
            self._log(f"⏱️ Timeout on {url}, proceeding with partial content.")
        except Exception as e:
            self._log(f"⚠️ Navigation error on {url}: {e}")
            return

        # Wait for dynamic content
        await asyncio.sleep(1)

        # Scroll to trigger lazy loading
        await self._scroll_page(page)

        # Extract HTML content
        try:
            html = await page.content()
            save_path = await self._save_resource(url, html.encode('utf-8'), 'html')
            self.resources[url] = Resource(
                url=url, type='html', data=html.encode('utf-8'),
                status=200, source='page_crawl', save_path=save_path,
                size=len(html)
            )
        except Exception:
            pass

        # Discover internal links
        try:
            links = await page.eval_on_selector_all(
                'a[href]',
                '''elements => elements.map(e => e.href).filter(h =>
                    h && !h.startsWith('javascript:') && !h.startsWith('mailto:') &&
                    !h.startsWith('#') && !h.startsWith('tel:')
                )'''
            )
            for link in links:
                clean_link = link.split('#')[0].split('?')[0].rstrip('/')
                if (clean_link and clean_link not in self.pages_crawled
                        and self._is_same_domain(clean_link)
                        and len(self.pages_crawled) < self.max_pages):
                    await self.pages_queue.put(clean_link)
        except Exception:
            pass

    async def _scroll_page(self, page: Page):
        """Scroll từ từ để trigger lazy loading."""
        try:
            total_height = await page.evaluate('document.body.scrollHeight')
            viewport_height = await page.evaluate('window.innerHeight')
            current = 0
            while current < total_height and not self._is_cancelled():
                current += viewport_height
                await page.evaluate(f'window.scrollTo(0, {current})')
                await asyncio.sleep(0.3)
            # Scroll lại top
            await page.evaluate('window.scrollTo(0, 0)')
            await asyncio.sleep(0.5)
        except Exception:
            pass

    # ========== Source Map Fetching ==========

    async def _fetch_pending_sourcemaps(self, session: aiohttp.ClientSession):
        """Download các .map files đã phát hiện nhưng chưa được browser load."""
        pending_maps = {
            js_url: map_url for js_url, map_url in self.source_maps_found.items()
            if map_url not in self.resources
        }

        if not pending_maps:
            return

        self._log(f"📥 Fetching {len(pending_maps)} source maps...")

        for js_url, map_url in pending_maps.items():
            if self._is_cancelled():
                break
            try:
                async with session.get(map_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        save_path = await self._save_resource(map_url, data, 'sourcemap')
                        self.resources[map_url] = Resource(
                            url=map_url, type='sourcemap', data=data,
                            status=200, source='sourcemap_fetch', save_path=save_path,
                            size=len(data), is_source_map=True
                        )
                        self.stats['sourcemap'] += 1

                        # Extract source
                        extracted = await SourceMapExtractor.extract_from_map_data(
                            data, self.output_dir, map_url, self._log
                        )
                        self.stats['source_extracted'] += len(extracted)
            except Exception as e:
                self._log(f"⚠️ Failed to fetch source map {map_url}: {e}")

    # ========== Deep HTML Analysis ==========

    async def _deep_analyze_html(self, session: aiohttp.ClientSession):
        """Phân tích HTML thêm để tìm tài nguyên bị miss bởi network interception."""
        html_resources = [r for r in self.resources.values() if r.type == 'html' and r.data]

        additional_urls = set()
        for resource in html_resources:
            html = resource.data.decode('utf-8', errors='ignore')

            # Tìm tài nguyên trong HTML
            patterns = [
                # <link href="...">
                re.compile(r'<link[^>]+href=["\']((?!data:|#|mailto:)[^"\']+)["\']', re.I),
                # <script src="...">
                re.compile(r'<script[^>]+src=["\']((?!data:)[^"\']+)["\']', re.I),
                # <img src="...">
                re.compile(r'<img[^>]+src=["\']((?!data:)[^"\']+)["\']', re.I),
                # url() in inline styles
                re.compile(r'url\(["\']?((?!data:)[^"\')\s]+)["\']?\)'),
                # og:image, twitter:image meta
                re.compile(r'<meta[^>]+content=["\'](https?://[^"\']+\.(png|jpg|jpeg|svg|webp))["\']', re.I),
                # manifest.json, favicon
                re.compile(r'<link[^>]+href=["\'](/[^"\']+(?:manifest|favicon|apple-touch)[^"\']*)["\']', re.I),
                # preload/prefetch
                re.compile(r'<link[^>]+rel=["\'](preload|prefetch)["\'][^>]+href=["\']((?!data:)[^"\']+)["\']', re.I),
            ]

            for pattern in patterns:
                for match in pattern.finditer(html):
                    # Handle preload pattern that has 2 groups
                    ref = match.group(2) if match.lastindex >= 2 and 'preload' in pattern.pattern else match.group(1)
                    full_url = urljoin(resource.url, ref)
                    if full_url not in self.resources and full_url not in additional_urls:
                        additional_urls.add(full_url)

        if not additional_urls:
            return

        self._log(f"🔎 Found {len(additional_urls)} additional resources in HTML analysis")

        # Download missing resources
        tasks = [self._fetch_additional(session, url) for url in additional_urls]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_additional(self, session: aiohttp.ClientSession, url: str):
        """Fetch một resource bổ sung."""
        if self._is_cancelled() or url in self.resources:
            return
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    content_type = resp.headers.get('Content-Type', '')
                    res_type = self._detect_type(url, content_type)
                    save_path = await self._save_resource(url, data, res_type)
                    self.resources[url] = Resource(
                        url=url, type=res_type, data=data,
                        status=200, source='deep_analysis', save_path=save_path,
                        content_type=content_type, size=len(data)
                    )
                    self.stats[res_type] += 1

                    if res_type in ('js', 'css'):
                        await self._discover_sourcemap(url, data)
        except Exception:
            pass

    # ========== File Management ==========

    def _detect_type(self, url: str, content_type: str = '') -> str:
        """Detect resource type from content-type and URL extension."""
        # Check content-type first
        ct_lower = content_type.lower().split(';')[0].strip()
        mapped = self.CONTENT_TYPE_MAP.get(ct_lower)
        if mapped:
            return mapped

        # Check URL for .map extension
        parsed_path = urlparse(url).path.lower()
        if parsed_path.endswith('.map'):
            return 'sourcemap'

        # Check extension
        ext = Path(parsed_path).suffix.lower()
        mapped = self.EXT_TYPE_MAP.get(ext)
        if mapped:
            return mapped

        return 'unknown'

    async def _save_resource(self, url: str, content: bytes, res_type: str) -> Optional[Path]:
        """Save resource to disk with proper directory structure."""
        if self._is_cancelled():
            return None
        try:
            save_path = self._get_save_path(url, res_type)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(save_path, 'wb') as f:
                await f.write(content)
            return save_path
        except Exception as e:
            log_audit(f"Failed to save {url}: {e}")
            return None

    def _get_save_path(self, url: str, res_type: str) -> Path:
        """Map URL to local file path, preserving directory structure."""
        parsed = urlparse(url)
        netloc = parsed.netloc.replace(':', '_') or self.base_domain
        path = unquote(parsed.path).lstrip('/')

        if not path or path.endswith('/'):
            path = path.rstrip('/') + '/index.html' if path else 'index.html'

        # Handle query strings (common in versioned assets)
        if parsed.query:
            # Keep query for uniqueness but sanitize
            safe_query = re.sub(r'[<>:"|?*]', '_', parsed.query)[:30]
            stem = Path(path).stem
            suffix = Path(path).suffix
            if suffix:
                path = str(Path(path).parent / f"{stem}_{safe_query}{suffix}")

        # Sanitize path segments
        parts = path.split('/')
        safe_parts = []
        for part in parts:
            part = re.sub(r'[<>:"|?*\\]', '_', part)
            if len(part) > 100:
                ext = Path(part).suffix
                part = hashlib.sha1(part.encode()).hexdigest()[:20] + ext
            safe_parts.append(part)

        # Add extension if missing
        filename = safe_parts[-1]
        if '.' not in filename and res_type != 'unknown':
            ext_map = {'html': '.html', 'js': '.js', 'css': '.css', 'json': '.json',
                       'svg': '.svg', 'image': '.png', 'font': '.woff2', 'sourcemap': '.map'}
            filename += ext_map.get(res_type, '')
            safe_parts[-1] = filename

        # Same domain → root, cross-domain → subdirectory
        if netloc == self.base_domain:
            return self.output_dir / Path(*safe_parts)
        else:
            return self.output_dir / '_external' / netloc / Path(*safe_parts)

    def _is_same_domain(self, url: str) -> bool:
        """Check if URL belongs to same domain."""
        try:
            return urlparse(url).netloc.lower() == self.base_domain
        except Exception:
            return False

    # ========== Main Entry Point ==========

    async def collect_all(self) -> Dict[str, Resource]:
        """
        Main method — khởi chạy Playwright, intercept network, crawl pages, extract sources.
        """
        self._log("🚀 Starting deep source code extraction...")

        # Import stealth module
        from .stealth import create_stealth_context, human_like_scroll

        async with async_playwright() as p:
            # Launch browser
            launch_args = ['--no-sandbox', '--disable-dev-shm-usage',
                           '--disable-blink-features=AutomationControlled']
            browser = await p.chromium.launch(
                headless=True,
                args=launch_args,
            )

            # Use stealth context instead of regular context
            context = await create_stealth_context(
                browser,
                session_cookies=self.session_cookies,
                proxy=self.proxy,
            )

            page = await context.new_page()

            # ===== API INTERCEPTION =====
            from .api_interceptor import APIInterceptor
            self.api_interceptor = APIInterceptor(self.base_url, self.output_dir, self._log)
            page.on('response', self.api_interceptor.on_response)

            # ===== NETWORK INTERCEPTION =====
            page.on('response', self._on_response)

            # ===== CRAWL FIRST PAGE =====
            await self._crawl_page(page, self.base_url)

            # ===== CRAWL ADDITIONAL PAGES =====
            while not self.pages_queue.empty() and not self._is_cancelled():
                if len(self.pages_crawled) >= self.max_pages:
                    break
                try:
                    next_url = self.pages_queue.get_nowait()
                    if next_url not in self.pages_crawled:
                        await self._crawl_page(page, next_url)
                except asyncio.QueueEmpty:
                    break

            await browser.close()

        if self._is_cancelled():
            self._log("⏹️ Cancelled by user.")
            return self.resources

        # ===== POST-PROCESSING: Fetch source maps & deep analysis =====
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
        }
        connector = aiohttp.TCPConnector(ssl=False, limit=20)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            await self._fetch_pending_sourcemaps(session)
            await self._deep_analyze_html(session)
            await self._fetch_pending_sourcemaps(session)

        # ===== SAVE API DATA =====
        if hasattr(self, 'api_interceptor') and self.api_interceptor.api_calls:
            self.api_interceptor.save_results()
            self._log(self.api_interceptor.get_summary())

        # ===== DISCOVER SPA ROUTES =====
        self._discover_spa_routes()

        # ===== REPORT =====
        self._print_stats()
        return self.resources

    def _discover_spa_routes(self):
        """Discover SPA routes from JS bundles (React Router, Vue Router, etc.)."""
        route_patterns = [
            # React Router
            re.compile(rb'path:\s*["\'](/[^"\']*)["\']'),
            re.compile(rb'Route\s+path=["\'](/[^"\']*)["\']'),
            # Vue Router
            re.compile(rb'path:\s*["\'](/[^"\']*)["\'].*?component'),
            # Next.js pages
            re.compile(rb'__NEXT_DATA__.*?"page"\s*:\s*"(/[^"]*)"'),
            # Generic route patterns
            re.compile(rb'routes?\s*[:=]\s*\[.*?path:\s*["\'](/[^"\']+)["\']', re.DOTALL),
        ]

        discovered_routes = set()

        for url, resource in self.resources.items():
            if resource.type != 'js' or not resource.data:
                continue
            for pattern in route_patterns:
                for match in pattern.finditer(resource.data):
                    route = match.group(1).decode('utf-8', errors='ignore')
                    if route and not route.startswith('//') and len(route) < 100:
                        discovered_routes.add(route)

        if discovered_routes:
            self._log(f"🗺️ Discovered {len(discovered_routes)} SPA routes: {', '.join(sorted(discovered_routes)[:10])}")
            # Save routes to file
            routes_path = self.output_dir / 'spa_routes.json'
            import json
            with open(routes_path, 'w', encoding='utf-8') as f:
                json.dump(sorted(discovered_routes), f, indent=2)

    def _print_stats(self):
        """Print collection statistics."""
        total = len(self.resources)
        self._log(f"\n{'='*50}")
        self._log(f"📊 Collection Complete — {total} resources captured")
        self._log(f"   Pages crawled: {len(self.pages_crawled)}")
        for rtype, count in sorted(self.stats.items()):
            emoji = {'html': '📄', 'js': '⚡', 'css': '🎨', 'image': '🖼️',
                     'font': '🔤', 'svg': '🎯', 'json': '📋', 'sourcemap': '🗺️',
                     'source_extracted': '📦'}.get(rtype, '📁')
            self._log(f"   {emoji} {rtype}: {count}")
        self._log(f"{'='*50}\n")


# ========== Public Entry Point ==========

async def capture_website_full(url: str, output_dir: Path, file_callback=None,
                                proxy=None, session_cookies=None,
                                cancel_event=None, max_pages=50) -> Dict[str, Resource]:
    """
    Main entry point — download toàn bộ source code của website.

    Args:
        url: Target URL
        output_dir: Directory to save files
        file_callback: Logging callback function
        proxy: Optional proxy URL
        session_cookies: List of cookie dicts for authenticated access
        cancel_event: Threading event for cancellation
        max_pages: Maximum number of pages to crawl (default 50)

    Returns:
        Dict mapping URL → Resource objects
    """
    config = {
        'concurrency': 20,
        'render_js': True,
    }

    collector = UltraCollectorV11(
        base_url=url,
        output_dir=output_dir,
        config=config,
        file_callback=file_callback,
        proxy=proxy,
        cancel_event=cancel_event,
        session_cookies=session_cookies or [],
        max_pages=max_pages,
    )

    resources = await collector.collect_all()
    return resources
