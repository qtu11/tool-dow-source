# Vị trí: webgrabber/webgrabber/core/session_manager.py

import asyncio
import browser_cookie3
import tkinter as tk
from playwright.async_api import async_playwright, Browser
from urllib.parse import urlparse
from typing import Callable, Optional, List, Dict, Any
from .audit_logger import log_audit
from .secure_storage import SecureTokenStorage

class SessionManager:
    """Handles user sessions to bypass authentication walls."""

    def __init__(self, url: str, log_callback: Optional[Callable[[str], None]] = None):
        self.url = url
        self.domain = urlparse(url).netloc
        self.log_callback = log_callback or log_audit
        self.storage = SecureTokenStorage(storage_file=f"session_{self.domain}.dat")
        self.browser: Optional[Browser] = None  # To hold the browser instance for proper cleanup

    def _log(self, message: str):
        """Helper to log messages using the provided callback."""
        if self.log_callback:
            self.log_callback(message)
        else:
            log_audit(message)  # Fallback

    def load_cookies_from_browser(self, browser_name: str) -> bool:
        """Imports cookies for the target domain from a specified browser."""
        self._log(f"Attempting to import cookies from '{browser_name}' for domain '{self.domain}'")
        try:
            cookie_loader = getattr(browser_cookie3, browser_name)
            cj = cookie_loader(domain_name=self.domain)
            cookies = [
                {
                    "name": c.name, "value": c.value, "domain": c.domain,
                    "path": c.path, "expires": c.expires,
                    "httpOnly": getattr(c, 'httpOnly', False), "secure": c.secure
                }
                for c in cj
            ]
            if not cookies:
                self._log(f"No cookies found in '{browser_name}' for '{self.domain}'.")
                return False
            self._save_session_data({"cookies": cookies})
            self._log(f"Successfully imported and saved {len(cookies)} cookies.")
            return True
        except Exception as e:
            self._log(f"Failed to import cookies from '{browser_name}': {e}")
            return False

    async def interactive_login(self) -> dict:
        """Opens a browser and a status window for manual login."""
        self._log(f"Starting interactive login for {self.url}")
        status_window = self._create_status_window()
        session_data = {}
        try:
            async with async_playwright() as p:
                self.browser = await p.chromium.launch(headless=False)
                context = await self.browser.new_context()
                page = await context.new_page()
                # FIX: The 'on' event callback for 'close' expects a function that accepts the page object.
                page.on("close", lambda page: status_window.destroy())
                await page.goto(self.url)
                status_window.mainloop()  # This blocks until the small window is closed
                cookies = await context.cookies()
                if cookies:
                    session_data = {"cookies": cookies}
                    self._save_session_data(session_data)
                    self._log(f"Interactive login successful. Captured {len(cookies)} cookies.")
                else:
                    self._log("Interactive login failed or was cancelled; no cookies captured.")
                # The browser is NOT closed here; orchestrator will call close_browser()
        except Exception as e:
            self._log(f"Error during interactive login: {e}")
            if status_window.winfo_exists():
                status_window.destroy()
            await self.close_browser()  # Ensure cleanup on error
        return session_data

    async def close_browser(self):
        """Closes the browser instance if it's open. Called by the orchestrator."""
        if self.browser and self.browser.is_connected():
            self._log("Closing interactive session browser.")
            await self.browser.close()
            self.browser = None

    async def get_cookies(self) -> List[Dict[str, Any]]:
        """Retrieves saved session cookies."""
        session_data = self.get_saved_session()
        return session_data.get("cookies", [])

    def _create_status_window(self):
        """Creates a small Tkinter window to inform the user."""
        if not tk._get_default_root('Error in _create_status_window'):
            root = tk.Tk()
            root.withdraw()

        window = tk.Toplevel()
        window.title("Interactive Login")
        window.geometry("400x150")
        window.attributes("-topmost", True)
        label = tk.Label(
            window,
            text="A browser window has been opened.\n\nPlease log in to the website.\n\n"
                 "After you have successfully logged in,\nCLOSE THIS SMALL WINDOW to continue.",
            padx=10, pady=10
        )
        label.pack(expand=True)
        return window

    def _save_session_data(self, session_data: dict):
        """Saves session data securely."""
        import json
        self.storage.save_token(platform=self.domain, token=json.dumps(session_data))

    def get_saved_session(self) -> dict:
        """Retrieves and parses saved session data."""
        encrypted_session = self.storage.load_token(platform=self.domain)
        if encrypted_session:
            try:
                import json
                return json.loads(encrypted_session)
            except Exception as e:
                self._log(f"Could not parse saved session data: {e}")
        return {}
