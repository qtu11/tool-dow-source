# webgrabber/webgrabber/cli/validators.py

import click
from urllib.parse import urlparse


def validate_url(ctx, param, value):
    """Validate URL format for Click callback."""
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise click.BadArgumentUsage("Invalid URL. Must include scheme (http/https) and domain.")
    return value


def validate_out(ctx, param, value):
    """Validate output directory for Click callback."""
    if not value:
        raise click.BadArgumentUsage("Output directory is required.")
    return value