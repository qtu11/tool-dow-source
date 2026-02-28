# webgrabber/webgrabber/crawler/api_interceptor.py
"""
API Interceptor — Bắt và lưu tất cả XHR/Fetch API calls.

Khi crawl website, module này tự động:
1. Bắt tất cả XHR/fetch requests (API calls)
2. Lưu request + response data
3. Phân loại: REST API, GraphQL, WebSocket
4. Generate API documentation (endpoints, methods, params)
5. Save response data dưới dạng JSON
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, urlencode, parse_qs


@dataclass
class APICall:
    url: str
    method: str
    status: int
    request_headers: Dict[str, str] = field(default_factory=dict)
    response_headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[str] = None
    response_body: Optional[bytes] = None
    content_type: str = ''
    is_graphql: bool = False
    is_api: bool = False
    category: str = 'unknown'  # rest, graphql, websocket, ssr_data


class APIInterceptor:
    """
    Intercept and catalog API calls during browser crawling.
    Integrates with Playwright's request/response events.
    """

    # Patterns that indicate API endpoints
    API_PATTERNS = [
        r'/api/',
        r'/v\d+/',
        r'/graphql',
        r'/rest/',
        r'/_next/data/',
        r'/__api/',
        r'/wp-json/',
        r'\.json$',
        r'/query',
    ]

    # Content types that indicate API responses
    API_CONTENT_TYPES = {
        'application/json',
        'application/graphql+json',
        'application/ld+json',
        'application/vnd.api+json',
        'text/json',
    }

    # Skip patterns (not API calls)
    SKIP_PATTERNS = [
        r'\.js$', r'\.css$', r'\.png$', r'\.jpg$', r'\.gif$', r'\.svg$',
        r'\.woff', r'\.ttf$', r'\.ico$', r'\.webp$', r'\.avif$',
        r'analytics', r'tracking', r'telemetry', r'gtag', r'facebook\.com',
        r'google-analytics', r'googletagmanager', r'hotjar', r'sentry',
    ]

    def __init__(self, base_url: str, output_dir: Path, log_fn=None):
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc.lower()
        self.output_dir = output_dir
        self.log_fn = log_fn
        self.api_calls: List[APICall] = []
        self.endpoints: Set[str] = set()
        self._seen_urls: Set[str] = set()

    def _log(self, msg: str):
        if self.log_fn:
            self.log_fn(msg)

    def _is_api_url(self, url: str, content_type: str = '') -> bool:
        """Check if URL looks like an API endpoint."""
        # Check content type
        ct = content_type.lower().split(';')[0].strip()
        if ct in self.API_CONTENT_TYPES:
            return True

        # Check URL patterns
        path = urlparse(url).path.lower()
        for pattern in self.API_PATTERNS:
            if re.search(pattern, path):
                return True

        return False

    def _should_skip(self, url: str) -> bool:
        """Check if URL should be skipped (static assets, trackers)."""
        for pattern in self.SKIP_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _categorize(self, url: str, method: str, request_body: str = None) -> str:
        """Categorize the API call."""
        path = urlparse(url).path.lower()

        if '/graphql' in path or (request_body and '"query"' in str(request_body)):
            return 'graphql'
        if '/_next/data/' in path:
            return 'ssr_data'
        if '/wp-json/' in path:
            return 'wordpress_api'
        if re.search(r'/api/|/v\d+/', path):
            return 'rest'
        return 'other'

    async def on_response(self, response):
        """
        Playwright response event handler.
        Attach to page: page.on('response', interceptor.on_response)
        """
        url = response.url
        status = response.status

        # Skip non-interesting requests
        if status < 200 or status >= 400:
            return
        if self._should_skip(url):
            return
        if url in self._seen_urls:
            return

        content_type = response.headers.get('content-type', '')

        if not self._is_api_url(url, content_type):
            return

        self._seen_urls.add(url)

        try:
            body = await response.body()
        except Exception:
            body = None

        request = response.request
        method = request.method

        call = APICall(
            url=url,
            method=method,
            status=status,
            response_headers=dict(response.headers),
            request_headers=dict(request.headers) if request.headers else {},
            request_body=request.post_data if hasattr(request, 'post_data') else None,
            response_body=body,
            content_type=content_type,
            is_graphql=('/graphql' in url.lower()),
            is_api=True,
            category=self._categorize(url, method, request.post_data if hasattr(request, 'post_data') else None),
        )

        self.api_calls.append(call)

        # Track unique endpoints (strip query params)
        parsed = urlparse(url)
        endpoint = f"{method} {parsed.path}"
        self.endpoints.add(endpoint)

        self._log(f"🔌 API: {method} {parsed.path} → {status}")

    def save_results(self) -> Path:
        """Save intercepted API data to output directory."""
        if not self.api_calls:
            return None

        api_dir = self.output_dir / '_api_data'
        api_dir.mkdir(parents=True, exist_ok=True)

        # 1. Save API catalog
        catalog = {
            'total_calls': len(self.api_calls),
            'unique_endpoints': len(self.endpoints),
            'endpoints': sorted(self.endpoints),
            'by_category': {},
            'calls': [],
        }

        for call in self.api_calls:
            call_info = {
                'url': call.url,
                'method': call.method,
                'status': call.status,
                'category': call.category,
                'content_type': call.content_type,
                'response_size': len(call.response_body) if call.response_body else 0,
            }
            catalog['calls'].append(call_info)

            if call.category not in catalog['by_category']:
                catalog['by_category'][call.category] = 0
            catalog['by_category'][call.category] += 1

        catalog_path = api_dir / 'api_catalog.json'
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

        # 2. Save individual API responses
        for i, call in enumerate(self.api_calls):
            if not call.response_body:
                continue

            parsed = urlparse(call.url)
            safe_name = re.sub(r'[<>:"|?*\\/ ]', '_', parsed.path.strip('/'))[:80]
            filename = f"{i:03d}_{call.method}_{safe_name}"

            # Try to parse as JSON
            try:
                data = json.loads(call.response_body)
                resp_path = api_dir / f"{filename}.json"
                with open(resp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, UnicodeDecodeError):
                resp_path = api_dir / f"{filename}.bin"
                with open(resp_path, 'wb') as f:
                    f.write(call.response_body)

        self._log(f"📋 Saved {len(self.api_calls)} API calls → {api_dir}")
        return api_dir

    def get_summary(self) -> str:
        """Generate human-readable summary."""
        if not self.api_calls:
            return "No API calls detected."

        lines = [
            f"🔌 {len(self.api_calls)} API calls intercepted",
            f"   📍 {len(self.endpoints)} unique endpoints",
        ]

        categories = {}
        for call in self.api_calls:
            categories[call.category] = categories.get(call.category, 0) + 1

        for cat, count in sorted(categories.items()):
            emoji = {'rest': '🔗', 'graphql': '💎', 'ssr_data': '📦',
                     'wordpress_api': '📝'}.get(cat, '📡')
            lines.append(f"   {emoji} {cat}: {count}")

        return '\n'.join(lines)
