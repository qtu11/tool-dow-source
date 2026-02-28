# webgrabber/webgrabber/crawler/source_map_bruteforcer.py
"""
Source Map Brute-force Scanner — Aggressive source map discovery & extraction.

Kỹ thuật:
1. Brute-force: Thử {url}.map cho MỌI JS/CSS file
2. HTTP Header scan: X-SourceMap, SourceMap headers
3. Inline source map extraction: data:application/json;base64,...
4. Next.js specific patterns: /_next/static/chunks/*.js.map
5. Common CDN patterns: /sourcemaps/, /maps/
6. Deep extraction: sourcesContent → khôi phục .tsx, .jsx, .vue, .scss
"""

import asyncio
import base64
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable
from urllib.parse import urljoin, urlparse

import aiohttp
import aiofiles

try:
    from ..core.audit_logger import log_audit
except (ImportError, ModuleNotFoundError):
    def log_audit(msg): pass


class SourceMapBruteforcer:
    """
    Aggressively discover and extract source maps to recover original source code.
    Goes far beyond simple sourceMappingURL parsing.
    """

    # Common source map URL patterns to brute-force
    BRUTE_FORCE_SUFFIXES = [
        '.map',           # standard: app.js → app.js.map
        '.js.map',        # alternative
        '.min.map',       # minified variant
        '.bundle.map',    # bundle variant
    ]

    # Common source map directory patterns
    MAP_DIR_PATTERNS = [
        '/sourcemaps/',
        '/maps/',
        '/source-maps/',
        '/.sourcemaps/',
    ]

    # Source map header names
    SOURCEMAP_HEADERS = [
        'sourcemap',
        'x-sourcemap',
    ]

    # Patterns to find sourceMappingURL in JS/CSS
    SOURCEMAP_URL_PATTERNS = [
        re.compile(rb'//[#@]\s*sourceMappingURL=(.+?)[\s\n\r]', re.MULTILINE),
        re.compile(rb'/\*[#@]\s*sourceMappingURL=(.+?)\s*\*/', re.MULTILINE),
    ]

    def __init__(self, output_dir: Path, base_url: str, log_fn: Callable = None):
        self.output_dir = output_dir
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc.lower()
        self.log_fn = log_fn or log_audit
        self.source_dir = output_dir / '_source_maps'
        self.recovered_dir = output_dir / '_recovered_source'

        # Stats
        self.maps_found = 0
        self.maps_extracted = 0
        self.sources_recovered = 0
        self.total_source_files = 0

    def _log(self, msg: str):
        if self.log_fn:
            self.log_fn(msg)

    async def bruteforce_all(self, js_urls: List[str], session: aiohttp.ClientSession) -> Dict[str, Path]:
        """
        Main entry point: aggressively scan ALL JS URLs for source maps.
        Returns dict of recovered source path → local file path.
        """
        self._log("🔍 Phase: Source Map Brute-force Scanner")
        self._log(f"   Scanning {len(js_urls)} JS files for source maps...")

        all_recovered = {}

        # 1. Brute-force .map URLs
        brute_tasks = [self._try_brute_force(url, session) for url in js_urls]
        brute_results = await asyncio.gather(*brute_tasks, return_exceptions=True)

        for result in brute_results:
            if isinstance(result, dict):
                all_recovered.update(result)

        # 2. Check already-downloaded JS files for inline source maps
        inline_results = await self._extract_inline_sourcemaps()
        all_recovered.update(inline_results)

        # 3. Try Next.js specific source map patterns
        nextjs_results = await self._try_nextjs_patterns(session)
        all_recovered.update(nextjs_results)

        # 4. Organize recovered sources into project structure
        if all_recovered:
            self._organize_recovered_sources(all_recovered)

        self._print_stats()
        return all_recovered

    async def _try_brute_force(self, js_url: str, session: aiohttp.ClientSession) -> Dict[str, Path]:
        """Try multiple .map URL patterns for a single JS file."""
        recovered = {}

        for suffix in self.BRUTE_FORCE_SUFFIXES:
            map_url = js_url + suffix if suffix == '.map' else js_url.rsplit('.', 1)[0] + suffix

            try:
                async with session.get(map_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get('content-type', '')
                        data = await resp.read()

                        # Verify it's actually a source map (JSON with "sources" key)
                        if self._is_valid_sourcemap(data):
                            self.maps_found += 1
                            self._log(f"🗺️ Found source map: {map_url}")
                            extracted = await self._extract_sources(data, map_url)
                            recovered.update(extracted)
                            break  # Found valid map, skip other suffixes

                # Also check headers for source map reference
                if not recovered:
                    async with session.head(js_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        for header in self.SOURCEMAP_HEADERS:
                            map_ref = resp.headers.get(header)
                            if map_ref:
                                full_map_url = urljoin(js_url, map_ref)
                                self._log(f"🗺️ Found via header [{header}]: {full_map_url}")
                                async with session.get(full_map_url, timeout=aiohttp.ClientTimeout(total=15)) as map_resp:
                                    if map_resp.status == 200:
                                        data = await map_resp.read()
                                        if self._is_valid_sourcemap(data):
                                            self.maps_found += 1
                                            extracted = await self._extract_sources(data, full_map_url)
                                            recovered.update(extracted)
                                break

            except (aiohttp.ClientError, asyncio.TimeoutError, Exception):
                continue

        return recovered

    async def _extract_inline_sourcemaps(self) -> Dict[str, Path]:
        """Scan downloaded JS/CSS files for inline base64 source maps."""
        recovered = {}
        js_files = list(self.output_dir.rglob('*.js'))
        css_files = list(self.output_dir.rglob('*.css'))

        for file_path in js_files + css_files:
            if '_source_maps' in str(file_path) or '_recovered' in str(file_path):
                continue
            try:
                content = file_path.read_bytes()
                for pattern in self.SOURCEMAP_URL_PATTERNS:
                    match = pattern.search(content)
                    if match:
                        ref = match.group(1).decode('utf-8', errors='ignore').strip()
                        if ref.startswith('data:'):
                            # Inline base64 source map
                            try:
                                b64_part = ref.split(',', 1)[1]
                                map_data = base64.b64decode(b64_part)
                                if self._is_valid_sourcemap(map_data):
                                    self.maps_found += 1
                                    self._log(f"📦 Inline source map in: {file_path.name}")
                                    extracted = await self._extract_sources(map_data, str(file_path))
                                    recovered.update(extracted)
                            except Exception:
                                pass
                        break
            except Exception:
                continue

        return recovered

    async def _try_nextjs_patterns(self, session: aiohttp.ClientSession) -> Dict[str, Path]:
        """Try Next.js-specific source map locations."""
        recovered = {}

        # Find BUILD_ID from downloaded HTML
        build_id = self._detect_nextjs_build_id()
        if not build_id:
            return recovered

        self._log(f"🔍 Next.js BUILD_ID detected: {build_id}")

        # Try common Next.js chunk patterns
        chunk_patterns = [
            f'/_next/static/chunks/main-{{hash}}.js.map',
            f'/_next/static/chunks/webpack-{{hash}}.js.map',
            f'/_next/static/chunks/framework-{{hash}}.js.map',
            f'/_next/static/chunks/pages/_app-{{hash}}.js.map',
            f'/_next/static/chunks/pages/index-{{hash}}.js.map',
            f'/_next/static/{build_id}/_buildManifest.js.map',
            f'/_next/static/{build_id}/_ssgManifest.js.map',
        ]

        # Scan existing downloaded JS files for their .map counterparts
        next_js_files = list(self.output_dir.rglob('_next/**/*.js'))
        for js_file in next_js_files:
            if js_file.suffix == '.map':
                continue
            try:
                rel = js_file.relative_to(self.output_dir)
                map_url = urljoin(self.base_url, '/' + str(rel).replace('\\', '/') + '.map')

                async with session.get(map_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if self._is_valid_sourcemap(data):
                            self.maps_found += 1
                            self._log(f"🗺️ Next.js source map: {rel}.map")
                            extracted = await self._extract_sources(data, map_url)
                            recovered.update(extracted)
            except Exception:
                continue

        return recovered

    def _detect_nextjs_build_id(self) -> Optional[str]:
        """Detect Next.js BUILD_ID from downloaded HTML files."""
        html_files = list(self.output_dir.glob('*.html'))
        for html_file in html_files:
            try:
                content = html_file.read_text(encoding='utf-8', errors='ignore')
                # Pattern: /_next/static/BUILD_ID/
                match = re.search(r'/_next/static/([a-zA-Z0-9_-]{20,})', content)
                if match:
                    return match.group(1)
            except Exception:
                continue
        return None

    def _is_valid_sourcemap(self, data: bytes) -> bool:
        """Verify data is actually a valid source map JSON."""
        try:
            parsed = json.loads(data.decode('utf-8', errors='ignore'))
            return isinstance(parsed, dict) and ('sources' in parsed or 'mappings' in parsed)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

    async def _extract_sources(self, map_data: bytes, source_url: str) -> Dict[str, Path]:
        """Extract original source files from source map data."""
        recovered = {}
        try:
            map_json = json.loads(map_data.decode('utf-8', errors='ignore'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return recovered

        sources = map_json.get('sources', [])
        sources_content = map_json.get('sourcesContent', [])
        source_root = map_json.get('sourceRoot', '')

        if not sources_content:
            return recovered

        self.maps_extracted += 1

        for i, source_path in enumerate(sources):
            if i >= len(sources_content) or sources_content[i] is None:
                continue

            content = sources_content[i]

            # Clean up webpack:// and similar prefixes
            clean_path = source_path
            for prefix in ['webpack://', 'webpack-internal:///', 'turbopack://[project]/',
                           'turbopack://[root]/', 'file://', '///', './', '../',
                           'app-pages-browser/']:
                clean_path = clean_path.replace(prefix, '')

            # Remove query strings and fragments
            clean_path = clean_path.split('?')[0].split('#')[0]

            # Skip node_modules (too large, not user code)
            if 'node_modules' in clean_path:
                continue

            # Skip empty/null/internal paths
            if not clean_path or clean_path.startswith('(') or clean_path.startswith('<'):
                continue

            # Build save path
            clean_path = clean_path.lstrip('/')
            if source_root:
                clean_path = source_root.strip('/') + '/' + clean_path

            save_path = self.source_dir / clean_path

            try:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(save_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
                recovered[clean_path] = save_path
                self.sources_recovered += 1
            except Exception as e:
                pass

        self.total_source_files += len(recovered)
        return recovered

    def _organize_recovered_sources(self, recovered: Dict[str, Path]):
        """Organize recovered sources into a clean project structure."""
        self.recovered_dir.mkdir(parents=True, exist_ok=True)

        for rel_path, source_path in recovered.items():
            if not source_path.exists():
                continue

            # Create clean project structure
            dest = self.recovered_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            try:
                import shutil
                shutil.copy2(source_path, dest)
            except Exception:
                pass

    def _print_stats(self):
        """Print recovery statistics."""
        self._log(f"\n{'='*50}")
        self._log(f"🔬 Source Map Brute-force Results:")
        self._log(f"   🗺️ Source maps found: {self.maps_found}")
        self._log(f"   📦 Source maps extracted: {self.maps_extracted}")
        self._log(f"   📄 Source files recovered: {self.sources_recovered}")

        if self.sources_recovered > 0:
            # Count by extension
            ext_counts = {}
            for f in self.source_dir.rglob('*') if self.source_dir.exists() else []:
                if f.is_file():
                    ext = f.suffix.lower()
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1

            for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
                emoji = {'.tsx': '⚛️', '.jsx': '⚛️', '.ts': '📘', '.js': '📜',
                         '.vue': '💚', '.svelte': '🧡', '.scss': '🎨', '.css': '🎨',
                         '.py': '🐍', '.html': '📄'}.get(ext, '📁')
                self._log(f"   {emoji} {ext}: {count} files")
        else:
            self._log(f"   ⚠️ No source maps found (site may not expose them)")

        self._log(f"{'='*50}\n")

    def get_summary(self) -> str:
        """Get human-readable summary."""
        if self.sources_recovered == 0:
            return "🔍 Source Map Brute-force: No source maps found"
        return (f"🔍 Source Map Brute-force: {self.maps_found} maps → "
                f"{self.sources_recovered} source files recovered")
