# webgrabber/webgrabber/cli/validators.py

import click
from urllib.parse import urlparse


def validate_url(url):
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise click.BadArgumentUsage("Invalid URL.")


def validate_out(out):
    if not out:
        raise click.BadArgumentUsage("Output required.")