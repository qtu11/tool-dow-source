# Vị trí lưu: webgrabber/crawler/resource_collector.py

import asyncio
import aiofiles
import aiohttp
import hashlib
import re
import threading
from bs4 import BeautifulSoup
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set
from urllib.parse import urljoin, urlparse, unquote
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

try:
    from ..core.audit_logger import log_audit
except (ImportError, ModuleNotFoundError):
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    def log_audit(msg): logging.info(msg)

@dataclass
class Resource:
    url: str
    type: str
    data: Optional[bytes] = None
    status: int = 0
    source: str = ''
    save_path: Optional[Path] = None

class UltraCollectorV10:
    """
    Collector nâng cao với khả năng dừng tiến trình.
    """
    def __init__(self, base_url: str, output_dir: Path, config: dict, file_callback=None, proxy: str = None, cancel_event: threading.Event = None):
        self.base_url = base_url
        self.output_dir = output_dir
        self.config = config
        self.file_callback = file_callback
        self.proxy = proxy
        self.cancel_event = cancel_event or threading.Event()
        
        self.seen_urls: Set[str] = set()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.resources: Dict[str, Resource] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def collect_all(self, page: Page) -> Dict[str, Resource]:
        """Bắt đầu quá trình thu thập, bao gồm cả việc giám sát sự kiện hủy."""
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(headers=headers, connector=connector)

        await self.queue.put(self.base_url)
        html_content = await page.content()
        await self._parse_html_deep(html_content, self.base_url)

        workers = [asyncio.create_task(self._worker()) for _ in range(self.config.get('concurrency', 20))]

        # Task giám sát sự kiện hủy
        monitor_task = asyncio.create_task(self._monitor_cancel())
        
        await self.queue.join()

        # Dọn dẹp
        monitor_task.cancel()
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, monitor_task, return_exceptions=True)
        
        await self.session.close()
        return self.resources

    async def _monitor_cancel(self):
        """Task chạy ngầm để kiểm tra sự kiện hủy và dừng queue."""
        while not self.cancel_event.is_set():
            await asyncio.sleep(0.5)
        
        log_audit("Cancellation signal received, clearing queue and stopping workers.")
        # Xóa queue để các worker thoát nhanh hơn
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def _worker(self):
        """Worker xử lý URL từ queue, có kiểm tra sự kiện hủy."""
        while not self.cancel_event.is_set():
            try:
                url = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                await self._process_url(url)
                self.queue.task_done()
            except asyncio.TimeoutError:
                # Hết giờ chờ không có nghĩa là lỗi, chỉ là queue đang trống
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_audit(f"Error in worker: {e}")

    async def _process_url(self, url: str):
        """Tải, lưu, và phân tích URL, có kiểm tra sự kiện hủy."""
        if self.cancel_event.is_set(): return
        try:
            res_type, content, status = await self._download_resource(url)
            if content is None: return

            save_path = await self._save_resource(url, content, res_type)
            self.resources[url] = Resource(url=url, type=res_type, data=content, status=status, save_path=save_path)
            
            if self.file_callback and save_path: self.file_callback(str(save_path.relative_to(self.output_dir)))

            if res_type == 'html': await self._parse_html_deep(content.decode('utf-8', 'ignore'), url)
            elif res_type == 'css': await self._parse_css(content.decode('utf-8', 'ignore'), url)
        except Exception as e:
            log_audit(f"Failed to process URL {url}: {e}")
            self.resources[url] = Resource(url=url, type='unknown', status=500, source='download_error')

    async def _download_resource(self, url: str):
        """Tải tài nguyên, có kiểm tra sự kiện hủy."""
        if self.cancel_event.is_set(): return 'cancelled', None, -1
        try:
            async with self.session.get(url, proxy=self.proxy, timeout=30) as response:
                content = await response.read()
                content_type = response.headers.get('Content-Type', '').lower()
                res_type = self._guess_type(url, content_type)
                log_audit(f"Downloaded {url} (Status: {response.status}, Type: {res_type})")
                return res_type, content, response.status
        except Exception as e:
            log_audit(f"Download error for {url}: {e}")
            return 'unknown', None, 500
    
    def _guess_type(self, url, content_type):
        if 'html' in content_type: return 'html'
        if 'css' in content_type: return 'css'
        if 'javascript' in content_type: return 'js'
        if 'image' in content_type: return 'image'
        if 'font' in content_type: return 'font'
        ext = Path(urlparse(url).path).suffix.lower()
        if ext in ['.js', '.css', '.html', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.eot']:
            return ext.replace('.', '')
        return 'unknown'

    async def _save_resource(self, url: str, content: bytes, res_type: str) -> Optional[Path]:
        if self.cancel_event.is_set(): return None
        try:
            save_path = self._get_save_path(url, res_type)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(save_path, 'wb') as f: await f.write(content)
            return save_path
        except Exception as e:
            log_audit(f"File save error for {url}: {e}")
            return None

    def _get_save_path(self, url: str, res_type: str) -> Path:
        parsed = urlparse(url)
        path = unquote(parsed.path)
        netloc = parsed.netloc.replace(':', '_')
        path_parts = [p for p in path.split('/') if p]
        filename = path_parts.pop() if path_parts and '.' in path_parts[-1] else 'index.html'
        safe_parts = [p if len(p) <= 50 else hashlib.sha1(p.encode()).hexdigest()[:16] for p in path_parts]
        if len(filename) > 50:
            ext = Path(filename).suffix or ('.' + res_type if res_type != 'unknown' else '.html')
            hashed_filename = hashlib.sha1(filename.encode()).hexdigest()[:16] + ext
        else: hashed_filename = filename
        if not Path(hashed_filename).suffix and res_type not in ['unknown', 'html']:
            hashed_filename += '.' + res_type
        return self.output_dir / netloc / Path(*safe_parts) / hashed_filename

    async def _parse_html_deep(self, html_content: str, source_url: str):
        if self.cancel_event.is_set(): return
        soup = BeautifulSoup(html_content, 'html.parser')
        resource_map = { 'img': ['src', 'srcset'], 'script': ['src'], 'link': ['href'], 'video': ['src', 'poster'], 'audio': ['src'], 'source': ['src', 'srcset'], 'object': ['data'], 'embed': ['src'], 'iframe': ['src'], 'a': ['href'] }
        found_urls = set()
        for tag, attrs in resource_map.items():
            for element in soup.find_all(tag):
                for attr in attrs:
                    if not element.has_attr(attr): continue
                    value = element[attr]
                    if not value or value.startswith(('data:', 'javascript:', '#', 'mailto:')): continue
                    urls_to_process = [url.strip().split(' ')[0] for url in value.split(',')] if attr == 'srcset' else [value]
                    for url in urls_to_process:
                        if url: found_urls.add(urljoin(source_url, url))
        for element in soup.find_all(style=True):
            css_urls = re.findall(r'url\((.*?)\)', element['style'])
            for url in css_urls:
                url = url.strip('\'"')
                if url and not url.startswith('data:'): found_urls.add(urljoin(source_url, url))
        for url in found_urls:
            if url not in self.seen_urls:
                self.seen_urls.add(url)
                await self.queue.put(url)

    async def _parse_css(self, css_content: str, source_url: str):
        if self.cancel_event.is_set(): return
        urls = re.findall(r'url\((.*?)\)', css_content)
        for url in urls:
            url = url.strip('\'"')
            if url and not url.startswith('data:'):
                full_url = urljoin(source_url, url)
                if full_url not in self.seen_urls:
                    self.seen_urls.add(full_url)
                    await self.queue.put(full_url)

async def capture_website_full(url: str, output_dir: Path, file_callback=None, proxy=None, session_cookies=None, cancel_event=None):
    """
    Điểm bắt đầu chính, có hỗ trợ hủy bỏ.
    """
    config = {'render_js': True, 'concurrency': 20}
    collector = UltraCollectorV10(url, output_dir, config, file_callback, proxy, cancel_event)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'], proxy={'server': proxy} if proxy else None)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ignore_https_errors=True,
        )
        if session_cookies:
            log_audit(f"Loading {len(session_cookies)} cookies into browser context.")
            await context.add_cookies(session_cookies)
        
        page = await context.new_page()
        try:
            log_audit(f"Navigating to {url}...")
            await page.goto(url, wait_until='networkidle', timeout=60000)
            log_audit("Navigation successful, page is idle.")
        except PlaywrightTimeoutError:
            log_audit("Network idle timeout reached, proceeding with available content.")
        except Exception as e:
            log_audit(f"Page navigation error: {e}")
            await browser.close()
            return {}
        
        if cancel_event and cancel_event.is_set():
            log_audit("Cancellation detected before collection.")
            await browser.close()
            return {}

        resources = await collector.collect_all(page)
        await browser.close()
        return resources

