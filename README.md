# WebGrabber

## Giới thiệu

WebGrabber là một công cụ mã nguồn mở mạnh mẽ được thiết kế để capture và download toàn bộ source code từ các website hoặc repository Git (như GitHub, GitLab, Bitbucket, v.v.). Tool hỗ trợ rendering JavaScript động bằng Playwright, xử lý sourcemaps, tải tài nguyên ẩn (như .env, package.json), và clone repo đầy đủ với xác thực (token, basic auth). 

Phiên bản hiện tại (0.9.0) nâng cấp hỗ trợ git clone cho source code đầy đủ, xử lý đường dẫn dài (hash tự động cho Windows), và retry nâng cao cho tài nguyên thất bại. Tool phù hợp cho developer, researcher, hoặc ai cần lưu trữ offline toàn bộ dự án web.

### Tính năng chính
- **Capture Website**: Tải HTML, CSS, JS, images, fonts, videos, và tài nguyên động (lazy load, AJAX).
- **Git Clone Mode**: Clone repo từ GitHub/GitLab/etc. với hỗ trợ HTTPS auth và fallback Perforce/Helix.
- **Stealth Mode**: Bỏ qua phát hiện bot, simulate human behavior (scroll, click).
- **Xử lý Sourcemaps**: Parse và reconstruct source gốc từ inline/external maps.
- **Long Path Handling**: Tự động hash đường dẫn dài để tránh lỗi Windows.
- **Retry Enhanced**: Tải lại tài nguyên thất bại với aiohttp, requests, curl/wget fallback.
- **Output**: Lưu thành file tree, manifest.json, và archive (ZIP/TAR.GZ).
- **Plugins**: Hỗ trợ Lua script cho tương tác tùy chỉnh (click, press keys).
- **GUI/CLI**: Chạy qua GUI đơn giản hoặc CLI.

## Yêu cầu hệ thống
- Python 3.8+
- Hệ điều hành: Windows/Linux/macOS (hỗ trợ headless browser).

## Cài đặt

### Bước 1: Cập nhật pip
```bash
pip install --upgrade pip
```

### Bước 2: Cài đặt dependencies từ requirements.txt
```bash
pip install -r requirements.txt
```
*(Danh sách: click, playwright, aiohttp, requests, beautifulsoup4, cssutils, tenacity, lupa, pybind11, pygit2, pyjnius, sourcemap)*

### Bước 3: Cài đặt thêm Git-related packages (cho git clone)
```bash
pip install gitpython PyGithub python-gitlab docker requests libvcs
```

### Bước 4: Cài đặt package editable (development mode)
```bash
pip install setuptools
pip install -e .
pip install sourcemap pyjnius lupa tenacity pyee pybind11 greenlet cssutils cffi beautifulsoup4 aiohappyeyeballs pygit2 playwright cryptography aiohttp
```
*(Hoặc dùng `python setup.py install` nếu không dùng editable).*

## Nếu không được anh em tải từng lệnh cho mình
```bash
pip install setuptools
pip install -e 
pip install sourcemap
pip install pyjnius
pip install lupa
pip install tenacity
pip install pyee
pip install pybind11
pip install greenlet
pip install cssutils
pip install cffi
pip install beautifulsoup4
pip install aiohappyeyeballsb
pip install pygit2
pip install playwright
pip install cryptography
pip install aiohttp
playwright install
playwright install chromium
pip install webgrabber
```
### Bước 5: Cài đặt Playwright browsers
```bash
playwright install
playwright install chromium  # Hoặc full: playwright install    # Nếu không được chạy thử "python -m playwright install chromium"

```

### Bước 6: Cài đặt package chính (nếu không dùng editable)
```bash
pip install webgrabber
```

Sau khi cài đặt, kiểm tra bằng lệnh:
```bash
webgrabber --help
```

## Hướng dẫn sử dụng

### Chạy GUI
Tool chính chạy qua GUI để dễ dàng nhập URL, config options (render JS, auth, git clone, v.v.), và xem tree file.
```bash
python -m webgrabber.core.gui
```
- **Input**: URL website hoặc Git repo (e.g., https://github.com/user/repo).
- **Options**:
  - `render_js`: True (render JS động).
  - `git_clone`: True (cho repo Git).
  - `auth_path`: Đường dẫn file JSON auth (cookies, headers, token).
  - `out`: Thư mục output.
  - `ignore_robots`: Bỏ qua robots.txt.
- **Output**: Thư mục chứa resources, manifest.json, và tree file cho GUI display.

### Sử dụng CLI (nếu có entry point)
```bash
webgrabber capture --url https://example.com --out ./output --render-js --git-clone
```
*(Kiểm tra `webgrabber --help` để xem đầy đủ args).*

### Ví dụ capture website
1. Chạy GUI, nhập URL: `https://example.com`.
2. Chọn render JS và ignore robots nếu cần.
3. Output: Thư mục `./output` với index.html, assets, manifest.json.

### Ví dụ git clone
1. Nhập URL: `https://github.com/user/repo.git`.
2. Cung cấp auth_path: `{"token": "ghp_xxx"}` (file JSON).
3. Output: Clone đầy đủ repo vào `./output`, với tree files.

### Retry failed resources
Sau capture, nếu có failed URLs (trong manifest.json), chạy:
```bash
python webgrabber/tools/retry_failed_enhanced.py ./output
```
Tool sẽ retry với aiohttp, requests, curl/wget.

### Test tool
Chạy unit test:
```bash
python -m unittest webgrabber.tests.test_crawler
```

## Cấu trúc dự án
```
webgrabber/
├── core/
│   ├── orchestrator.py     # Main runner (capture + git clone)
│   ├── session_manager.py  # Handle auth/cookies
│   └── sourcemap_handler.py # Parse sourcemaps
├── crawler/
│   ├── playwright_driver.py # Browser automation
│   └── resource_collector.py # UltraCollectorV10 (main logic)
├── output/
│   ├── archiver.py         # ZIP/TAR archive
│   ├── manifest_gen.py     # Generate manifest.json
│   └── tree_builder.py     # Build file tree
├── plugins/
│   └── lua_runner.py       # Lua script support
├── tools/
│   └── retry_failed_enhanced.py # Retry tool
├── tests/
│   └── test_crawler.py     # Unit tests
├── setup.py                # Setup script
└── requirements.txt        # Dependencies
```

## Troubleshooting
- **Playwright error**: Chạy `playwright install chromium`.
- **Git auth fail**: Kiểm tra token trong auth JSON.
- **Long path Windows**: Tool tự hash, nhưng kiểm tra `max_path_segment=50` trong config.
- **No internet**: Tool cần kết nối để download.
- **Dependencies conflict**: Sử dụng virtualenv.


## Cách điền proxy trong GUI

**Chạy GUI bằng lệnh**: "python -m webgrabber.core.gui"
Trong giao diện, có ô "🛡️ Proxy:" (dưới phần tùy chọn tải).
**Điền vào ô đó format giống CLI**, ví dụ: http://youruser:yourpass@proxyhost.com:8080.
Sau đó chọn các tùy chọn khác (như "Clone Git Repo") và nhấn "⬇️ Tải về".
Proxy sẽ được truyền vào orchestrator để dùng trong capture/clone.


## Giấy phép
MIT License. Contribute tại GitHub: [your-repo-link].

## Liên hệ
- Author: [Nguyễn Quang Tú]
- Issues: [GitHub qtu]
