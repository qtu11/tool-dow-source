# webgrabber/webgrabber/output/tree_builder.py

import os
import re
from pathlib import Path
from urllib.parse import urlparse, unquote


def build_tree(resources, base_url):
    """
    Build file tree from Resource objects or cloned dir
    """
    tree = {}

    # Handle both list and dict
    if isinstance(resources, dict):
        resources = list(resources.values())

    for resource in resources:
        try:
            # Extract data from Resource object
            url = resource.url
            data = resource.data if resource.data else b''
        except AttributeError:
            # Skip invalid resources
            continue

        # Convert URL to path
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path.lstrip('/'))
        except:
            path = f"resource_{hash(url)}.bin"

        if not path or path == '/':
            path = 'index.html'

        # Sanitize path
        path = re.sub(r'[<>:"|?*]', '_', path)

        # Add domain prefix for cross-domain
        if parsed.netloc and parsed.netloc != urlparse(base_url).netloc:
            path = f"{parsed.netloc}/{path}"

        tree[path] = data

    return tree


def build_tree_from_dir(dir_path):
    """Build tree from cloned directory (for git_clone mode)"""
    tree = {}
    dir_path = Path(dir_path)
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            rel_path = Path(root) / file
            rel_path_str = rel_path.relative_to(dir_path)
            tree[str(rel_path_str)] = f"Cloned: {str(rel_path_str)}"
    return tree