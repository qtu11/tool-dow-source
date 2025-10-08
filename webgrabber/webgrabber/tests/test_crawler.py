# webgrabber/webgrabber/tests/test_crawler.py

import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch
from webgrabber.crawler.resource_collector import capture_website_full
from webgrabber.core.orchestrator import run_git_clone, detect_platform

class TestCrawler(unittest.TestCase):
    async def async_test_website(self):
        url = "https://example.com"
        output = Path('./test_output')
        resources = await capture_website_full(url, output)
        self.assertGreater(len(resources), 0)

    @patch('subprocess.run')
    async def async_test_git_clone(self, mock_subprocess):
        url = "https://github.com/user/repo.git"
        output = Path('./test_output_clone')
        mock_subprocess.return_value.returncode = 0
        tree = await run_git_clone(url, None, str(output))
        self.assertTrue(len(tree) > 0)
        self.assertEqual(detect_platform(url), 'github')

    def test_crawl(self):
        asyncio.run(self.async_test_website())

    def test_git_clone(self):
        asyncio.run(self.async_test_git_clone())