# webgrabber/webgrabber/crawler/playwright_driver.py

from playwright.async_api import async_playwright


class PlaywrightDriver:
    def __init__(self, url, render_js, session, proxy=None):
        self.url = url
        self.render_js = render_js
        self.session = session  # For headers/cookies
        self.page = None
        self.proxy = proxy

    async def init_browser(self):
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-infobars',
            '--window-position=0,0',
            '--ignore-certificate-errors'
        ]
        if self.proxy:
            args.append(f'--proxy-server={self.proxy}')
        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch(
            headless=True,
            args=args
        )
        self.context = await self.browser.new_context(
            extra_http_headers=self.session.headers,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        await self.context.add_cookies([{'name': k, 'value': v} for k, v in self.session.cookies.items()])
        self.page = await self.context.new_page()
        await self.page.goto(self.url)
        if self.render_js:
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(5000)
            # No F12 or Ctrl+Shift+I simulation - rely on stealth script
        return self.page

    async def get_content(self):
        return await self.page.content()

    def export_har(self, path):
        # Use playwright context tracing for HAR-like
        pass