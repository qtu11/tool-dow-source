# webgrabber/webgrabber/core/audit_logger.py

import logging
import os
from pathlib import Path

# Determine log file location relative to the project root
_log_dir = Path(__file__).resolve().parent.parent.parent
_log_file = _log_dir / 'audit.log'

logging.basicConfig(
    filename=str(_log_file),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8',
)

_logger = logging.getLogger('webgrabber')


def log_audit(message: str):
    """Log an audit message to the audit.log file."""
    _logger.info(message)