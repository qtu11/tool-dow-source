# webgrabber/webgrabber/crawler/stealth.py
"""
Stealth Browser Module — Bypass anti-bot detection.

Techniques:
1. WebDriver flag removal
2. Navigator properties override (plugins, languages, platform)
3. Chrome automation flags removal
4. Realistic viewport + screen dimensions
5. Human-like mouse movement + scroll patterns
6. Random delays between actions
7. WebGL/Canvas fingerprint randomization
"""

import random

# ========== Stealth Scripts ==========

STEALTH_SCRIPTS = """
() => {
    // 1. Remove webdriver flag
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    delete navigator.__proto__.webdriver;

    // 2. Override navigator.plugins (empty = bot signal)
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', description: '', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', description: '', filename: 'internal-nacl-plugin' }
            ];
            plugins.length = 3;
            return plugins;
        }
    });

    // 3. Override navigator.languages
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'vi'] });

    // 4. Override navigator.platform
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

    // 5. Chrome runtime mock
    window.chrome = {
        runtime: { id: undefined },
        loadTimes: function () { return {}; },
        csi: function () { return {}; },
        app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } }
    };

    // 6. Permission query override (notifications)
    const originalQuery = window.Notification && Notification.permission;
    if (window.Notification) {
        Notification.requestPermission = () => Promise.resolve('default');
    }

    // 7. Override iframe detection
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get: function () {
            return window;
        }
    });

    // 8. WebGL vendor/renderer
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function (parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.apply(this, arguments);
    };

    // 9. Override connection.rtt to non-zero (headless = 0)
    if (navigator.connection) {
        Object.defineProperty(navigator.connection, 'rtt', { get: () => 50 });
    }

    // 10. Prevent detection via toString()
    const nativeToString = Function.prototype.toString;
    Function.prototype.toString = function () {
        if (this === Function.prototype.toString) return 'function toString() { [native code] }';
        return nativeToString.call(this);
    };
}
"""

# User-Agent pool — realistic Chrome versions
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
]

# Viewport variations
VIEWPORTS = [
    {'width': 1920, 'height': 1080},
    {'width': 1536, 'height': 864},
    {'width': 1440, 'height': 900},
    {'width': 1366, 'height': 768},
    {'width': 2560, 'height': 1440},
]

# Screen variations matching viewports
SCREENS = [
    {'width': 1920, 'height': 1080},
    {'width': 1536, 'height': 864},
    {'width': 1440, 'height': 900},
    {'width': 1366, 'height': 768},
    {'width': 2560, 'height': 1440},
]

# Timezone options
TIMEZONES = [
    'Asia/Ho_Chi_Minh',
    'America/New_York',
    'Europe/London',
    'Asia/Tokyo',
]

# Locale options
LOCALES = ['en-US', 'en-GB', 'vi-VN']


def get_random_profile() -> dict:
    """Generate a random but consistent browser profile."""
    idx = random.randint(0, len(VIEWPORTS) - 1)
    return {
        'user_agent': random.choice(USER_AGENTS),
        'viewport': VIEWPORTS[idx],
        'screen': SCREENS[idx],
        'timezone': random.choice(TIMEZONES),
        'locale': random.choice(LOCALES),
    }


async def apply_stealth(context):
    """Apply stealth scripts to a Playwright browser context."""
    await context.add_init_script(STEALTH_SCRIPTS)


async def create_stealth_context(browser, session_cookies=None, proxy=None):
    """
    Create a Playwright browser context with full stealth mode.

    Returns:
        context: Stealth-enabled browser context
    """
    profile = get_random_profile()

    context_options = {
        'user_agent': profile['user_agent'],
        'viewport': profile['viewport'],
        'screen': profile['screen'],
        'locale': profile['locale'],
        'timezone_id': profile['timezone'],
        'ignore_https_errors': True,
        'java_script_enabled': True,
        'has_touch': False,
        'is_mobile': False,
        'device_scale_factor': random.choice([1, 1.25, 1.5, 2]),
        'color_scheme': 'light',
    }

    if proxy:
        context_options['proxy'] = {'server': proxy}

    context = await browser.new_context(**context_options)

    # Apply stealth scripts
    await apply_stealth(context)

    # Load cookies if provided
    if session_cookies:
        await context.add_cookies(session_cookies)

    return context


async def human_like_scroll(page, total_scroll=None):
    """Simulate human-like scrolling behavior."""
    import asyncio

    if total_scroll is None:
        total_scroll = await page.evaluate('document.body.scrollHeight')

    viewport_height = await page.evaluate('window.innerHeight')
    current = 0

    while current < total_scroll:
        # Random scroll distance (70-130% of viewport)
        scroll_amount = int(viewport_height * (0.7 + random.random() * 0.6))
        current += scroll_amount

        await page.evaluate(f'window.scrollTo({{top: {current}, behavior: "smooth"}})')

        # Random pause (human reading time)
        await asyncio.sleep(0.3 + random.random() * 0.7)

        # Occasionally pause longer (reading content)
        if random.random() < 0.15:
            await asyncio.sleep(1.0 + random.random() * 2.0)

    # Scroll back to top
    await page.evaluate('window.scrollTo({top: 0, behavior: "smooth"})')
    await asyncio.sleep(0.5)
