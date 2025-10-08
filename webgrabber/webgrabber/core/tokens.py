"""
Enhanced token management with secure storage
This file now serves as a compatibility layer and migration helper
"""

from .secure_storage import SecureTokenStorage
from .audit_logger import log_audit

# Initialize secure storage instance
_secure_storage = SecureTokenStorage()

def save_token(platform: str, token: str, metadata: dict = None) -> bool:
    """Save token securely"""
    return _secure_storage.save_token(platform, token, metadata)

def load_token(platform: str) -> str:
    """Load token securely"""
    return _secure_storage.load_token(platform)

def delete_token(platform: str) -> bool:
    """Delete token for platform"""
    return _secure_storage.delete_token(platform)

def list_platforms() -> list:
    """List all platforms with saved tokens"""
    return _secure_storage.list_platforms()

def migrate_old_tokens() -> bool:
    """Migrate tokens from old plain text format"""
    return _secure_storage.migrate_from_old_format()

def validate_token_format(platform: str, token: str) -> bool:
    """Validate token format"""
    return _secure_storage.validate_token_format(platform, token)

# Backward compatibility - these will be empty as tokens are now encrypted
# Old format tokens will be automatically migrated when accessed
GITHUB_TOKEN = ''
GITLAB_TOKEN = ''
BITBUCKET_TOKEN = ''
GITEA_TOKEN = ''
GOGS_TOKEN = ''
FORGEJO_TOKEN = ''
RHODECODE_TOKEN = ''

# Auto-migration on import
try:
    if migrate_old_tokens():
        log_audit("Successfully migrated tokens from old format to secure storage")
except Exception as e:
    log_audit(f"Token migration failed: {e}")