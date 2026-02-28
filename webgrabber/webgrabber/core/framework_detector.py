# webgrabber/webgrabber/core/framework_detector.py
"""
Framework Detector — Nhận diện framework từ HTML/JS content.

Detect: React, Vue, Angular, Next.js, Nuxt, Svelte, SolidJS,
        Astro, Remix, Gatsby, WordPress, Laravel, Django, Rails.
"""

import re
from typing import Dict, List, Optional


class FrameworkDetector:
    """Analyze HTML and JS to detect web frameworks."""

    # Detection patterns: (pattern, framework_id, confidence)
    HTML_PATTERNS = [
        # React/Next.js
        (r'<div\s+id="__next"', 'nextjs', 95),
        (r'_next/static', 'nextjs', 90),
        (r'__NEXT_DATA__', 'nextjs', 95),
        (r'<div\s+id="root"', 'react', 60),
        (r'<div\s+id="app"', 'vue_or_react', 40),
        (r'react\.production\.min\.js', 'react', 85),
        (r'react-dom', 'react', 80),

        # Vue/Nuxt
        (r'<div\s+id="__nuxt"', 'nuxt', 95),
        (r'_nuxt/', 'nuxt', 90),
        (r'__NUXT__', 'nuxt', 95),
        (r'vue\.runtime', 'vue', 85),
        (r'vue\.min\.js', 'vue', 85),
        (r'data-v-[a-f0-9]+', 'vue', 80),
        (r'data-server-rendered', 'nuxt', 70),

        # Angular
        (r'<app-root', 'angular', 90),
        (r'ng-version', 'angular', 95),
        (r'angular\.min\.js', 'angular', 85),
        (r'ng-app', 'angularjs', 85),

        # Svelte/SvelteKit
        (r'__sveltekit', 'sveltekit', 95),
        (r'svelte-[a-z0-9]+', 'svelte', 75),

        # Astro
        (r'astro-island', 'astro', 95),
        (r'astro\.js', 'astro', 80),

        # Remix
        (r'__remixContext', 'remix', 95),
        (r'remix\.run', 'remix', 80),

        # Gatsby
        (r'___gatsby', 'gatsby', 95),
        (r'gatsby-', 'gatsby', 70),

        # CMS
        (r'wp-content/', 'wordpress', 90),
        (r'wp-includes/', 'wordpress', 90),
        (r'wp-json', 'wordpress', 85),

        # Others
        (r'data-turbolinks', 'rails', 70),
        (r'csrf-token.*content="', 'rails_or_laravel', 50),
        (r'laravel_session', 'laravel', 85),
        (r'DJANGO', 'django', 60),

        # Build tools
        (r'vite', 'vite', 60),
        (r'webpack', 'webpack', 60),
        (r'parcel', 'parcel', 60),
    ]

    # JS content patterns
    JS_PATTERNS = [
        (rb'React\.createElement', 'react', 90),
        (rb'ReactDOM\.', 'react', 90),
        (rb'__webpack_modules__', 'webpack', 85),
        (rb'__vite_ssr_import__', 'vite', 85),
        (rb'Vue\.component', 'vue', 85),
        (rb'createApp\(', 'vue', 50),
        (rb'@angular/core', 'angular', 90),
        (rb'svelte/internal', 'svelte', 90),
    ]

    # Framework metadata
    FRAMEWORK_INFO = {
        'nextjs': {'name': 'Next.js', 'category': 'fullstack', 'base': 'react', 'icon': '▲'},
        'react': {'name': 'React', 'category': 'frontend', 'base': 'react', 'icon': '⚛️'},
        'nuxt': {'name': 'Nuxt', 'category': 'fullstack', 'base': 'vue', 'icon': '💚'},
        'vue': {'name': 'Vue.js', 'category': 'frontend', 'base': 'vue', 'icon': '💚'},
        'angular': {'name': 'Angular', 'category': 'frontend', 'base': 'angular', 'icon': '🅰️'},
        'angularjs': {'name': 'AngularJS', 'category': 'frontend', 'base': 'angular', 'icon': '🅰️'},
        'svelte': {'name': 'Svelte', 'category': 'frontend', 'base': 'svelte', 'icon': '🔥'},
        'sveltekit': {'name': 'SvelteKit', 'category': 'fullstack', 'base': 'svelte', 'icon': '🔥'},
        'astro': {'name': 'Astro', 'category': 'fullstack', 'base': 'astro', 'icon': '🚀'},
        'remix': {'name': 'Remix', 'category': 'fullstack', 'base': 'react', 'icon': '💿'},
        'gatsby': {'name': 'Gatsby', 'category': 'fullstack', 'base': 'react', 'icon': '🟣'},
        'wordpress': {'name': 'WordPress', 'category': 'cms', 'base': 'php', 'icon': '📝'},
        'rails': {'name': 'Ruby on Rails', 'category': 'backend', 'base': 'ruby', 'icon': '💎'},
        'laravel': {'name': 'Laravel', 'category': 'backend', 'base': 'php', 'icon': '🔴'},
        'django': {'name': 'Django', 'category': 'backend', 'base': 'python', 'icon': '🐍'},
        'vite': {'name': 'Vite', 'category': 'build_tool', 'base': None, 'icon': '⚡'},
        'webpack': {'name': 'Webpack', 'category': 'build_tool', 'base': None, 'icon': '📦'},
    }

    @staticmethod
    def detect_from_html(html_content: str) -> Dict:
        """
        Detect frameworks from HTML content.

        Returns:
            {
                'primary': {'id': 'nextjs', 'name': 'Next.js', ...},
                'detected': [{'id': 'react', 'confidence': 85}, ...],
                'build_tool': 'webpack',
            }
        """
        scores = {}

        for pattern, framework_id, confidence in FrameworkDetector.HTML_PATTERNS:
            if re.search(pattern, html_content, re.IGNORECASE):
                if framework_id not in scores or confidence > scores[framework_id]:
                    scores[framework_id] = confidence

        if not scores:
            return {'primary': None, 'detected': [], 'build_tool': None}

        # Sort by confidence
        detected = sorted(
            [{'id': fid, 'confidence': conf, **FrameworkDetector.FRAMEWORK_INFO.get(fid, {})}
             for fid, conf in scores.items()],
            key=lambda x: x['confidence'],
            reverse=True
        )

        # Find primary framework (highest confidence, not a build tool)
        primary = None
        build_tool = None
        for d in detected:
            info = FrameworkDetector.FRAMEWORK_INFO.get(d['id'], {})
            if info.get('category') == 'build_tool':
                build_tool = d['id']
            elif primary is None and d['confidence'] >= 60:
                primary = d

        return {
            'primary': primary,
            'detected': detected,
            'build_tool': build_tool,
        }

    @staticmethod
    def detect_from_js(js_content: bytes) -> List[Dict]:
        """Detect frameworks from JS bundle content."""
        results = []
        for pattern, framework_id, confidence in FrameworkDetector.JS_PATTERNS:
            if re.search(pattern, js_content):
                info = FrameworkDetector.FRAMEWORK_INFO.get(framework_id, {})
                results.append({'id': framework_id, 'confidence': confidence, **info})
        return results

    @staticmethod
    def get_summary(detection_result: Dict) -> str:
        """Generate human-readable summary."""
        primary = detection_result.get('primary')
        if not primary:
            return "❓ Unknown framework"

        info = FrameworkDetector.FRAMEWORK_INFO.get(primary['id'], {})
        icon = info.get('icon', '🔧')
        name = info.get('name', primary['id'])
        confidence = primary.get('confidence', 0)
        build_tool = detection_result.get('build_tool')

        summary = f"{icon} {name} (confidence: {confidence}%)"
        if build_tool:
            bt_info = FrameworkDetector.FRAMEWORK_INFO.get(build_tool, {})
            summary += f" + {bt_info.get('icon', '')} {bt_info.get('name', build_tool)}"

        return summary
