"""
Secure token storage module with encryption support
"""
import os
import json
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .audit_logger import log_audit

class SecureTokenStorage:
    def __init__(self, storage_file="secure_tokens.dat"):
        self.storage_file = Path(storage_file)
        self.key_file = Path(".token_key")
        self._ensure_key_exists()
    
    def _ensure_key_exists(self):
        """Generate or load encryption key"""
        if not self.key_file.exists():
            # Generate a new key
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(self.key_file, 0o600)
            log_audit("Generated new encryption key for token storage")
        
    def _get_cipher(self):
        """Get Fernet cipher instance"""
        with open(self.key_file, 'rb') as f:
            key = f.read()
        return Fernet(key)
    
    def save_token(self, platform: str, token: str, metadata: dict = None):
        """Save encrypted token for platform"""
        try:
            # Load existing tokens
            tokens = self._load_tokens()
            
            # Add/update token
            tokens[platform] = {
                'token': token,
                'metadata': metadata or {},
                'created_at': str(Path().stat().st_mtime if Path().exists() else 0)
            }
            
            # Encrypt and save
            cipher = self._get_cipher()
            encrypted_data = cipher.encrypt(json.dumps(tokens).encode())
            
            with open(self.storage_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Set restrictive permissions
            os.chmod(self.storage_file, 0o600)
            log_audit(f"Securely saved token for platform: {platform}")
            return True
            
        except Exception as e:
            log_audit(f"Error saving token for {platform}: {e}")
            return False
    
    def load_token(self, platform: str):
        """Load decrypted token for platform"""
        try:
            tokens = self._load_tokens()
            token_data = tokens.get(platform)
            if token_data:
                return token_data.get('token')
            return None
            
        except Exception as e:
            log_audit(f"Error loading token for {platform}: {e}")
            return None
    
    def _load_tokens(self):
        """Load and decrypt all tokens"""
        if not self.storage_file.exists():
            return {}
        
        try:
            cipher = self._get_cipher()
            with open(self.storage_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
            
        except Exception as e:
            log_audit(f"Error loading tokens: {e}")
            return {}
    
    def list_platforms(self):
        """List all platforms with saved tokens"""
        tokens = self._load_tokens()
        return list(tokens.keys())
    
    def delete_token(self, platform: str):
        """Delete token for platform"""
        try:
            tokens = self._load_tokens()
            if platform in tokens:
                del tokens[platform]
                
                # Re-encrypt and save
                cipher = self._get_cipher()
                encrypted_data = cipher.encrypt(json.dumps(tokens).encode())
                
                with open(self.storage_file, 'wb') as f:
                    f.write(encrypted_data)
                
                log_audit(f"Deleted token for platform: {platform}")
                return True
            return False
            
        except Exception as e:
            log_audit(f"Error deleting token for {platform}: {e}")
            return False
    
    def validate_token_format(self, platform: str, token: str):
        """Validate token format for specific platform"""
        validation_rules = {
            'github': lambda t: t.startswith(('ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_')) and len(t) >= 40,
            'gitlab': lambda t: len(t) >= 20 and t.replace('-', '').replace('_', '').isalnum(),
            'bitbucket': lambda t: len(t) >= 20,
            'gitea': lambda t: len(t) >= 20,
            'gogs': lambda t: len(t) >= 20,
            'forgejo': lambda t: len(t) >= 20,
            'rhodecode': lambda t: len(t) >= 20,
        }
        
        validator = validation_rules.get(platform)
        if validator:
            return validator(token)
        
        # Default validation - at least 10 characters
        return len(token) >= 10
    
    def migrate_from_old_format(self, old_tokens_file="tokens.py"):
        """Migrate tokens from old plain text format"""
        if not Path(old_tokens_file).exists():
            return False
        
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("old_tokens", old_tokens_file)
            old_tokens = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(old_tokens)
            
            migrated_count = 0
            for attr_name in dir(old_tokens):
                if attr_name.endswith('_TOKEN') and not attr_name.startswith('_'):
                    platform = attr_name.replace('_TOKEN', '').lower()
                    token = getattr(old_tokens, attr_name)
                    if token and isinstance(token, str):
                        self.save_token(platform, token, {'migrated': True})
                        migrated_count += 1
            
            if migrated_count > 0:
                log_audit(f"Migrated {migrated_count} tokens from old format")
                # Backup old file
                os.rename(old_tokens_file, f"{old_tokens_file}.backup")
            
            return migrated_count > 0
            
        except Exception as e:
            log_audit(f"Error migrating tokens: {e}")
            return False