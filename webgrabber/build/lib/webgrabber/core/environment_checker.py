# webgrabber/core/environment_checker.py
import shutil
from .audit_logger import log_audit

class EnvironmentChecker:
    """Checks for the existence of required external command-line tools."""

    @staticmethod
    def is_tool_installed(name: str) -> bool:
        """
        Checks whether `name` is on PATH and marked as executable.
        Returns:
            bool: True if the tool is found, False otherwise.
        """
        is_installed = shutil.which(name) is not None
        if is_installed:
            log_audit(f"Tool '{name}' is installed.")
        else:
            log_audit(f"Tool '{name}' is NOT installed or not in PATH.")
        return is_installed

    @staticmethod
    def get_missing_tool_message(tool_name: str) -> str:
        """Generates a user-friendly message for a missing tool."""
        messages = {
            "git": "Git is not installed or not in your system's PATH. Please install Git to use this feature.",
            "scp": "SCP (Secure Copy) is not available. It's usually part of an OpenSSH client installation.",
            "heroku": "The Heroku CLI is not installed. Please install it to download from Heroku."
        }
        return messages.get(tool_name, f"Required tool '{tool_name}' is missing.")
