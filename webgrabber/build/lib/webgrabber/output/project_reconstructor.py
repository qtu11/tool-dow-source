# webgrabber/webgrabber/output/project_reconstructor.py
"""
Project Reconstructor — Tạo project structure từ downloaded source.

Dựa vào framework_detector kết quả, module này:
1. Generate package.json với đúng dependencies
2. Tạo serve config (next.config.js, vite.config.js, etc.)
3. Tạo README.md hướng dẫn chạy
4. Tạo Dockerfile nếu cần
"""

import json
from pathlib import Path
from typing import Dict, Optional


class ProjectReconstructor:
    """Generate runnable project config from detected framework."""

    # Framework → typical dependencies
    FRAMEWORK_DEPS = {
        'react': {
            'dependencies': {
                'react': '^18.2.0',
                'react-dom': '^18.2.0',
            },
            'devDependencies': {
                'vite': '^5.0.0',
                '@vitejs/plugin-react': '^4.0.0',
            },
            'scripts': {
                'dev': 'vite',
                'build': 'vite build',
                'preview': 'vite preview',
            },
        },
        'nextjs': {
            'dependencies': {
                'react': '^18.2.0',
                'react-dom': '^18.2.0',
                'next': '^14.0.0',
            },
            'scripts': {
                'dev': 'next dev',
                'build': 'next build',
                'start': 'next start',
            },
        },
        'vue': {
            'dependencies': {
                'vue': '^3.4.0',
            },
            'devDependencies': {
                'vite': '^5.0.0',
                '@vitejs/plugin-vue': '^5.0.0',
            },
            'scripts': {
                'dev': 'vite',
                'build': 'vite build',
                'preview': 'vite preview',
            },
        },
        'nuxt': {
            'dependencies': {
                'nuxt': '^3.9.0',
                'vue': '^3.4.0',
            },
            'scripts': {
                'dev': 'nuxt dev',
                'build': 'nuxt build',
                'preview': 'nuxt preview',
            },
        },
        'angular': {
            'dependencies': {
                '@angular/core': '^17.0.0',
                '@angular/common': '^17.0.0',
                '@angular/platform-browser': '^17.0.0',
                'rxjs': '^7.8.0',
                'zone.js': '^0.14.0',
            },
            'devDependencies': {
                '@angular/cli': '^17.0.0',
                'typescript': '^5.2.0',
            },
            'scripts': {
                'start': 'ng serve',
                'build': 'ng build',
            },
        },
        'svelte': {
            'dependencies': {
                'svelte': '^4.2.0',
            },
            'devDependencies': {
                'vite': '^5.0.0',
                '@sveltejs/vite-plugin-svelte': '^3.0.0',
            },
            'scripts': {
                'dev': 'vite',
                'build': 'vite build',
            },
        },
        'sveltekit': {
            'dependencies': {
                'svelte': '^4.2.0',
                '@sveltejs/kit': '^2.0.0',
            },
            'devDependencies': {
                'vite': '^5.0.0',
                '@sveltejs/vite-plugin-svelte': '^3.0.0',
            },
            'scripts': {
                'dev': 'vite dev',
                'build': 'vite build',
                'preview': 'vite preview',
            },
        },
        'astro': {
            'dependencies': {
                'astro': '^4.0.0',
            },
            'scripts': {
                'dev': 'astro dev',
                'build': 'astro build',
                'preview': 'astro preview',
            },
        },
    }

    # Static site → simple serve
    STATIC_SERVE = {
        'scripts': {
            'serve': 'npx serve .',
            'dev': 'npx serve . -l 3000',
        },
    }

    def __init__(self, output_dir: Path, framework_info: Dict = None, log_fn=None):
        self.output_dir = output_dir
        self.framework_info = framework_info or {}
        self.log_fn = log_fn or (lambda x: None)
        self.primary = framework_info.get('primary') if framework_info else None

    def reconstruct(self):
        """Generate all project config files."""
        self._generate_package_json()
        self._generate_readme()
        self._generate_serve_config()
        self.log_fn("📦 Project reconstruction complete!")

    def _generate_package_json(self):
        """Generate package.json based on detected framework."""
        pkg_path = self.output_dir / 'package.json'

        # Don't overwrite if already exists (downloaded from source)
        if pkg_path.exists():
            self.log_fn("📦 package.json already exists, skipping.")
            return

        framework_id = self.primary
        if framework_id and framework_id in self.FRAMEWORK_DEPS:
            template = self.FRAMEWORK_DEPS[framework_id]
        else:
            template = self.STATIC_SERVE

        pkg = {
            'name': 'webgrabber-downloaded-project',
            'version': '1.0.0',
            'private': True,
            'description': f'Downloaded from {self.framework_info.get("source_url", "unknown")}',
            **template,
        }

        with open(pkg_path, 'w', encoding='utf-8') as f:
            json.dump(pkg, f, indent=2)
        self.log_fn(f"📦 Generated package.json ({framework_id or 'static'})")

    def _generate_readme(self):
        """Generate README.md with setup instructions."""
        readme_path = self.output_dir / 'README.md'
        if readme_path.exists():
            return

        framework_name = 'Unknown'
        if self.framework_info:
            framework_name = self.framework_info.get('primary_name', 'Static Site')

        source_url = self.framework_info.get('source_url', 'N/A')

        content = f"""# Downloaded Website Source Code

> Downloaded by **WebGrabber v1.0** from: {source_url}

## Detected Framework
**{framework_name}**

## Quick Start

### Option 1: Static Preview (recommended)
```bash
npx serve .
```
Then open http://localhost:3000

### Option 2: Framework Dev Server
```bash
npm install
npm run dev
```

## Project Structure
- `index.html` — Main entry point
- `_source_maps/` — Reconstructed original source code
- `_api_data/` — Captured API responses
- `_external/` — Cross-domain assets
- `framework_info.json` — Framework detection results
- `download_summary.json` — Download statistics

## Notes
- Source code was extracted from source maps where available
- API calls were intercepted and saved
- All URLs have been rewritten for offline access
"""
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        self.log_fn("📝 Generated README.md")

    def _generate_serve_config(self):
        """Generate a simple serve config for static preview."""
        serve_path = self.output_dir / 'serve.json'
        if serve_path.exists():
            return

        config = {
            'headers': [
                {
                    'source': '**/*',
                    'headers': [
                        {'key': 'Access-Control-Allow-Origin', 'value': '*'},
                        {'key': 'Cache-Control', 'value': 'no-cache'},
                    ]
                }
            ],
            'rewrites': [
                {'source': '**', 'destination': '/index.html'}
            ],
            'cleanUrls': True,
        }

        with open(serve_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        self.log_fn("⚙️ Generated serve.json (SPA routing)")
