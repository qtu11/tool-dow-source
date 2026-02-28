# webgrabber/webgrabber/core/preview_server.py
"""
Local Preview Server — Serve downloaded website locally.

Features:
- Built-in HTTP server
- Auto-open browser
- MIME type detection
- SPA fallback (serve index.html for unknown routes)
- CORS headers for API proxying
"""

import http.server
import json
import mimetypes
import os
import socket
import threading
import webbrowser
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urlparse, unquote

from .audit_logger import log_audit


class PreviewRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler with SPA support and CORS."""

    def __init__(self, *args, directory=None, spa_mode=True, **kwargs):
        self.spa_mode = spa_mode
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self):
        """Handle GET requests with SPA fallback."""
        # Decode path
        path = unquote(self.path.split('?')[0])
        file_path = Path(self.directory) / path.lstrip('/')

        # If file exists, serve it normally
        if file_path.is_file():
            super().do_GET()
            return

        # If directory has index.html, serve it
        if file_path.is_dir() and (file_path / 'index.html').exists():
            super().do_GET()
            return

        # SPA fallback: serve root index.html for unmatched routes
        if self.spa_mode:
            root_index = Path(self.directory) / 'index.html'
            if root_index.exists():
                self.path = '/index.html'
                super().do_GET()
                return

        # 404
        self.send_error(404, f"File not found: {path}")

    def end_headers(self):
        """Add CORS and cache headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.end_headers()

    def guess_type(self, path):
        """Enhanced MIME type detection."""
        # Add common web types
        extra_types = {
            '.woff2': 'font/woff2',
            '.woff': 'font/woff',
            '.ttf': 'font/ttf',
            '.otf': 'font/otf',
            '.eot': 'application/vnd.ms-fontobject',
            '.webp': 'image/webp',
            '.avif': 'image/avif',
            '.svg': 'image/svg+xml',
            '.json': 'application/json',
            '.mjs': 'application/javascript',
            '.map': 'application/json',
            '.wasm': 'application/wasm',
            '.webmanifest': 'application/manifest+json',
            '.ico': 'image/x-icon',
        }

        ext = Path(path).suffix.lower()
        if ext in extra_types:
            return extra_types[ext]

        return super().guess_type(path)

    def log_message(self, format, *args):
        """Quiet logging — only log errors."""
        if args and isinstance(args[0], str) and args[0].startswith('4'):
            log_audit(f"Preview: {format % args}")


class PreviewServer:
    """
    Local HTTP server to preview downloaded websites.

    Usage:
        server = PreviewServer(directory="/path/to/downloaded/site")
        server.start()      # Start server in background
        server.open_browser()
        server.stop()        # Stop server
    """

    def __init__(self, directory: str | Path, port: int = 0, spa_mode: bool = True,
                 log_callback: Optional[Callable] = None):
        self.directory = str(Path(directory).resolve())
        self.spa_mode = spa_mode
        self.log_callback = log_callback or log_audit
        self._server = None
        self._thread = None

        # Auto-find free port
        if port == 0:
            self.port = self._find_free_port()
        else:
            self.port = port

    def _find_free_port(self) -> int:
        """Find a free port on localhost."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def start(self) -> str:
        """Start the server in a background thread. Returns the URL."""
        handler = lambda *args, **kwargs: PreviewRequestHandler(
            *args, directory=self.directory, spa_mode=self.spa_mode, **kwargs
        )

        self._server = http.server.HTTPServer(('127.0.0.1', self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        url = f"http://127.0.0.1:{self.port}"
        self.log_callback(f"🌐 Preview server started at {url}")
        return url

    def open_browser(self):
        """Open the preview in default browser."""
        url = f"http://127.0.0.1:{self.port}"
        webbrowser.open(url)
        self.log_callback(f"🔗 Opened browser: {url}")

    def stop(self):
        """Stop the server."""
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None
            self.log_callback("⏹️ Preview server stopped.")

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def is_running(self) -> bool:
        return self._server is not None
