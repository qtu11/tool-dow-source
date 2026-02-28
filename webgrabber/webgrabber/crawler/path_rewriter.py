# webgrabber/webgrabber/crawler/path_rewriter.py
"""
Path Rewriter — Chuyển đổi absolute URLs thành relative paths local.

Sau khi download source code, module này rewrite TẤT CẢ URLs trong HTML/CSS/JS
để website có thể mở và chạy offline chỉ bằng cách mở index.html.

Ví dụ:
  <link href="https://example.com/css/style.css"> → <link href="./css/style.css">
  url("https://cdn.example.com/font.woff2") → url("./_external/cdn.example.com/font.woff2")
  <script src="/assets/app.abc123.js"> → <script src="./assets/app.abc123.js">
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Set
from urllib.parse import urlparse, unquote

try:
    from ..core.audit_logger import log_audit
except (ImportError, ModuleNotFoundError):
    def log_audit(msg): pass


class PathRewriter:
    """Rewrite URLs in downloaded files to make them work offline."""

    def __init__(self, output_dir: Path, base_url: str, resources: dict, log_fn=None):
        self.output_dir = output_dir
        self.base_url = base_url.rstrip('/')
        self.base_domain = urlparse(base_url).netloc.lower()
        self.base_scheme = urlparse(base_url).scheme
        self.resources = resources  # URL → Resource mapping
        self.log_fn = log_fn or log_audit
        self.rewrite_count = 0

        # Build URL → local path mapping
        self.url_to_local: Dict[str, str] = {}
        self._build_url_mapping()

    def _build_url_mapping(self):
        """Build mapping from original URLs to local relative paths."""
        for url, resource in self.resources.items():
            if resource.save_path and resource.save_path.exists():
                try:
                    rel_path = resource.save_path.relative_to(self.output_dir)
                    self.url_to_local[url] = str(rel_path).replace('\\', '/')
                except ValueError:
                    pass

    def rewrite_all(self):
        """Rewrite URLs in all HTML, CSS, and JS files."""
        self.log_fn("🔄 Rewriting URLs for offline access...")

        html_files = list(self.output_dir.rglob('*.html'))
        html_files += list(self.output_dir.rglob('*.htm'))
        css_files = list(self.output_dir.rglob('*.css'))
        js_files = list(self.output_dir.rglob('*.js'))

        for f in html_files:
            if '_source_maps' in str(f):
                continue
            self._rewrite_html(f)

        for f in css_files:
            if '_source_maps' in str(f):
                continue
            self._rewrite_css(f)

        for f in js_files:
            if '_source_maps' in str(f):
                continue
            self._rewrite_js(f)

        self.log_fn(f"✅ Rewrote {self.rewrite_count} URLs across {len(html_files)} HTML, "
                    f"{len(css_files)} CSS, {len(js_files)} JS files")

    def _rewrite_html(self, file_path: Path):
        """Rewrite URLs in HTML file."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            original = content
            file_dir = file_path.parent

            # Rewrite src, href, action, poster, data attributes
            attr_pattern = re.compile(
                r'(\s(?:src|href|action|poster|data|content|srcset)=")([^"]*?)(")',
                re.IGNORECASE
            )
            content = attr_pattern.sub(
                lambda m: m.group(1) + self._resolve_url(m.group(2), file_dir) + m.group(3),
                content
            )

            # Also handle single-quoted attributes
            attr_pattern_sq = re.compile(
                r"(\s(?:src|href|action|poster|data|content|srcset)=')([^']*?)(')",
                re.IGNORECASE
            )
            content = attr_pattern_sq.sub(
                lambda m: m.group(1) + self._resolve_url(m.group(2), file_dir) + m.group(3),
                content
            )

            # Rewrite CSS url() in inline styles
            content = re.sub(
                r'(url\(["\']?)((?!data:)[^"\')\s]+)(["\']?\))',
                lambda m: m.group(1) + self._resolve_url(m.group(2), file_dir) + m.group(3),
                content
            )

            # Rewrite <meta http-equiv="refresh" content="0;url=...">
            content = re.sub(
                r'(content="\d+;\s*url=)(https?://[^"]+)(")',
                lambda m: m.group(1) + self._resolve_url(m.group(2), file_dir) + m.group(3),
                content, flags=re.IGNORECASE
            )

            if content != original:
                file_path.write_text(content, encoding='utf-8')

        except Exception as e:
            self.log_fn(f"⚠️ Failed to rewrite HTML {file_path.name}: {e}")

    def _rewrite_css(self, file_path: Path):
        """Rewrite url() references in CSS files."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            original = content
            file_dir = file_path.parent

            # Rewrite url()
            content = re.sub(
                r'(url\(["\']?)((?!data:|#)[^"\')\s]+)(["\']?\))',
                lambda m: m.group(1) + self._resolve_url(m.group(2), file_dir) + m.group(3),
                content
            )

            # Rewrite @import
            content = re.sub(
                r'(@import\s+["\'])((?!data:)[^"\']+)(["\'])',
                lambda m: m.group(1) + self._resolve_url(m.group(2), file_dir) + m.group(3),
                content
            )

            if content != original:
                file_path.write_text(content, encoding='utf-8')

        except Exception as e:
            self.log_fn(f"⚠️ Failed to rewrite CSS {file_path.name}: {e}")

    def _rewrite_js(self, file_path: Path):
        """Rewrite absolute URLs in JS files (limited — only obvious string URLs)."""
        try:
            content = file_path.read_bytes()
            original = content
            file_dir = file_path.parent

            # Only rewrite obvious absolute URL strings pointing to same domain
            # Pattern: "https://example.com/..." or 'https://example.com/...'
            base_escaped = re.escape(f"{self.base_scheme}://{self.base_domain}")

            def replace_js_url(match):
                quote = match.group(1)
                url = match.group(2)
                resolved = self._resolve_url(url, file_dir)
                self.rewrite_count += 1
                return quote.encode() + resolved.encode() + quote.encode()

            pattern = re.compile(
                rb'(["\'])(' + base_escaped.encode() + rb'(?:/[^"\'\\]*?))\1'
            )

            content = pattern.sub(replace_js_url, content)

            if content != original:
                file_path.write_bytes(content)

        except Exception as e:
            self.log_fn(f"⚠️ Failed to rewrite JS {file_path.name}: {e}")

    def _resolve_url(self, url: str, from_dir: Path) -> str:
        """
        Resolve a URL to a relative local path.
        
        Args:
            url: Original URL (absolute or relative)
            from_dir: Directory of the file containing this URL
        
        Returns:
            Relative path from from_dir to the local file
        """
        if not url or url.startswith(('#', 'data:', 'javascript:', 'mailto:', 'tel:', 'blob:')):
            return url

        # Handle srcset (multiple URLs)
        if ',' in url and (' ' in url.split(',')[0]):
            parts = url.split(',')
            rewritten_parts = []
            for part in parts:
                part = part.strip()
                tokens = part.split()
                if tokens:
                    tokens[0] = self._resolve_single_url(tokens[0], from_dir)
                rewritten_parts.append(' '.join(tokens))
            return ', '.join(rewritten_parts)

        return self._resolve_single_url(url, from_dir)

    def _resolve_single_url(self, url: str, from_dir: Path) -> str:
        """Resolve a single URL to relative path."""
        original_url = url

        # Skip already-relative paths that look local
        if url.startswith('./') or url.startswith('../'):
            return url

        # Handle protocol-relative URLs (//cdn.example.com/...)
        if url.startswith('//'):
            url = self.base_scheme + ':' + url

        # Handle absolute URLs (https://...)
        if url.startswith(('http://', 'https://')):
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check if we have this file downloaded
            if url in self.url_to_local:
                target_path = self.output_dir / self.url_to_local[url]
                return self._make_relative(from_dir, target_path)

            # Same domain — convert to path-based lookup
            if domain == self.base_domain:
                path = unquote(parsed.path).lstrip('/')
                if not path or path.endswith('/'):
                    path = path.rstrip('/') + '/index.html' if path else 'index.html'
                target_path = self.output_dir / path
                if target_path.exists():
                    return self._make_relative(from_dir, target_path)
                # Try to find by searching
                found = self._find_local_file(path)
                if found:
                    return self._make_relative(from_dir, found)

            # External domain — check _external directory
            if domain != self.base_domain:
                ext_path = unquote(parsed.path).lstrip('/')
                target_path = self.output_dir / '_external' / domain.replace(':', '_') / ext_path
                if target_path.exists():
                    return self._make_relative(from_dir, target_path)

            # URL not found locally — keep original
            return original_url

        # Handle root-relative URLs (/assets/...)
        if url.startswith('/'):
            path = unquote(url).lstrip('/')
            target_path = self.output_dir / path
            if target_path.exists():
                return self._make_relative(from_dir, target_path)
            found = self._find_local_file(path)
            if found:
                return self._make_relative(from_dir, found)

            # Try without query/fragment
            clean_path = path.split('?')[0].split('#')[0]
            target_path = self.output_dir / clean_path
            if target_path.exists():
                return self._make_relative(from_dir, target_path)

        return original_url

    def _make_relative(self, from_dir: Path, target: Path) -> str:
        """Calculate relative path from from_dir to target file."""
        try:
            rel = os.path.relpath(target, from_dir).replace('\\', '/')
            if not rel.startswith('.'):
                rel = './' + rel
            self.rewrite_count += 1
            return rel
        except ValueError:
            return str(target).replace('\\', '/')

    def _find_local_file(self, path: str) -> Path | None:
        """Try to find a local file matching the path (handles hashed filenames)."""
        # Direct match
        target = self.output_dir / path
        if target.exists():
            return target

        # Try parent dir with glob for hashed files
        parent = (self.output_dir / path).parent
        if parent.exists():
            name = Path(path).name
            stem = Path(name).stem
            suffix = Path(name).suffix
            # Try exact match first
            for f in parent.iterdir():
                if f.name == name:
                    return f
            # Try matching by suffix
            if suffix:
                for f in parent.glob(f'*{suffix}'):
                    return f

        return None
