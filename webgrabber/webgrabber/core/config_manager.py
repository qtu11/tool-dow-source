# Vị trí lưu: webgrabber/core/config_manager.py
import json
from pathlib import Path
from .audit_logger import log_audit

class ConfigManager:
    """Manages reading and writing the user's config.json file."""

    def __init__(self, config_path="config.json"):
        """Initializes the ConfigManager, loading or creating the config file."""
        self.config_path = Path(config_path)
        self.config = self._load_or_create_config()

    def _get_default_config(self):
        """Returns the default configuration structure."""
        return {
            "git_strategy": {
                "branch": "main"
            },
            "ssh_strategy": {
                "user": "root",
                "host": "example.com",
                "port": 22,
                "remote_path": "/var/www/html",
                "private_key_path": "",
                "exclude": [
                    "node_modules/",
                    ".git/",
                    "*.log",
                    "cache/"
                ]
            },
            "paas_strategy": {
                "heroku": {
                    "app_name": ""
                }
            },
            "general": {
                "proxy": ""
            }
        }

    def _load_or_create_config(self):
        """Loads the config file if it exists, otherwise creates it."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                log_audit(f"Error loading config.json: {e}. Reverting to default.")
                return self._get_default_config()
        else:
            log_audit("config.json not found, creating a default one.")
            default_config = self._get_default_config()
            self.save_config(default_config)
            return default_config

    def get_config(self):
        """Returns the current in-memory configuration."""
        return self.config

    def save_config(self, new_config: dict):
        """Saves the provided configuration to the config.json file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4)
            self.config = new_config # Also update the in-memory config
            log_audit("Configuration saved successfully.")
        except IOError as e:
            log_audit(f"Error saving config.json: {e}")

