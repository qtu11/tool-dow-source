# webgrabber/webgrabber/tools/retry_failed_enhanced.py

import asyncio
import aiofiles
import aiohttp
import hashlib
import json
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import List
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import urlparse, unquote
from webgrabber.core.orchestrator import detect_platform, load_token

def load_manifest(output_dir: Path) -> List[str]:
    manifest_path = output_dir / 'manifest.json'
    if not manifest_path.exists():
        print("No manifest.json found!")
        return []
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    failed_urls = manifest.get('failed_urls', [])
    print(f"Found {len(failed_urls)} failed URLs in manifest.")
    return failed_urls

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def download_with_requests(url: str, output_dir: Path, method: str = 'get') -> bool:
    headers_base = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': urlparse(url).scheme + '://' + urlparse(url).netloc or ''
    }
    platform = detect_platform(url)
    token = load_token(platform)
    if token:
        headers_base['Authorization'] = f"Bearer {token}" if platform == 'github' else f"token {token}"
    
    try:
        if method == 'head_get':
            head_resp = requests.head(url, headers=headers_base, timeout=30)
            if head_resp.status_code != 200:
                raise Exception(f"HEAD failed: {head_resp.status_code}")
            resp = requests.get(url, headers=headers_base, stream=True, timeout=60)
        elif method == 'no_headers':
            resp = requests.get(url, headers={}, stream=True, timeout=60)
        else:
            resp = requests.get(url, headers=headers_base, stream=True, timeout=60)
        if resp.status_code == 200:
            filepath = _url_to_path(url, output_dir)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"✓ Downloaded with requests ({method}): {url} -> {filepath}")
            return True
        else:
            print(f"✗ Failed requests ({method}): {url} (status {resp.status_code})")
            raise Exception(f"Status {resp.status_code}")
    except Exception as e:
        print(f"✗ Error requests ({method}): {e}")
        raise

async def download_with_aiohttp_retry(url: str, output_dir: Path, attempt: int = 1) -> bool:
    try:
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
        timeout = aiohttp.ClientTimeout(total=60 + (attempt * 10))
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0)',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        platform = detect_platform(url)
        token = load_token(platform)
        if token:
            headers['Authorization'] = f"Bearer {token}" if platform == 'github' else f"token {token}"
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    filepath = _url_to_path(url, output_dir)
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(data)
                    print(f"✓ Downloaded with aiohttp (attempt {attempt}): {url} -> {filepath}")
                    return True
                else:
                    print(f"✗ Failed aiohttp (attempt {attempt}): {url} (status {resp.status})")
                    if attempt < 5:
                        await asyncio.sleep(2 ** attempt)
                        return await download_with_aiohttp_retry(url, output_dir, attempt + 1)
                    return False
    except Exception as e:
        print(f"✗ Error aiohttp (attempt {attempt}): {e}")
        if attempt < 5:
            await asyncio.sleep(2 ** attempt)
            return await download_with_aiohttp_retry(url, output_dir, attempt + 1)
        return False

def download_with_curl(url: str, output_dir: Path) -> bool:
    try:
        filepath = _url_to_path(url, output_dir)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            'curl', '-s', '-L', '-o', str(filepath),
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '--max-time', '60',
            url
        ]
        platform = detect_platform(url)
        token = load_token(platform)
        if token:
            cmd.insert(1, f"--header=Authorization: Bearer {token}" if platform == 'github' else f"--header=Authorization: token {token}")
        
        result = subprocess.run(cmd, capture_output=True, timeout=70)
        if result.returncode == 0 and filepath.exists() and filepath.stat().st_size > 0:
            print(f"✓ Downloaded with curl: {url} -> {filepath}")
            return True
        else:
            print(f"✗ Failed curl: {url} (code {result.returncode})")
            return False
    except Exception as e:
        print(f"✗ Error curl: {e}")
        try:
            cmd_wget = [
                'wget', '-q', '-O', str(filepath),
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '--timeout=60',
                url
            ]
            if token:
                cmd_wget.insert(1, f"--header=Authorization: Bearer {token}" if platform == 'github' else f"--header=Authorization: token {token}")
            result_wget = subprocess.run(cmd_wget, capture_output=True, timeout=70)
            if result_wget.returncode == 0 and filepath.exists() and filepath.stat().st_size > 0:
                print(f"✓ Downloaded with wget fallback: {url} -> {filepath}")
                return True
        except:
            pass
        return False

def _url_to_path(url: str, output_dir: Path, force_hash: bool = False) -> Path:
    parsed = urlparse(url)
    if not parsed.netloc:
        safe_path = re.sub(r'[<>:"|?*\]', '', unquote(url))
        if len(safe_path) > 50 or force_hash:
            safe_path = hashlib.md5(safe_path.encode()).hexdigest()[:16] + Path(safe_path).suffix
        return output_dir / safe_path
    domain = parsed.netloc
    if len(domain) > 50:
        domain = hashlib.md5(domain.encode()).hexdigest()[:16]
    path_segments = [s for s in parsed.path.strip('/').split('/') if s]
    hashed_segments = []
    for segment in path_segments:
        safe_seg = re.sub(r'[<>:"|?*\]', '_', unquote(segment))
        if len(safe_seg) > 50 or force_hash:
            safe_seg = hashlib.md5(safe_seg.encode()).hexdigest()[:16] + ('.' + Path(segment).suffix if '.' in segment else '')
        hashed_segments.append(safe_seg)
    path = '/'.join(hashed_segments)
    if not path:
        path = 'index.html'
    full_path = f"{domain}/{path}"
    return output_dir / full_path

async def retry_failed_files(output_dir: Path, failed_urls: List[str]):
    if not failed_urls:
        print("No failed URLs to retry.")
        return
    print(f"Starting enhanced retry for {len(failed_urls)} URLs...")
    print("Step 1: Aiohttp parallel retry...")
    tasks = [download_with_aiohttp_retry(url, output_dir) for url in failed_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    aio_success = sum(1 for r in results if r is True)
    print(f"Aiohttp: {aio_success}/{len(failed_urls)} success")
    remaining = [url for idx, url in enumerate(failed_urls) if results[idx] is not True]
    failed_after_requests = []
    if remaining:
        print(f"Step 2: Requests fallback for {len(remaining)} remaining...")
        for url in remaining:
            methods = ['get', 'head_get', 'no_headers']
            success = False
            for method in methods:
                try:
                    if download_with_requests(url, output_dir, method):
                        success = True
                        break
                except:
                    continue
            if not success:
                failed_after_requests.append(url)
            await asyncio.sleep(0.5)
    ultimate_fails = failed_after_requests
    if ultimate_fails:
        print(f"Step 3: Curl/wget fallback for {len(ultimate_fails)} ultimate fails...")
        for url in ultimate_fails:
            download_with_curl(url, output_dir)
    print("Enhanced retry complete. Check output_dir for new/overwritten files.")
    print("Research notes: Used exponential backoff (tenacity), multi-headers, subprocess curl for bypass. For persistent fails: proxy/VPN or check robots.txt.")

async def main(output_dir_str: str):
    output_dir = Path(output_dir_str)
    failed_urls = load_manifest(output_dir)
    await retry_failed_files(output_dir, failed_urls)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python retry_failed_enhanced.py <output_dir>")
    else:
        asyncio.run(main(sys.argv[1]))