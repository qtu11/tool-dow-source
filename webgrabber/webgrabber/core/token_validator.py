"""
Token validation module for different platforms
"""
import re
import requests
from .audit_logger import log_audit
from .platform_detector import PlatformDetector

class TokenValidator:
    # API endpoints for token validation
    VALIDATION_ENDPOINTS = {
        'github': 'https://api.github.com/user',
        'gitlab': 'https://gitlab.com/api/v4/user',
        'bitbucket': 'https://api.bitbucket.org/2.0/user',
        'gitea': '/api/v1/user',  # Relative path for self-hosted
        'gogs': '/api/v1/user',
        'forgejo': '/api/v1/user',
    }
    
    @classmethod
    def validate_token_format(cls, platform: str, token: str) -> tuple[bool, str]:
        """Validate token format for specific platform"""
        if not token or not isinstance(token, str):
            return False, "Token cannot be empty"
        
        # Remove whitespace
        token = token.strip()
        
        # Platform-specific format validation
        validators = {
            'github': cls._validate_github_token,
            'gitlab': cls._validate_gitlab_token,
            'bitbucket': cls._validate_bitbucket_token,
            'gitea': cls._validate_gitea_token,
            'gogs': cls._validate_gogs_token,
            'forgejo': cls._validate_forgejo_token,
            'rhodecode': cls._validate_rhodecode_token,
        }
        
        validator = validators.get(platform, cls._validate_generic_token)
        return validator(token)
    
    @classmethod
    def _validate_github_token(cls, token: str) -> tuple[bool, str]:
        """Validate GitHub token format"""
        # GitHub token prefixes
        valid_prefixes = ['ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_']
        
        if not any(token.startswith(prefix) for prefix in valid_prefixes):
            return False, "GitHub tokens should start with ghp_, gho_, ghu_, ghs_, or ghr_"
        
        if len(token) < 40:
            return False, "GitHub tokens should be at least 40 characters long"
        
        # Check for valid characters (alphanumeric + underscore)
        if not re.match(r'^[a-zA-Z0-9_]+$', token):
            return False, "GitHub tokens should only contain alphanumeric characters and underscores"
        
        return True, "Valid GitHub token format"
    
    @classmethod
    def _validate_gitlab_token(cls, token: str) -> tuple[bool, str]:
        """Validate GitLab token format"""
        if len(token) < 20:
            return False, "GitLab tokens should be at least 20 characters long"
        
        # GitLab tokens are typically alphanumeric with hyphens and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', token):
            return False, "GitLab tokens should only contain alphanumeric characters, hyphens, and underscores"
        
        return True, "Valid GitLab token format"
    
    @classmethod
    def _validate_bitbucket_token(cls, token: str) -> tuple[bool, str]:
        """Validate Bitbucket app password format"""
        if len(token) < 20:
            return False, "Bitbucket app passwords should be at least 20 characters long"
        
        # Bitbucket app passwords are alphanumeric
        if not re.match(r'^[a-zA-Z0-9]+$', token):
            return False, "Bitbucket app passwords should only contain alphanumeric characters"
        
        return True, "Valid Bitbucket app password format"
    
    @classmethod
    def _validate_gitea_token(cls, token: str) -> tuple[bool, str]:
        """Validate Gitea token format"""
        if len(token) < 20:
            return False, "Gitea tokens should be at least 20 characters long"
        
        # Gitea tokens are typically alphanumeric with underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', token):
            return False, "Gitea tokens should only contain alphanumeric characters and underscores"
        
        return True, "Valid Gitea token format"
    
    @classmethod
    def _validate_gogs_token(cls, token: str) -> tuple[bool, str]:
        """Validate Gogs token format"""
        if len(token) < 20:
            return False, "Gogs tokens should be at least 20 characters long"
        
        # Gogs tokens are typically alphanumeric
        if not re.match(r'^[a-zA-Z0-9]+$', token):
            return False, "Gogs tokens should only contain alphanumeric characters"
        
        return True, "Valid Gogs token format"
    
    @classmethod
    def _validate_forgejo_token(cls, token: str) -> tuple[bool, str]:
        """Validate Forgejo token format"""
        if len(token) < 20:
            return False, "Forgejo tokens should be at least 20 characters long"
        
        # Forgejo tokens are similar to Gitea
        if not re.match(r'^[a-zA-Z0-9_]+$', token):
            return False, "Forgejo tokens should only contain alphanumeric characters and underscores"
        
        return True, "Valid Forgejo token format"
    
    @classmethod
    def _validate_rhodecode_token(cls, token: str) -> tuple[bool, str]:
        """Validate RhodeCode token format"""
        if len(token) < 20:
            return False, "RhodeCode tokens should be at least 20 characters long"
        
        # RhodeCode tokens are typically alphanumeric with hyphens
        if not re.match(r'^[a-zA-Z0-9_-]+$', token):
            return False, "RhodeCode tokens should only contain alphanumeric characters, hyphens, and underscores"
        
        return True, "Valid RhodeCode token format"
    
    @classmethod
    def _validate_generic_token(cls, token: str) -> tuple[bool, str]:
        """Generic token validation"""
        if len(token) < 10:
            return False, "Token should be at least 10 characters long"
        
        # Allow most common token characters
        if not re.match(r'^[a-zA-Z0-9_.-]+$', token):
            return False, "Token contains invalid characters"
        
        return True, "Valid token format"
    
    @classmethod
    async def test_token_access(cls, platform: str, token: str, base_url: str = None) -> tuple[bool, str]:
        """Test if token has valid access to the platform"""
        try:
            endpoint = cls.VALIDATION_ENDPOINTS.get(platform)
            if not endpoint:
                return True, "Token validation not supported for this platform"
            
            # Handle self-hosted instances
            if endpoint.startswith('/') and base_url:
                endpoint = base_url.rstrip('/') + endpoint
            elif endpoint.startswith('/'):
                return True, "Cannot validate self-hosted token without base URL"
            
            # Prepare headers based on platform
            headers = cls._get_auth_headers(platform, token)
            
            # Make API request
            response = requests.get(endpoint, headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_info = response.json()
                username = cls._extract_username(platform, user_info)
                return True, f"Token valid for user: {username}"
            elif response.status_code == 401:
                return False, "Token is invalid or expired"
            elif response.status_code == 403:
                return False, "Token has insufficient permissions"
            else:
                return False, f"API returned status {response.status_code}"
                
        except requests.RequestException as e:
            log_audit(f"Token validation error for {platform}: {e}")
            return False, f"Network error: {str(e)}"
        except Exception as e:
            log_audit(f"Unexpected error validating token for {platform}: {e}")
            return False, f"Validation error: {str(e)}"
    
    @classmethod
    def _get_auth_headers(cls, platform: str, token: str) -> dict:
        """Get authentication headers for platform"""
        if platform == 'github':
            return {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            }
        elif platform == 'gitlab':
            return {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        elif platform == 'bitbucket':
            return {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
        elif platform in ['gitea', 'gogs', 'forgejo']:
            return {
                'Authorization': f'token {token}',
                'Content-Type': 'application/json'
            }
        else:
            return {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
    
    @classmethod
    def _extract_username(cls, platform: str, user_info: dict) -> str:
        """Extract username from API response"""
        username_fields = ['login', 'username', 'name', 'display_name']
        
        for field in username_fields:
            if field in user_info and user_info[field]:
                return user_info[field]
        
        return "Unknown"
    
    @classmethod
    def get_token_instructions(cls, platform: str) -> str:
        """Get instructions for creating tokens for specific platform"""
        instructions = {
            'github': """
GitHub Personal Access Token:
1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Click 'Generate new token (classic)'
3. Select scopes: 'repo' for private repos, 'public_repo' for public repos
4. Copy the generated token (starts with ghp_)
            """,
            'gitlab': """
GitLab Personal Access Token:
1. Go to GitLab User Settings > Access Tokens
2. Enter token name and expiration date
3. Select scopes: 'read_repository' or 'write_repository'
4. Click 'Create personal access token'
5. Copy the generated token
            """,
            'bitbucket': """
Bitbucket App Password:
1. Go to Bitbucket Settings > App passwords
2. Click 'Create app password'
3. Select permissions: 'Repositories: Read' or 'Write'
4. Copy the generated password
            """,
            'gitea': """
Gitea Access Token:
1. Go to User Settings > Applications > Access Tokens
2. Enter token name
3. Select scopes as needed
4. Click 'Generate Token'
5. Copy the generated token
            """,
            'gogs': """
Gogs Access Token:
1. Go to User Settings > Applications > Access Tokens
2. Enter token name
3. Click 'Generate New Token'
4. Copy the generated token
            """,
            'forgejo': """
Forgejo Access Token:
1. Go to User Settings > Applications > Access Tokens
2. Enter token name and select scopes
3. Click 'Generate Token'
4. Copy the generated token
            """,
            'rhodecode': """
RhodeCode API Token:
1. Go to User Settings > API Keys
2. Enter description and expiration
3. Select permissions as needed
4. Click 'Add'
5. Copy the generated API key
            """
        }
        
        return instructions.get(platform, f"Please refer to {platform} documentation for token creation instructions.")