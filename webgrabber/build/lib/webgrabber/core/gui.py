# Vị trí lưu: webgrabber/webgrabber/core/gui.py
import asyncio
import json
import os
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk, Toplevel, Text, simpledialog

from playwright._impl._errors import Error as PlaywrightError

from .audit_logger import log_audit
from .orchestrator import run_intelligent_capture
from .session_manager import SessionManager
from .config_manager import ConfigManager
from .preview_server import PreviewServer
from .batch_processor import BatchProcessor

class WebGrabberGUI:
    """The main class for the WebGrabber Graphical User Interface."""
    def __init__(self, root):
        self.root = root
        self.root.title("🌐 WebGrabber v1.0 - Intelligent Source Downloader")
        self.root.geometry("850x800")
        
        self.cancel_event = None
        self.preview_server = None
        
        self.config_manager = ConfigManager()
        self.create_menu()
        
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Khu vực nhập URL ---
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, expand=True, pady=(0, 5))
        ttk.Label(url_frame, text="🔗 URL / Batch File:", font=("Segoe UI", 10, "bold")).pack(side=tk.TOP, anchor="w")
        
        self.url_entry = ttk.Entry(url_frame, width=70)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(url_frame, text="Load File...", command=self.load_batch_file).pack(side=tk.LEFT, padx=(5, 0))

        # --- Khu vực chọn thư mục đầu ra ---
        ttk.Label(main_frame, text="💾 Output Directory:", font=("Segoe UI", 10, "bold")).pack(pady=(10, 5), anchor="w")
        out_frame = ttk.Frame(main_frame)
        out_frame.pack(fill=tk.X, expand=True)
        self.out_folder = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.out_folder).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_frame, text="Browse...", command=self.choose_folder).pack(side=tk.LEFT, padx=(5, 0))

        # --- Tùy chọn nâng cao (Export) ---
        export_frame = ttk.Frame(main_frame)
        export_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(export_frame, text="📦 Export Options:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        self.export_zip_var = tk.BooleanVar(value=False)
        self.init_git_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(export_frame, text="Export as ZIP", variable=self.export_zip_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(export_frame, text="Init local Git repo", variable=self.init_git_var).pack(side=tk.LEFT, padx=5)

        # --- Các nút hành động ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        self.download_btn = ttk.Button(btn_frame, text="⬇️ Start Download", command=self.start_download)
        self.download_btn.pack(side=tk.LEFT, padx=5, ipady=5)

        # THÊM MỚI: Nút dừng tải
        self.stop_btn = ttk.Button(btn_frame, text="⏹️ Stop Download", command=self.stop_download, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5, ipady=5)

        self.preview_btn = ttk.Button(btn_frame, text="🌐 Preview Site", command=self.preview_site, state=tk.DISABLED)
        self.preview_btn.pack(side=tk.LEFT, padx=5, ipady=5)

        # --- Hiển thị tiến trình và trạng thái ---
        self.status_label = ttk.Label(main_frame, text="Ready.")
        self.status_label.pack(anchor="w", pady=(5, 0))
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", mode="indeterminate")
        self.progress.pack(pady=5, fill=tk.X, expand=True)

        # --- Nhật ký hoạt động ---
        ttk.Label(main_frame, text="🧾 Activity Log:", font=("Segoe UI", 10, "bold")).pack(pady=(10, 5), anchor="w")
        self.log_text = scrolledtext.ScrolledText(main_frame, height=15, state=tk.DISABLED, font=("Courier New", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def create_menu(self):
        """Tạo menu chính của ứng dụng."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        session_menu = tk.Menu(menubar, tearoff=0)
        session_menu.add_command(label="Login via Browser (Interactive)", command=self.interactive_login)
        session_menu.add_separator()
        session_menu.add_command(label="Import Cookies from Chrome", command=lambda: self.import_cookies('chrome'))
        session_menu.add_command(label="Import Cookies from Firefox", command=lambda: self.import_cookies('firefox'))
        menubar.add_cascade(label="Session", menu=session_menu)
        
        menubar.add_command(label="Settings", command=self.open_settings)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Install Required Browsers", command=self._run_playwright_install)
        menubar.add_cascade(label="Help", menu=help_menu)
        
    def choose_folder(self):
        """Mở hộp thoại để chọn thư mục đầu ra."""
        folder = filedialog.askdirectory()
        if folder: self.out_folder.set(folder)

    def interactive_login(self):
        """Bắt đầu quá trình đăng nhập tương tác trong một luồng riêng."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL first.")
            return
        
        self.log_message("Starting interactive login... Please follow instructions in the new browser window.")
        threading.Thread(
            target=lambda: asyncio.run(SessionManager(url, self.log_message).interactive_login()),
            daemon=True
        ).start()

    def import_cookies(self, browser):
        """Nhập cookie từ một trình duyệt được chỉ định."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL first.")
            return
            
        try:
            success = SessionManager(url, self.log_message).load_cookies_from_browser(browser)
            if success:
                messagebox.showinfo("Success", f"Cookies imported successfully from {browser.title()}!")
                self.log_message(f"Cookies imported from {browser.title()}.")
            else:
                messagebox.showwarning("Not Found", f"No relevant cookies were found in {browser.title()}.")
                self.log_message(f"Cookie import from {browser.title()} failed or found no cookies.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import cookies: {e}")
            self.log_message(f"Error importing cookies from {browser.title()}: {e}")

    def open_settings(self):
        """Mở cửa sổ cài đặt nâng cao."""
        SettingsWindow(self.root, self.config_manager)

    def log_message(self, msg: str):
        """Ghi một thông báo vào GUI một cách an toàn cho luồng."""
        def _log():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {msg}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, _log)
        log_audit(msg)

    def _prompt_for_token(self, platform: str) -> str:
        """Hàm callback để orchestrator yêu cầu token."""
        self.log_message(f"ACTION REQUIRED: Please provide a token for {platform.title()}")
        token = simpledialog.askstring(
            f"{platform.title()} Token Required",
            f"Please enter your Personal Access Token for {platform.title()}:",
            parent=self.root,
            show='*'
        )
        return token or ""

    def load_batch_file(self):
        """Mở hộp thoại chọn file TXT chứa danh sách URL."""
        file_path = filedialog.askopenfilename(
            title="Select Batch File", 
            filetypes=(("Text Files", "*.txt"), ("All Files", "*.*"))
        )
        if file_path:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, file_path)

    def start_download(self):
        """Bắt đầu quá trình tải xuống chính trong một luồng nền."""
        url_input = self.url_entry.get().strip()
        folder = self.out_folder.get().strip()
        if not url_input or not folder:
            messagebox.showerror("Error", "URL/Batch File and Output Directory are required.")
            return

        # NÂNG CẤP: Thiết lập cấu hình Export dựa trên Checkboxes
        export_config = {
            'export_zip': self.export_zip_var.get(),
            'init_git': self.init_git_var.get()
        }
        self.config_manager.set_value('export', export_config)

        # Thiết lập trạng thái các nút và sự kiện hủy
        self.cancel_event = threading.Event()
        self.download_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start()
        self.status_label.config(text="Starting download...")

        def run_async():
            try:
                # Kiểm tra xem input là đường dẫn file (Batch Mode) hay URL đơn
                import os
                if os.path.isfile(url_input):
                    self.log_message(f"Starting Batch Process from file: {url_input}")
                    with open(url_input, 'r', encoding='utf-8') as f:
                        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    
                    if not urls:
                        self.log_message("❌ Batch file is empty or contains no valid URLs.")
                        return

                    processor = BatchProcessor(
                        urls=urls,
                        base_output_dir=Path(folder),
                        log_callback=self.log_message,
                        token_callback=self._prompt_for_token,
                        cancel_event=self.cancel_event
                    )
                    asyncio.run(processor.run())
                    
                    if self.cancel_event and not self.cancel_event.is_set():
                        self.log_message(f"✅ Batch Process complete! Processed {len(urls)} URLs.")
                        messagebox.showinfo("Success", f"Batch Processing finished!\nCheck output folder:\n{folder}")
                
                else:
                    # Chế độ tải 1 URL duy nhất
                    self.log_message(f"Starting intelligent download for {url_input}")
                    file_tree = asyncio.run(
                        run_intelligent_capture(
                            url=url_input,
                            output_dir=folder,
                            log_callback=self.log_message,
                            token_callback=self._prompt_for_token,
                            cancel_event=self.cancel_event
                        )
                    )
                    
                    if self.cancel_event and not self.cancel_event.is_set():
                        self.log_message(f"✅ Download complete! {len(file_tree)} files processed.")
                        self.root.after(0, lambda: self.preview_btn.config(state=tk.NORMAL))
                        messagebox.showinfo("Success", f"Download finished!\n{len(file_tree)} files saved to:\n{folder}\n\nClick 'Preview Site' to view offline.")
            
            except PlaywrightError as e:
                if "Executable doesn't exist" in str(e):
                    self.log_message("❌ Playwright browsers not found.")
                    if messagebox.askyesno("Playwright Installation Required",
                                           "Required browser files are missing.\n\n"
                                           "This is necessary for the website capture strategy.\n\n"
                                           "Would you like to install them now? (This may take a few minutes)"):
                        self.root.after(0, self._run_playwright_install)
                else:
                    import traceback
                    self.log_message(f"❌ A Playwright error occurred: {e}\n{traceback.format_exc()}")
                    messagebox.showerror("Error", str(e))
            except Exception as e:
                # Không hiển thị lỗi nếu đó là do người dùng hủy
                if not (self.cancel_event and self.cancel_event.is_set()):
                    import traceback
                    self.log_message(f"❌ An error occurred: {e}\n{traceback.format_exc()}")
                    messagebox.showerror("Error", str(e))
            finally:
                self.root.after(0, self.reset_ui_after_download)
        
        threading.Thread(target=run_async, daemon=True).start()

    # THÊM MỚI: Hàm để dừng việc tải xuống
    def stop_download(self):
        """Gửi tín hiệu cho luồng tải xuống để dừng lại."""
        if self.cancel_event:
            self.log_message("⏹️ Stop signal sent. Waiting for current operation to terminate...")
            self.cancel_event.set()
            self.stop_btn.config(state=tk.DISABLED)

    def preview_site(self):
        """Start local preview server and open browser."""
        folder = self.out_folder.get().strip()
        if not folder:
            messagebox.showerror("Error", "No output directory set.")
            return

        # Stop existing preview if running
        if self.preview_server and self.preview_server.is_running:
            self.preview_server.stop()

        try:
            self.preview_server = PreviewServer(
                directory=folder,
                log_callback=self.log_message,
                spa_mode=True,
            )
            url = self.preview_server.start()
            self.preview_server.open_browser()
            self.log_message(f"🌐 Preview running at {url}")
            self.status_label.config(text=f"Preview: {url}")
        except Exception as e:
            self.log_message(f"❌ Preview server error: {e}")
            messagebox.showerror("Error", f"Could not start preview: {e}")

    def reset_ui_after_download(self):
        """Đặt lại giao diện về trạng thái ban đầu."""
        self.download_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress.stop()
        self.status_label.config(text="Ready.")
        self.cancel_event = None

    def _run_playwright_install(self):
        """Tạo một cửa sổ modal và chạy 'playwright install' trong một luồng."""
        install_window = Toplevel(self.root)
        install_window.title("Installing Playwright Browsers...")
        install_window.geometry("700x400")
        install_window.transient(self.root)
        install_window.grab_set()

        log_area = scrolledtext.ScrolledText(install_window, state=tk.DISABLED, font=("Courier New", 9), wrap=tk.WORD, bg="black", fg="white")
        log_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        status_label = ttk.Label(install_window, text="Starting installation...")
        status_label.pack(pady=(0, 10))

        def log_to_widget(msg):
            log_area.config(state=tk.NORMAL)
            log_area.insert(tk.END, msg)
            log_area.see(tk.END)
            log_area.config(state=tk.DISABLED)

        def run_install():
            self.root.after(0, lambda: self.download_btn.config(state=tk.DISABLED))
            self.root.after(0, log_to_widget, "Running 'python -m playwright install'...\nThis might take several minutes.\n\n")
            
            try:
                creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                process = subprocess.Popen(
                    ['python', '-m', 'playwright', 'install'], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    encoding='utf-8',
                    creationflags=creation_flags
                )

                for line in iter(process.stdout.readline, ''):
                    self.root.after(0, log_to_widget, line)
                
                process.stdout.close()
                return_code = process.wait()

                if return_code == 0:
                    self.root.after(0, lambda: status_label.config(text="Installation successful! You can close this window."))
                    self.root.after(0, lambda: messagebox.showinfo("Success", "Browsers installed successfully!\nPlease try the download again.", parent=install_window))
                else:
                    self.root.after(0, lambda: status_label.config(text="Installation failed! See log for details."))
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Installation failed with exit code {return_code}.\n\nRun 'python -m playwright install' manually to debug.", parent=install_window))
            except FileNotFoundError:
                 self.root.after(0, lambda: messagebox.showerror("Error", "Could not find 'python'. Please ensure Python is in your system PATH.", parent=install_window))
            except Exception as ex:
                self.root.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred: {ex}", parent=install_window))
            finally:
                self.root.after(0, lambda: self.reset_ui_after_download())

        threading.Thread(target=run_install, daemon=True).start()

class SettingsWindow(Toplevel):
    """Một cửa sổ Toplevel để chỉnh sửa file config.json của ứng dụng."""
    def __init__(self, parent, config_manager):
        super().__init__(parent)
        self.config_manager = config_manager
        self.title("Advanced Settings")
        self.geometry("600x400")

        self.text_editor = Text(self, wrap="word", font=("Courier New", 10))
        self.text_editor.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.text_editor.insert("1.0", json.dumps(self.config_manager.get_config(), indent=4))
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        ttk.Button(btn_frame, text="Save and Close", command=self.save_and_close).pack()

    def save_and_close(self):
        """Lưu cấu hình và đóng cửa sổ."""
        try:
            new_config_str = self.text_editor.get("1.0", "end")
            new_config = json.loads(new_config_str)
            self.config_manager.save_config(new_config)
            self.destroy()
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON format. Please correct it before saving.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}", parent=self)

if __name__ == '__main__':
    root = tk.Tk()
    app = WebGrabberGUI(root)
    root.mainloop()

