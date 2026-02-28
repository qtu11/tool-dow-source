# webgrabber/webgrabber/crawler/js_debundler.py
"""
JavaScript Bundle Debundler — Extract modules from Webpack/Vite bundles.

Kỹ thuật:
1. Parse Webpack runtime → tìm __webpack_modules__
2. Extract individual modules → file riêng
3. Detect module paths từ webpack comments
4. JS Beautification → format code readable
5. Reconstruct project structure từ module IDs/paths
6. Next.js _buildManifest.js parsing → extract ALL routes
7. Git repo discovery → check /.git/HEAD, package.json
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Callable
from urllib.parse import urljoin, urlparse

import aiohttp

try:
    from ..core.audit_logger import log_audit
except (ImportError, ModuleNotFoundError):
    def log_audit(msg): pass


def _beautify_js(code: str) -> str:
    """Beautify minified JS code to improve readability."""
    try:
        import jsbeautifier
        opts = jsbeautifier.default_options()
        opts.indent_size = 2
        opts.indent_char = ' '
        opts.max_preserve_newlines = 2
        opts.preserve_newlines = True
        opts.keep_array_indentation = False
        opts.break_chained_methods = True
        opts.space_before_conditional = True
        opts.unescape_strings = True
        opts.wrap_line_length = 120
        opts.end_with_newline = True
        return jsbeautifier.beautify(code, opts)
    except ImportError:
        # Fallback: basic formatting if jsbeautifier not installed
        return _basic_beautify(code)


def _basic_beautify(code: str) -> str:
    """Basic JS formatter when jsbeautifier is not available."""
    # Add newlines after semicolons and braces
    code = re.sub(r';(?!\s*\n)', ';\n', code)
    code = re.sub(r'\{(?!\s*\n)', '{\n', code)
    code = re.sub(r'\}(?![\s,;\)])', '}\n', code)

    # Basic indentation
    lines = code.split('\n')
    result = []
    indent = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('}') or stripped.startswith(']'):
            indent = max(0, indent - 1)
        result.append('  ' * indent + stripped)
        if stripped.endswith('{') or stripped.endswith('['):
            indent += 1
    return '\n'.join(result)


class WebpackDebundler:
    """
    Extract individual modules from Webpack/Vite bundles.
    Reconstructs project structure even without source maps.
    """

    # Patterns to identify webpack module definitions
    WEBPACK_PATTERNS = [
        # Webpack 5: {"./src/App.tsx": function(module, exports, require) {...}}
        re.compile(
            r'["\'](\./[^"\']+\.(?:tsx?|jsx?|vue|svelte|css|scss))["\']'
            r'\s*:\s*(?:function|\()',
            re.MULTILINE
        ),
        # Webpack module.id comment
        re.compile(r'/\*!\s*module\.id\s*=\s*["\']([^"\']+)["\']\s*\*/', re.MULTILINE),
        # Webpack named modules
        re.compile(r'__webpack_modules__\[["\'](\.\/[^"\']+)["\']\]', re.MULTILINE),
    ]

    # Patterns to extract individual module code blocks
    MODULE_CODE_PATTERN = re.compile(
        r'["\'](\./[^"\']+)["\']'
        r'\s*:\s*(?:\(\s*(?:function\s*)?\([^)]*\)\s*\{|function\s*\([^)]*\)\s*\{)'
        r'([\s\S]*?)(?=\n["\']\.\/|\Z)',
        re.MULTILINE
    )

    # React component patterns
    REACT_COMPONENT_PATTERNS = [
        re.compile(r'(?:var|let|const)\s+(\w+)\s*=\s*(?:React\.)?(?:createClass|createElement|forwardRef|memo)\s*\('),
        re.compile(r'function\s+(\w+)\s*\([^)]*\)\s*\{[^}]*return\s+(?:React\.)?createElement'),
        re.compile(r'(?:var|let|const)\s+(\w+)\s*=\s*\(\s*\)\s*=>\s*\{[^}]*(?:jsx|createElement)'),
    ]

    def __init__(self, output_dir: Path, base_url: str, log_fn: Callable = None):
        self.output_dir = output_dir
        self.base_url = base_url
        self.log_fn = log_fn or log_audit
        self.debundled_dir = output_dir / '_debundled'
        self.modules_found = 0
        self.components_detected = 0

    def _log(self, msg: str):
        if self.log_fn:
            self.log_fn(msg)

    async def debundle_all(self) -> Dict[str, Path]:
        """
        Scan all downloaded JS files and extract webpack modules.
        Returns dict of module_path → local file path.
        """
        self._log("🔧 Phase: Webpack Bundle Debundler")

        js_files = list(self.output_dir.rglob('*.js'))
        js_files = [f for f in js_files
                     if '_source_maps' not in str(f)
                     and '_debundled' not in str(f)
                     and '_recovered' not in str(f)]

        self._log(f"   Scanning {len(js_files)} JS bundle files...")

        all_modules = {}

        for js_file in js_files:
            try:
                content = js_file.read_text(encoding='utf-8', errors='ignore')

                # Extract webpack modules
                modules = self._extract_webpack_modules(content, js_file.name)
                all_modules.update(modules)

                # Detect React components
                components = self._detect_react_components(content, js_file.name)
                self.components_detected += len(components)

            except Exception as e:
                continue

        # Save extracted modules
        saved = {}
        if all_modules:
            saved = self._save_modules(all_modules)

        # Beautify main bundles if no modules found
        if not all_modules:
            saved = self._beautify_bundles(js_files)

        self._print_stats()
        return saved

    def _extract_webpack_modules(self, content: str, filename: str) -> Dict[str, str]:
        """Extract individual modules from a webpack bundle."""
        modules = {}

        # Try each pattern to find module definitions
        for pattern in self.WEBPACK_PATTERNS:
            for match in pattern.finditer(content):
                module_path = match.group(1)
                self.modules_found += 1

                # Try to extract the module's code
                module_code = self._extract_module_code(content, module_path)
                if module_code:
                    modules[module_path] = module_code

        # Also try to parse webpack IIFE format: (self["webpackChunk"]= ...)
        chunk_modules = self._parse_webpack_chunk(content)
        modules.update(chunk_modules)

        if modules:
            self._log(f"   📦 {filename}: {len(modules)} modules found")

        return modules

    def _extract_module_code(self, content: str, module_path: str) -> Optional[str]:
        """Extract the code block for a specific module."""
        escaped_path = re.escape(module_path)

        # Pattern: "module_path": function(module, exports, require) { ... }
        pattern = re.compile(
            rf'["\'](?:{escaped_path})["\']'
            rf'\s*:\s*(?:\(\s*)?(?:function\s*)?\([^)]*\)\s*\{{',
            re.MULTILINE
        )

        match = pattern.search(content)
        if not match:
            return None

        # Find matching closing brace
        start = match.end() - 1  # Include the opening brace
        code = self._extract_balanced_braces(content, start)
        if code:
            return _beautify_js(code)
        return None

    def _extract_balanced_braces(self, content: str, start: int) -> Optional[str]:
        """Extract code between balanced braces starting from position."""
        if start >= len(content) or content[start] != '{':
            return None

        depth = 0
        i = start
        in_string = False
        string_char = None

        while i < len(content):
            char = content[i]

            if in_string:
                if char == '\\':
                    i += 2
                    continue
                if char == string_char:
                    in_string = False
            else:
                if char in '"\'`':
                    in_string = True
                    string_char = char
                elif char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return content[start:i + 1]

            i += 1

        # Limit extraction to prevent huge outputs
        max_len = min(len(content), start + 50000)
        return content[start:max_len] if start < max_len else None

    def _parse_webpack_chunk(self, content: str) -> Dict[str, str]:
        """Parse webpack chunk format: (self["webpackChunk"] = ...).push(...)"""
        modules = {}

        # Find webpackChunk push patterns
        chunk_pattern = re.compile(
            r'(?:self|window|globalThis)\[[\"\']webpackChunk[^\"\']*[\"\']\]',
            re.MULTILINE
        )

        if not chunk_pattern.search(content):
            return modules

        # Find module ID → path mappings
        id_path_pattern = re.compile(
            r'(\d+)\s*:\s*\(\s*(?:function\s*)?\([^)]*\)\s*\{',
            re.MULTILINE
        )

        for match in id_path_pattern.finditer(content):
            module_id = match.group(1)
            code = self._extract_balanced_braces(content, match.end() - 1)
            if code and len(code) > 50:  # Skip trivial modules
                # Try to detect module purpose from content
                module_name = self._guess_module_name(code, module_id)
                modules[module_name] = _beautify_js(code)

        return modules

    def _guess_module_name(self, code: str, module_id: str) -> str:
        """Guess a meaningful name for a module based on its content."""
        # Check for React component
        for pattern in self.REACT_COMPONENT_PATTERNS:
            match = pattern.search(code)
            if match:
                return f"components/{match.group(1)}.jsx"

        # Check for CSS/style content
        if 'style' in code.lower() and ('className' in code or 'styled' in code):
            return f"styles/module_{module_id}.css.js"

        # Check for API/fetch calls
        if 'fetch(' in code or 'axios' in code or '/api/' in code:
            return f"api/module_{module_id}.js"

        # Check for utility functions
        if code.count('function') > 3 or code.count('=>') > 5:
            return f"utils/module_{module_id}.js"

        return f"modules/chunk_{module_id}.js"

    def _detect_react_components(self, content: str, filename: str) -> List[str]:
        """Detect React components in JS bundles."""
        components = []
        for pattern in self.REACT_COMPONENT_PATTERNS:
            for match in pattern.finditer(content):
                components.append(match.group(1))
        return components

    def _save_modules(self, modules: Dict[str, str]) -> Dict[str, Path]:
        """Save extracted modules to disk."""
        saved = {}
        self.debundled_dir.mkdir(parents=True, exist_ok=True)

        for module_path, code in modules.items():
            clean_path = module_path.lstrip('./')
            save_path = self.debundled_dir / clean_path

            try:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_text(code, encoding='utf-8')
                saved[clean_path] = save_path
            except Exception:
                continue

        self._log(f"   💾 Saved {len(saved)} debundled modules → _debundled/")
        return saved

    def _beautify_bundles(self, js_files: List[Path]) -> Dict[str, Path]:
        """When no modules found, beautify main bundle files for readability."""
        saved = {}
        beautified_dir = self.debundled_dir / 'beautified'
        beautified_dir.mkdir(parents=True, exist_ok=True)

        # Only beautify significant JS files (> 1KB, < 5MB)
        significant_files = [f for f in js_files
                              if 1024 < f.stat().st_size < 5 * 1024 * 1024]

        if not significant_files:
            return saved

        self._log(f"   🎨 Beautifying {len(significant_files)} JS bundles...")

        for js_file in significant_files[:20]:  # Limit to top 20
            try:
                content = js_file.read_text(encoding='utf-8', errors='ignore')
                beautified = _beautify_js(content)

                save_path = beautified_dir / js_file.name
                save_path.write_text(beautified, encoding='utf-8')
                saved[str(js_file.name)] = save_path
            except Exception:
                continue

        return saved

    def _print_stats(self):
        """Print debundling statistics."""
        self._log(f"\n{'='*50}")
        self._log(f"🔧 Webpack Debundler Results:")
        self._log(f"   📦 Webpack modules extracted: {self.modules_found}")
        self._log(f"   ⚛️ React components detected: {self.components_detected}")
        if self.debundled_dir.exists():
            total = sum(1 for _ in self.debundled_dir.rglob('*') if _.is_file())
            self._log(f"   💾 Files saved: {total}")
        self._log(f"{'='*50}\n")


class NextJsRecon:
    """
    Next.js-specific reconnaissance — extract app structure from build artifacts.
    """

    def __init__(self, output_dir: Path, base_url: str, log_fn: Callable = None):
        self.output_dir = output_dir
        self.base_url = base_url.rstrip('/')
        self.log_fn = log_fn or log_audit
        self.recon_dir = output_dir / '_nextjs_recon'
        self.routes = []
        self.build_id = None

    def _log(self, msg: str):
        if self.log_fn:
            self.log_fn(msg)

    async def reconn(self, session: aiohttp.ClientSession) -> Dict:
        """Run full Next.js reconnaissance."""
        self._log("🔍 Phase: Next.js Deep Reconnaissance")

        # 1. Detect Build ID
        self.build_id = self._detect_build_id()
        if not self.build_id:
            self._log("   ℹ️ Not a Next.js site (no BUILD_ID found)")
            return {}

        self._log(f"   🔑 Build ID: {self.build_id}")
        self.recon_dir.mkdir(parents=True, exist_ok=True)

        results = {
            'build_id': self.build_id,
            'framework': 'Next.js',
            'routes': [],
            'pages': [],
            'chunks': [],
        }

        # 2. Fetch and parse _buildManifest.js
        manifest_data = await self._fetch_build_manifest(session)
        if manifest_data:
            results['routes'] = list(manifest_data.keys())
            results['pages'] = manifest_data
            self.routes = results['routes']
            self._log(f"   🗺️ Routes found: {len(results['routes'])}")
            for route in sorted(results['routes'])[:15]:
                self._log(f"      → {route}")
            if len(results['routes']) > 15:
                self._log(f"      ... and {len(results['routes']) - 15} more")

        # 3. Fetch SSR data for each route
        ssr_data = await self._fetch_ssr_data(session)
        if ssr_data:
            results['ssr_data'] = ssr_data

        # 4. Save results
        results_path = self.recon_dir / 'nextjs_structure.json'
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        self._log(f"   📋 Saved Next.js structure → _nextjs_recon/nextjs_structure.json")
        return results

    def _detect_build_id(self) -> Optional[str]:
        """Detect BUILD_ID from HTML or JS files."""
        # Check HTML files
        for html_file in self.output_dir.glob('*.html'):
            try:
                content = html_file.read_text(encoding='utf-8', errors='ignore')
                match = re.search(r'/_next/static/([a-zA-Z0-9_-]{8,})', content)
                if match:
                    return match.group(1)
            except Exception:
                continue

        # Check _next directory structure
        next_static = self.output_dir / '_next' / 'static'
        if next_static.exists():
            for d in next_static.iterdir():
                if d.is_dir() and d.name != 'chunks' and d.name != 'css' and d.name != 'media':
                    return d.name

        return None

    async def _fetch_build_manifest(self, session: aiohttp.ClientSession) -> Optional[Dict]:
        """Fetch and parse _buildManifest.js."""
        manifest_url = f"{self.base_url}/_next/static/{self.build_id}/_buildManifest.js"

        try:
            async with session.get(manifest_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    content = await resp.text()

                    # Save raw manifest
                    raw_path = self.recon_dir / '_buildManifest.js'
                    raw_path.write_text(content, encoding='utf-8')

                    # Parse: self.__BUILD_MANIFEST = {"/": [...], "/about": [...], ...}
                    match = re.search(r'self\.__BUILD_MANIFEST\s*=\s*(\{[\s\S]*?\})\s*;', content)
                    if match:
                        try:
                            # Handle JS object → JSON conversion
                            js_obj = match.group(1)
                            # Simple conversion: wrap keys
                            js_obj = re.sub(r'(?<=[{,])\s*(/[^:]*?):', r'"\1":', js_obj)
                            manifest = json.loads(js_obj)
                            return manifest
                        except json.JSONDecodeError:
                            pass

                    # Fallback: extract route patterns directly
                    routes = re.findall(r'["\'](/[^"\']*)["\']', content)
                    if routes:
                        return {r: [] for r in set(routes) if not r.endswith('.js')}

        except Exception:
            pass

        # Try from already-downloaded files
        for f in self.output_dir.rglob('_buildManifest.js'):
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                routes = re.findall(r'["\'](/[^"\']*)["\']', content)
                if routes:
                    return {r: [] for r in set(routes) if not r.endswith('.js')}
            except Exception:
                continue

        return None

    async def _fetch_ssr_data(self, session: aiohttp.ClientSession) -> Dict:
        """Fetch _next/data/{BUILD_ID}/*.json for SSR pages."""
        ssr_data = {}

        for route in self.routes[:20]:  # Limit to 20 routes
            # Convert route to data URL: /about → /_next/data/BUILD_ID/about.json
            data_path = route.rstrip('/')
            if not data_path or data_path == '/':
                data_path = '/index'

            data_url = f"{self.base_url}/_next/data/{self.build_id}{data_path}.json"

            try:
                async with session.get(data_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        ssr_data[route] = data

                        # Save SSR data
                        save_name = data_path.strip('/').replace('/', '_') or 'index'
                        save_path = self.recon_dir / 'ssr_data' / f'{save_name}.json'
                        save_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(save_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)

                        self._log(f"   📊 SSR data: {route}")
            except Exception:
                continue

        return ssr_data


class GitRepoDiscovery:
    """
    Discover public Git repositories associated with a website.
    """

    def __init__(self, output_dir: Path, base_url: str, log_fn: Callable = None):
        self.output_dir = output_dir
        self.base_url = base_url.rstrip('/')
        self.log_fn = log_fn or log_audit
        self.repo_url = None

    def _log(self, msg: str):
        if self.log_fn:
            self.log_fn(msg)

    async def discover(self, session: aiohttp.ClientSession) -> Optional[str]:
        """
        Try to discover public Git repository for this website.
        Returns repository URL if found, None otherwise.
        """
        self._log("🔍 Phase: Git Repository Discovery")

        # 1. Check for exposed .git directory
        repo_url = await self._check_exposed_git(session)
        if repo_url:
            return repo_url

        # 2. Check package.json for repository field
        repo_url = self._check_package_json()
        if repo_url:
            return repo_url

        # 3. Check HTML meta tags and comments for GitHub links
        repo_url = self._check_html_for_repo()
        if repo_url:
            return repo_url

        self._log("   ℹ️ No public Git repository found")
        return None

    async def _check_exposed_git(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Check if .git directory is exposed."""
        git_urls = [
            f'{self.base_url}/.git/HEAD',
            f'{self.base_url}/.git/config',
        ]

        for url in git_urls:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        if url.endswith('HEAD') and 'ref:' in content:
                            self._log(f"   ⚠️ EXPOSED .git directory at: {url}")
                            # Try to get remote URL from config
                            config_url = f'{self.base_url}/.git/config'
                            async with session.get(config_url) as cfg_resp:
                                if cfg_resp.status == 200:
                                    config = await cfg_resp.text()
                                    match = re.search(r'url\s*=\s*(.+)', config)
                                    if match:
                                        repo = match.group(1).strip()
                                        self._log(f"   🎯 Found repository: {repo}")
                                        return repo
                        elif 'url =' in content:
                            match = re.search(r'url\s*=\s*(.+)', content)
                            if match:
                                repo = match.group(1).strip()
                                self._log(f"   🎯 Found repository: {repo}")
                                return repo
            except Exception:
                continue

        return None

    def _check_package_json(self) -> Optional[str]:
        """Check downloaded package.json for repository field."""
        pkg_files = list(self.output_dir.rglob('package.json'))
        for pkg_file in pkg_files:
            try:
                with open(pkg_file, 'r', encoding='utf-8') as f:
                    pkg = json.load(f)
                repo = pkg.get('repository')
                if isinstance(repo, str):
                    self._log(f"   🎯 Found repo in package.json: {repo}")
                    return repo
                elif isinstance(repo, dict):
                    url = repo.get('url', '')
                    if url:
                        # Clean up git+https:// prefix
                        url = url.replace('git+', '').replace('git://', 'https://')
                        self._log(f"   🎯 Found repo in package.json: {url}")
                        return url
            except Exception:
                continue

        return None

    def _check_html_for_repo(self) -> Optional[str]:
        """Check HTML files for GitHub/GitLab links."""
        github_pattern = re.compile(
            r'https?://(?:www\.)?github\.com/[\w-]+/[\w.-]+',
            re.IGNORECASE
        )

        for html_file in self.output_dir.glob('*.html'):
            try:
                content = html_file.read_text(encoding='utf-8', errors='ignore')
                matches = github_pattern.findall(content)
                if matches:
                    # Return the most likely repo URL (not a file/blob link)
                    for match in matches:
                        parts = urlparse(match).path.strip('/').split('/')
                        if len(parts) == 2:  # owner/repo format
                            self._log(f"   🎯 Found GitHub link in HTML: {match}")
                            return match
            except Exception:
                continue

        return None
