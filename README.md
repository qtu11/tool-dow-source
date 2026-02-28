<div align="center">
  <img src="https://raw.githubusercontent.com/playwright-community/playwright-python/master/docs/logo.svg" alt="Logo" width="120"/>
  <h1>🕸️ WebGrabber v2.0 - Deep Source Recovery Engine</h1>
  <p><strong>Công Cụ Cào Dữ Liệu & Phục Hồi Mã Nguồn Frontend Cấp Độ Chuyên Gia</strong></p>

  <p>
    <a href="https://github.com/microsoft/playwright-python"><img src="https://img.shields.io/badge/Powered%20by-Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
    <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License">
    <img src="https://img.shields.io/badge/Status-Active-success?style=for-the-badge" alt="Status">
  </p>
</div>

---

## � Giới thiệu (Introduction)

**WebGrabber v2.0** không chỉ là một trình cào web (web scraper/crawler) thông thường. Đây là một cỗ máy **Deep Source Recovery** (Khôi phục mã nguồn sâu) được thiết kế đặc biệt dành cho các chuyên gia an ninh mạng, kỹ sư reverse engineering, và lập trình viên muốn nghiên cứu kiến trúc của các ứng dụng web hiện đại (SPA, SSR, SSG).

Công cụ này vượt qua ranh giới của việc chỉ tải HTML/CSS. Bằng các kỹ thuật phân tích gói tin (traffic interception), vượt qua tường lửa/anti-bot (Cloudflare, Akamai), cơ chế brute-force và giải mã, WebGrabber có khả năng **"dựng lại hiện trường"** của một dự án web trước khi nó bị minify và bundle bởi Webpack/Vite.

---

## 🚀 Tính Năng Chuyên Sâu (Deep/Pro Features)

### 1. 🕵️‍♂️ Deep Source Recovery Engine (Cốt lõi Mới - Độc quyền v2.0)
- **Source Map Brute-forcer & Extractor:** Tự động rà quét, phát hiện và tải xuống các tệp `*.map` (ngay cả khi bị ẩn Header hoặc chèn Base64 dưới dạng comment). Trích xuất ngược (reverse) hoàn hảo ra cấu trúc thư mục gồm các file `*.jsx`, `*.tsx`, `*.vue`, `*.ts` gốc.
- **Webpack/Vite Debundler:** Khi trang web chặn hoặc xóa Source Maps ở môi trường Production, công cụ sẽ đọc mảng `__webpack_modules__` hoặc các chunk bundle. Từ đó cắt nhỏ và bóc tách từng module React/Vue/Angular nội bộ, cứu vãn được cấu trúc component.
- **JavaScript Code Beautifier:** Tích hợp `jsbeautifier` để làm đẹp (format) lại các file JS đã bị làm rối (obfuscated) hoặc nén (minified), biến chúng trở thành các đoạn code con người đọc được.
- **Next.js & Nuxt.js Deep Reconnaissance:** Khai thác các tệp metadata sinh tự động ra của Next.js (như `_buildManifest.js`, `_ssgManifest.js`, và thư mục nội bộ `/_next/data/...`) nhằm dựng lại Site Map đầy đủ, bao gồm toàn bộ các API ẩn và props tĩnh.
- **Local Git Repository Discovery:** Gửi truy vấn HTTP thầm lặng thăm dò thư mục ẩn `/.git/`, kiểm tra `package.json` hoặc Git metadata bị lộ cấu hình. Nếu phát hiện repo public, gợi ý và có thể tự fetch mã nguồn gốc 100% từ GitHub/Gitlab.

### 2. �️ Cơ Chế Stealth & Chống Chặn (Anti-Bot Bypass)
- **Playwright Automation Engine:** Sử dụng trình duyệt thực Chromium/Firefox (Headless hoặc Headful) ngụy trang bằng Fingerprint giả, tự động cuộn trang (Lazy-load trigger) và Bypass Cloudflare Turnstile hay reCAPTCHA cơ bản.
- **Network Interception & API Dumping:** Bắt trọn toàn bộ lưu lượng mạng (XHR / Fetch). Lưu trữ các API payload (`*.json`, `*.xml`) truyền tải ngầm mà các tool dùng cURL cổ điển không bao giờ bắt được.

### 3. 🖥️ Giao Diện Người Dùng & Tiện Ích Đỉnh Cao (Modern GUI)
- **Dark Obsidian UI:** Giao diện đồ họa (Tkinter) viết lại hoàn toàn mang phong cách Dark Theme Hacker-style sang trọng. Thể hiện tiến trình tải qua Progress Bar, console log trực tiếp với mảng màu báo lỗi / phân loại pha xử lý (Phases).
- **Session Import & Auth Handle:** Tự động đồng bộ Cookie (nhập từ trình duyệt Chrome, Edge, Firefox đang chạy ở máy tính bạn) để qua cửa các page bắt buộc đăng nhập (Facebook, X, Forums, Bảng điều khiển Admin).
- **Trình Cắm Local Server:** Nút "Preview Site" dựng ngay 1 HTTP server giả lập hỗ trợ Routing của SPA (Single Page Application) giúp bạn duyệt web ở Offline Mode hoàn hảo 100% không vỡ giao diện.
- **Batch Processing:** Nhập danh sách hàng trăm URL qua file `.txt`. Tool sẽ chạy hàng đợi Queue an toàn. Tự động xuất ra file nén `.zip` tùy chọn.

---

## ⚙️ Hướng Dẫn Setup & Cài Đặt (Step-by-Step)

WebGrabber yêu cầu **Python 3.10 trở lên** để chạy các chức năng async mới nhất. Bạn nên dùng môi trường ảo để không xung đột thư viện.

### Môi Trường Windows (Powershell)

```powershell
# 1. Clone source code (Nếu dùng Git)
git clone https://github.com/qtu11/webgrabber.git
cd webgrabber

# 2. Tạo thiết lập Môi trường ảo (Khuyên dùng)
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Cài đặt toàn bộ thư viện cần thiết
pip install --upgrade pip
pip install -r requirements.txt

# 4. Tải xuống bộ nhân trình duyệt tự khởi động (Chromium, Firefox, Webkit)
python -m playwright install
```

### Môi Trường Linux / macOS / Ubuntu (Terminal bash)

```bash
# 1. Update APT và Cài đặt thư viện hệ thống (dành cho Linux)
sudo apt update
sudo apt install software-properties-common python3-venv python3-pip

# 2. Setup Venv
python3 -m venv venv
source venv/bin/activate

# 3. Cập nhật và cài dependencies
pip install -r requirements.txt

# 4. Tải bộ nhân trình duyệt + Dependencies system của Playwright
python -m playwright install
python -m playwright install-deps
```

> **Lưu ý Quan Trọng:** Nếu bạn không muốn cài tất cả các trình duyệt, bạn có thể chạy `python -m playwright install chromium` cho nhẹ máy (chỉ tải riêng Chrome).

---

## 🎮 Cách Sử Dụng (Usage Guide)

### 1. Khởi chạy Giao Diện Đồ Họa (GUI Mode)

Cách dễ nhất và khuyến nghị nhất là dùng giao diện:
*(Hoặc click chuột thẳng vào `run_webgrabber.ps1` đối với Windows)*

```bash
python -m webgrabber.core.gui
```

**Workflow sử dụng App:**
1. **Target URL:** Nhập link website bạn muốn phân tích, hoặc bấm `Load Batch` nếu bạn có 1 cục file `list.txt` ghi nhiều URL mỗi dòng 1 Link.
2. **Output Directory:** Nơi bạn muốn đẻ ra thư mục mã nguồn. *(Nên chọn thư mục rỗng để chứa)*
3. **Menu Session (Quan trọng):**
   - Nếu web bắt mật khẩu hoặc Login 👉 Vào Menu top App: `Session` -> `Login via Browser`.
   - Tool sẽ mở 1 tab lên, bạn nhập tài khoản mật khẩu (bằng tay) xong gập tab đó xuống, nó sẽ ghi nhớ Session.
4. Tích chọn Option **"Export ZIP"** nếu bạn muốn có 1 file Archive nén mang đi nộp báo cáo hoặc backup.
5. Nhấn **Start Download** (nút Xanh). Quá trình có 7 Pha (Phases) sẽ hiển thị ở màn hình Console Log.
6. Khi hoàn tất, nhấn **Preview Site** để Review thành quả tải về nội bộ bằng Routing ảo.

### 2. Ý Nghĩa Cấu Trúc Khôi Phục (Output Directory Structure)

Sau quá trình cào mảng 7 Pha (bao gồm Interceptor, URL Rewriting, SourceMap BF, Webpack Debundle, Next.js Recon), bạn sẽ có Output cực khủng:

```text
/Luu-Tru-cua-Ban/ (Output Dir)
├── index.html                   [Mặt tiền - Trang chủ đã tải tĩnh offline]
├── assets/                      [Chứa CSS, Images, Fonts đã thiết lập lại URL Link Base]
│
├── _source_maps/                [🔥 KẾT QUẢ ĐẮT GIÁ: Nơi chứa đống Map và File gốc JSX, Vue]
│   ├── components/Header.jsx    [Mã gốc dev tự tay viết, rớt ra từ .map]
│   └── views/Layout.vue
│
├── _debundled/                  [🔥 Nơi chứa dữ liệu tách ra từ Webpack nếu mất Map]
│   └── modules/
│       ├── chunk-0.js           [JavaScript đã được chạy Tool Code Format/Beautifier lại]
│       └── react_253.js
│
├── _nextjs_recon/               [🔥 Các cấu trúc file trích xuất nếu Target là Next.js]
│   ├── paths_ssg.json           [Danh sách tất cả các path ảo nội bộ giấu kín]
│   └── build_manifest.js
│
├── _api_data/                   [JSON Payload Response bị chặn lại từ Backend]
│
└── website_export.zip           [File Export tùy chọn]
```

---

## 🧠 Hiểu Về Kiến Trúc 7 Pha Xử Lý (The 7-Phase Pipeline)

1. **Phase 1: Deep Crawling & Intercept:** Dùng Playwright mở trang, cuộn trang theo dõi XHR, lấy DOM, tải JS/CSS và lưu Payload.
2. **Phase 2: Rewrite Local Path:** Viết lại toàn bộ `<img src>`, `<link href>`, `import()`, CSS `url()` trỏ về hệ thống File Path Relative Offline trên máy cục bộ của bạn.  
3. **Phase 3: Database Cache Save:** Lưu mảng tệp vào cấu trúc băm sha256 (Hash Caching) tiết kiệm ổ cứng.
4. **Phase 4: Source Map Brute-force:** Bắt đầu phân tích tìm file `*.map` và dịch ngược file bản Base64 -> Cứu ra Source gốc.
5. **Phase 5: Webpack Debundle:** Nếu Phase 4 hụt, bật chế độ mổ xẻ mảng array của webpack. Format cho đẹp code lại.
6. **Phase 6: Framework Recon:** Kiểm tra chữ ký Framework (VD: `window.__NEXT_DATA__`) bốc cấu trúc ảo.
7. **Phase 7: Repo Discovery:** Kiểm tra thư mục Git có bị expose public hay không.

---

## �️ Khắc Phục Lỗi Cơ Bản (Troubleshooting FAQ)

| Hiện Tượng & Lỗi | Nguyên Nhân & Thuốc Chữa |
| :--- | :--- |
| **`TclError: window was deleted before...`** | Do gọi Menu Tkinter ở Thread con. **Đã fix ở v2.0**, nếu gặp lại hãy tải latest commit. |
| **`Playwright: Executable doesn't exist`** | Quên cài đặt Browser nhân Chromium. 👉 Chạy: `python -m playwright install` |
| **Báo Lỗi Missing Module Dependency (`ModuleNotFoundError`)** | Thư viện ảo chưa cập nhật. Chạy: `pip install -r requirements.txt` (Ví dụ thiếu `jsbeautifier` hoặc `aiohttp`). |
| **Khôi phục JS/TSX được 0 file (Phase 4, 5)** | Website đó không sử dụng Framework đóng gói, hoặc Server của họ xóa 100% tệp tin `.map` khi đem lên Production gắt gao. Hãy tự đọc file Webpack Chunk ở mục `assets/` thay thế. |
| **`Permission denied: C:\...` khi ghi Path** | Do trang web có Path quá dài bị Windows chặn. Phiên bản này đã tự động cắt hash MD5 Path, nhưng hãy tránh lưu project vào sâu thư mục như `C:\Users\X\Desktop\...\...`. |
| **Báo lỗi Memory Leak khi cào cực sâu**| Tắt tuỳ chọn "Unlimited recursive", giới hạn Max Pages (Settings Menu) xuống khoảng 500-1000 pages tuỳ máy. |

---

## 🤝 Roadmap & Đóng Góp (Contributing)

Tương lai chúng tôi định hướng:
- [ ] Thêm tính năng khử rối (Deobfuscator) thông minh (AST Tree).
- [ ] Hỗ trợ Recon cho kiến trúc Nuxt 3 và SvelteKit đỉnh cao hơn.
- [ ] Parse Firebase và Supabase Config Key lộ liễu.
- [ ] Thêm Crawler Queue dùng Redis phân tán cào hệ thống lớn.

Mọi ý tưởng vui lòng Push Request tại kho lưu trữ. Chúng tôi trân trọng các đóng góp kiến trúc từ Dev.

## � License & Tác Giả
- Ghi danh (Author): **Nguyễn Quang Tú (QtusDev)** - Senior System & Fullstack Architect
- MIT License - Miễn phí nghiên cứu và sử dụng, không thương mại hóa hay vi phạm pháp luật khai phá hệ thống trái phép. Công cụ được sinh ra nhằm mục đích học tập.
</div>
