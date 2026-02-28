# Vị trí lưu: webgrabber/webgrabber/core/gui.py
"""
WebGrabber v2.0 — Professional Dark Theme GUI
Dark Obsidian design with modern UX, full-featured controls.
"""
import asyncio
import json
import os
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk, Toplevel, Text, simpledialog

from playwright._impl._errors import Error as PlaywrightError

from .audit_logger import log_audit
from .orchestrator import run_intelligent_capture
from .session_manager import SessionManager
from .config_manager import ConfigManager
from .preview_server import PreviewServer
from .batch_processor import BatchProcessor

# ═══════════════════════════════════════════════════════
# THEME COLORS — Dark Obsidian
# ═══════════════════════════════════════════════════════
COLORS = {
    'bg_dark':       '#0d1117',
    'bg_card':       '#161b22',
    'bg_input':      '#21262d',
    'bg_hover':      '#30363d',
    'border':        '#30363d',
    'border_focus':  '#58a6ff',
    'text_primary':  '#e6edf3',
    'text_secondary':'#8b949e',
    'text_muted':    '#484f58',
    'accent_blue':   '#58a6ff',
    'accent_green':  '#3fb950',
    'accent_red':    '#f85149',
    'accent_orange': '#d29922',
    'accent_purple': '#bc8cff',
    'accent_cyan':   '#39d2c0',
    'btn_primary':   '#238636',
    'btn_primary_h': '#2ea043',
    'btn_danger':    '#da3633',
    'btn_danger_h':  '#f85149',
    'btn_default':   '#21262d',
    'btn_default_h': '#30363d',
    'log_bg':        '#0d1117',
    'log_info':      '#58a6ff',
    'log_success':   '#3fb950',
    'log_warning':   '#d29922',
    'log_error':     '#f85149',
    'progress_bg':   '#21262d',
    'progress_fill': '#58a6ff',
}

FONTS = {
    'title':     ('Segoe UI', 18, 'bold'),
    'subtitle':  ('Segoe UI', 11),
    'label':     ('Segoe UI', 10, 'bold'),
    'body':      ('Segoe UI', 10),
    'small':     ('Segoe UI', 9),
    'mono':      ('Cascadia Code', 9),
    'mono_log':  ('Cascadia Code', 9),
    'btn':       ('Segoe UI', 10, 'bold'),
    'btn_small': ('Segoe UI', 9),
}


class WebGrabberGUI:
    """Professional Dark Theme GUI for WebGrabber v2.0"""

    def __init__(self, root):
        self.root = root
        self.root.title("WebGrabber v2.0 — Intelligent Source Recovery Engine")
        self.root.geometry("1050x780")
        self.root.minsize(900, 650)
        self.root.configure(bg=COLORS['bg_dark'])

        self.cancel_event = None
        self.preview_server = None
        self.config_manager = ConfigManager()
        self.download_start_time = None

        # Configure dark ttk styles
        self._setup_styles()
        self._create_menu()
        self._build_ui()

    # ═══════════════ STYLES ═══════════════

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Frame
        style.configure('Dark.TFrame', background=COLORS['bg_dark'])
        style.configure('Card.TFrame', background=COLORS['bg_card'])

        # Labels
        style.configure('Dark.TLabel',
                         background=COLORS['bg_dark'],
                         foreground=COLORS['text_primary'],
                         font=FONTS['body'])
        style.configure('Title.TLabel',
                         background=COLORS['bg_dark'],
                         foreground=COLORS['text_primary'],
                         font=FONTS['title'])
        style.configure('Subtitle.TLabel',
                         background=COLORS['bg_dark'],
                         foreground=COLORS['text_secondary'],
                         font=FONTS['subtitle'])
        style.configure('Section.TLabel',
                         background=COLORS['bg_dark'],
                         foreground=COLORS['accent_blue'],
                         font=FONTS['label'])
        style.configure('Card.TLabel',
                         background=COLORS['bg_card'],
                         foreground=COLORS['text_primary'],
                         font=FONTS['body'])
        style.configure('CardSection.TLabel',
                         background=COLORS['bg_card'],
                         foreground=COLORS['accent_blue'],
                         font=FONTS['label'])
        style.configure('Status.TLabel',
                         background=COLORS['bg_dark'],
                         foreground=COLORS['accent_green'],
                         font=FONTS['small'])

        # Entry
        style.configure('Dark.TEntry',
                         fieldbackground=COLORS['bg_input'],
                         foreground=COLORS['text_primary'],
                         bordercolor=COLORS['border'],
                         insertcolor=COLORS['text_primary'])
        style.map('Dark.TEntry',
                   bordercolor=[('focus', COLORS['border_focus'])])

        # Buttons
        style.configure('Primary.TButton',
                         background=COLORS['btn_primary'],
                         foreground='white',
                         font=FONTS['btn'],
                         borderwidth=0,
                         padding=(16, 8))
        style.map('Primary.TButton',
                   background=[('active', COLORS['btn_primary_h']),
                               ('disabled', COLORS['bg_hover'])])

        style.configure('Danger.TButton',
                         background=COLORS['btn_danger'],
                         foreground='white',
                         font=FONTS['btn'],
                         borderwidth=0,
                         padding=(16, 8))
        style.map('Danger.TButton',
                   background=[('active', COLORS['btn_danger_h']),
                               ('disabled', COLORS['bg_hover'])])

        style.configure('Default.TButton',
                         background=COLORS['btn_default'],
                         foreground=COLORS['text_primary'],
                         font=FONTS['btn_small'],
                         borderwidth=1,
                         bordercolor=COLORS['border'],
                         padding=(12, 6))
        style.map('Default.TButton',
                   background=[('active', COLORS['btn_default_h']),
                               ('disabled', COLORS['bg_hover'])])

        style.configure('Small.TButton',
                         background=COLORS['btn_default'],
                         foreground=COLORS['text_secondary'],
                         font=FONTS['small'],
                         borderwidth=1,
                         bordercolor=COLORS['border'],
                         padding=(8, 4))
        style.map('Small.TButton',
                   background=[('active', COLORS['btn_default_h'])])

        # Checkbutton
        style.configure('Dark.TCheckbutton',
                         background=COLORS['bg_card'],
                         foreground=COLORS['text_primary'],
                         font=FONTS['body'])
        style.map('Dark.TCheckbutton',
                   background=[('active', COLORS['bg_card'])])

        # Progressbar
        style.configure('Custom.Horizontal.TProgressbar',
                         troughcolor=COLORS['progress_bg'],
                         background=COLORS['progress_fill'],
                         borderwidth=0,
                         thickness=6)

        # Separator
        style.configure('Dark.TSeparator', background=COLORS['border'])

    # ═══════════════ MENU ═══════════════

    def _create_menu(self):
        menubar = tk.Menu(self.root, bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                          activebackground=COLORS['accent_blue'], activeforeground='white',
                          borderwidth=0, relief='flat')
        self.root.config(menu=menubar)

        # Session menu
        session_menu = tk.Menu(menubar, tearoff=0,
                                bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                                activebackground=COLORS['accent_blue'], activeforeground='white')
        session_menu.add_command(label="🔓  Login via Browser", command=self.interactive_login)
        session_menu.add_separator()
        session_menu.add_command(label="🍪  Import from Chrome", command=lambda: self.import_cookies('chrome'))
        session_menu.add_command(label="🦊  Import from Firefox", command=lambda: self.import_cookies('firefox'))
        session_menu.add_command(label="🌊  Import from Edge", command=lambda: self.import_cookies('edge'))
        menubar.add_cascade(label="  Session  ", menu=session_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0,
                              bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                              activebackground=COLORS['accent_blue'], activeforeground='white')
        tools_menu.add_command(label="⚙️  Settings", command=self.open_settings)
        tools_menu.add_command(label="📦  Install Browsers", command=self._run_playwright_install)
        tools_menu.add_separator()
        tools_menu.add_command(label="📂  Open Output Folder", command=self._open_output_folder)
        tools_menu.add_command(label="🗑️  Clear Log", command=self._clear_log)
        menubar.add_cascade(label="  Tools  ", menu=tools_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0,
                             bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                             activebackground=COLORS['accent_blue'], activeforeground='white')
        help_menu.add_command(label="ℹ️  About", command=self._show_about)
        menubar.add_cascade(label="  Help  ", menu=help_menu)

    # ═══════════════ BUILD UI ═══════════════

    def _build_ui(self):
        # Main container
        container = tk.Frame(self.root, bg=COLORS['bg_dark'])
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))

        # ─── HEADER ───
        header = tk.Frame(container, bg=COLORS['bg_dark'])
        header.pack(fill=tk.X, pady=(0, 15))

        tk.Label(header, text="⚡ WebGrabber", font=FONTS['title'],
                 bg=COLORS['bg_dark'], fg=COLORS['text_primary']).pack(side=tk.LEFT)
        tk.Label(header, text="v2.0  •  Deep Source Recovery Engine", font=FONTS['subtitle'],
                 bg=COLORS['bg_dark'], fg=COLORS['text_secondary']).pack(side=tk.LEFT, padx=(8, 0), pady=(6, 0))

        # Status indicator
        self.header_status = tk.Label(header, text="● Ready", font=FONTS['small'],
                                       bg=COLORS['bg_dark'], fg=COLORS['accent_green'])
        self.header_status.pack(side=tk.RIGHT, pady=(6, 0))

        # ─── INPUT CARD ───
        input_card = tk.Frame(container, bg=COLORS['bg_card'], highlightbackground=COLORS['border'],
                               highlightthickness=1, padx=20, pady=16)
        input_card.pack(fill=tk.X, pady=(0, 12))

        # URL Input
        tk.Label(input_card, text="🔗  Target URL / Batch File",
                 font=FONTS['label'], bg=COLORS['bg_card'], fg=COLORS['accent_blue']).pack(anchor='w')

        url_row = tk.Frame(input_card, bg=COLORS['bg_card'])
        url_row.pack(fill=tk.X, pady=(6, 12))

        self.url_entry = tk.Entry(url_row, font=FONTS['body'],
                                   bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                                   insertbackground=COLORS['text_primary'],
                                   relief='flat', borderwidth=0,
                                   highlightbackground=COLORS['border'],
                                   highlightcolor=COLORS['border_focus'],
                                   highlightthickness=1)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 8))
        self.url_entry.insert(0, "https://")

        ttk.Button(url_row, text="📁 Load Batch", style='Default.TButton',
                    command=self.load_batch_file).pack(side=tk.RIGHT)

        # Output Dir
        tk.Label(input_card, text="💾  Output Directory",
                 font=FONTS['label'], bg=COLORS['bg_card'], fg=COLORS['accent_blue']).pack(anchor='w')

        out_row = tk.Frame(input_card, bg=COLORS['bg_card'])
        out_row.pack(fill=tk.X, pady=(6, 12))

        self.out_folder = tk.StringVar()
        tk.Entry(out_row, textvariable=self.out_folder, font=FONTS['body'],
                 bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                 insertbackground=COLORS['text_primary'],
                 relief='flat', borderwidth=0,
                 highlightbackground=COLORS['border'],
                 highlightcolor=COLORS['border_focus'],
                 highlightthickness=1).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 8))

        ttk.Button(out_row, text="📂 Browse", style='Default.TButton',
                    command=self.choose_folder).pack(side=tk.RIGHT)

        # ─── OPTIONS ROW ───
        opts_row = tk.Frame(input_card, bg=COLORS['bg_card'])
        opts_row.pack(fill=tk.X, pady=(0, 4))

        tk.Label(opts_row, text="📦  Export Options:", font=FONTS['label'],
                 bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(side=tk.LEFT, padx=(0, 12))

        self.export_zip_var = tk.BooleanVar(value=True)
        self.init_git_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts_row, text="ZIP Archive", variable=self.export_zip_var,
                        bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                        selectcolor=COLORS['bg_input'], activebackground=COLORS['bg_card'],
                        activeforeground=COLORS['text_primary'],
                        font=FONTS['body']).pack(side=tk.LEFT, padx=(0, 16))
        tk.Checkbutton(opts_row, text="Init Git Repo", variable=self.init_git_var,
                        bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                        selectcolor=COLORS['bg_input'], activebackground=COLORS['bg_card'],
                        activeforeground=COLORS['text_primary'],
                        font=FONTS['body']).pack(side=tk.LEFT)

        # ─── ACTION BUTTONS ───
        btn_frame = tk.Frame(container, bg=COLORS['bg_dark'])
        btn_frame.pack(fill=tk.X, pady=(0, 12))

        self.download_btn = ttk.Button(btn_frame, text="⬇  Start Download",
                                        style='Primary.TButton', command=self.start_download)
        self.download_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_btn = ttk.Button(btn_frame, text="⏹  Stop",
                                    style='Danger.TButton', command=self.stop_download,
                                    state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.preview_btn = ttk.Button(btn_frame, text="🌐  Preview Site",
                                       style='Default.TButton', command=self.preview_site,
                                       state=tk.DISABLED)
        self.preview_btn.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(btn_frame, text="📂  Open Folder", style='Default.TButton',
                    command=self._open_output_folder).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(btn_frame, text="🗑  Clear", style='Small.TButton',
                    command=self._clear_log).pack(side=tk.RIGHT)

        # ─── PROGRESS BAR ───
        progress_frame = tk.Frame(container, bg=COLORS['bg_dark'])
        progress_frame.pack(fill=tk.X, pady=(0, 4))

        self.progress = ttk.Progressbar(progress_frame, style='Custom.Horizontal.TProgressbar',
                                         orient='horizontal', mode='indeterminate')
        self.progress.pack(fill=tk.X)

        # Status row
        status_row = tk.Frame(container, bg=COLORS['bg_dark'])
        status_row.pack(fill=tk.X, pady=(2, 8))

        self.status_label = tk.Label(status_row, text="Ready — Enter a URL and click Start Download",
                                      font=FONTS['small'], bg=COLORS['bg_dark'],
                                      fg=COLORS['text_secondary'], anchor='w')
        self.status_label.pack(side=tk.LEFT)

        self.timer_label = tk.Label(status_row, text="", font=FONTS['small'],
                                     bg=COLORS['bg_dark'], fg=COLORS['text_muted'])
        self.timer_label.pack(side=tk.RIGHT)

        # ─── LOG AREA ───
        log_header = tk.Frame(container, bg=COLORS['bg_dark'])
        log_header.pack(fill=tk.X, pady=(0, 6))

        tk.Label(log_header, text="📋  Activity Log", font=FONTS['label'],
                 bg=COLORS['bg_dark'], fg=COLORS['accent_blue']).pack(side=tk.LEFT)

        # Log text widget
        log_frame = tk.Frame(container, bg=COLORS['border'], highlightthickness=0)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=FONTS['mono_log'],
                                 bg=COLORS['log_bg'], fg=COLORS['text_secondary'],
                                 insertbackground=COLORS['text_primary'],
                                 relief='flat', borderwidth=8, padx=12, pady=10,
                                 state=tk.DISABLED, cursor='arrow',
                                 selectbackground=COLORS['accent_blue'],
                                 selectforeground='white')
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview,
                                  bg=COLORS['bg_dark'], troughcolor=COLORS['bg_card'],
                                  width=10, relief='flat')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Configure log tags for colored output
        self.log_text.tag_configure('info', foreground=COLORS['log_info'])
        self.log_text.tag_configure('success', foreground=COLORS['log_success'])
        self.log_text.tag_configure('warning', foreground=COLORS['log_warning'])
        self.log_text.tag_configure('error', foreground=COLORS['log_error'])
        self.log_text.tag_configure('timestamp', foreground=COLORS['text_muted'])
        self.log_text.tag_configure('phase', foreground=COLORS['accent_purple'], font=('Cascadia Code', 9, 'bold'))

        # ─── FOOTER ───
        footer = tk.Frame(container, bg=COLORS['bg_dark'])
        footer.pack(fill=tk.X, pady=(8, 0))
        tk.Label(footer, text="WebGrabber v2.0 — Deep Source Recovery Engine  •  Built by QtusDev",
                 font=('Segoe UI', 8), bg=COLORS['bg_dark'], fg=COLORS['text_muted']).pack(side=tk.LEFT)

    # ═══════════════ CORE FUNCTIONS ═══════════════

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.out_folder.set(folder)

    def interactive_login(self):
        url = self.url_entry.get().strip()
        if not url or url == 'https://':
            messagebox.showerror("Error", "Please enter a URL first.")
            return
        self.log_message("Starting interactive login...")
        threading.Thread(
            target=lambda: asyncio.run(SessionManager(url, self.log_message).interactive_login()),
            daemon=True
        ).start()

    def import_cookies(self, browser):
        url = self.url_entry.get().strip()
        if not url or url == 'https://':
            messagebox.showerror("Error", "Please enter a URL first.")
            return
        try:
            success = SessionManager(url, self.log_message).load_cookies_from_browser(browser)
            if success:
                messagebox.showinfo("Success", f"Cookies imported from {browser.title()}!")
                self.log_message(f"✅ Cookies imported from {browser.title()}")
            else:
                messagebox.showwarning("Not Found", f"No cookies found in {browser.title()}")
        except Exception as e:
            messagebox.showerror("Error", f"Cookie import failed: {e}")

    def open_settings(self):
        SettingsWindow(self.root, self.config_manager)

    def load_batch_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Batch File",
            filetypes=(("Text Files", "*.txt"), ("All Files", "*.*"))
        )
        if file_path:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, file_path)

    # ═══════════════ LOGGING ═══════════════

    def log_message(self, msg: str):
        def _log():
            self.log_text.config(state=tk.NORMAL)

            # Timestamp
            ts = time.strftime('%H:%M:%S')
            self.log_text.insert(tk.END, f"{ts}", 'timestamp')
            self.log_text.insert(tk.END, " — ")

            # Color-coded message
            tag = None
            if any(e in msg for e in ['✅', 'Success', 'complete', 'OK']):
                tag = 'success'
            elif any(e in msg for e in ['❌', 'Error', 'Failed', 'error']):
                tag = 'error'
            elif any(e in msg for e in ['⚠️', 'Warning', 'warning']):
                tag = 'warning'
            elif any(e in msg for e in ['Phase', 'PHASE', '═══', '🔍', '🔬', '🔧']):
                tag = 'phase'
            elif any(e in msg for e in ['📡', '🗺️', '📦', '🎯', '⚡']):
                tag = 'info'

            if tag:
                self.log_text.insert(tk.END, f"{msg}\n", tag)
            else:
                self.log_text.insert(tk.END, f"{msg}\n")

            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

        self.root.after(0, _log)
        log_audit(msg)

    def _prompt_for_token(self, platform: str) -> str:
        """Thread-safe token prompt."""
        self.log_message(f"ACTION REQUIRED: Please provide a token for {platform.title()}")
        result = [None]
        event = threading.Event()

        def _ask():
            try:
                token = simpledialog.askstring(
                    f"{platform.title()} Token Required",
                    f"Enter your Personal Access Token for {platform.title()}:",
                    parent=self.root, show='*'
                )
                result[0] = token
            except Exception:
                result[0] = None
            finally:
                event.set()

        self.root.after(0, _ask)
        event.wait()
        return result[0] or ""

    # ═══════════════ DOWNLOAD ═══════════════

    def start_download(self):
        url_input = self.url_entry.get().strip()
        folder = self.out_folder.get().strip()
        if not url_input or url_input == 'https://' or not folder:
            messagebox.showerror("Error", "URL and Output Directory are required.")
            return

        export_config = {
            'export_zip': self.export_zip_var.get(),
            'init_git': self.init_git_var.get()
        }
        self.config_manager.set_value('export', export_config)

        self.cancel_event = threading.Event()
        self.download_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start(12)
        self.download_start_time = time.time()
        self._update_timer()

        self.status_label.config(text="Downloading...", fg=COLORS['accent_blue'])
        self.header_status.config(text="● Downloading", fg=COLORS['accent_orange'])

        def run_async():
            try:
                if os.path.isfile(url_input):
                    self.log_message(f"📋 Batch Mode: {url_input}")
                    with open(url_input, 'r', encoding='utf-8') as f:
                        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    if not urls:
                        self.log_message("❌ Batch file is empty.")
                        return
                    processor = BatchProcessor(
                        urls=urls, base_output_dir=Path(folder),
                        log_callback=self.log_message,
                        token_callback=self._prompt_for_token,
                        cancel_event=self.cancel_event
                    )
                    asyncio.run(processor.run())
                    if not self.cancel_event.is_set():
                        self.log_message(f"✅ Batch complete! {len(urls)} URLs processed.")
                        self.root.after(0, lambda: messagebox.showinfo("Success", f"Batch done! {len(urls)} URLs."))
                else:
                    self.log_message(f"🚀 Starting download: {url_input}")
                    file_tree = asyncio.run(run_intelligent_capture(
                        url=url_input, output_dir=folder,
                        log_callback=self.log_message,
                        token_callback=self._prompt_for_token,
                        cancel_event=self.cancel_event
                    ))
                    if not self.cancel_event.is_set():
                        elapsed = time.time() - self.download_start_time
                        self.log_message(f"✅ Download complete! {len(file_tree)} files in {elapsed:.1f}s")
                        self.root.after(0, lambda: self.preview_btn.config(state=tk.NORMAL))
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Success", f"Download finished!\n{len(file_tree)} files saved.\n\nCheck _source_maps/ for original code."))

            except PlaywrightError as e:
                if "Executable doesn't exist" in str(e):
                    self.log_message("❌ Playwright browsers not found.")
                    if messagebox.askyesno("Install Required", "Install Playwright browsers now?"):
                        self.root.after(0, self._run_playwright_install)
                else:
                    import traceback
                    self.log_message(f"❌ Playwright error: {e}\n{traceback.format_exc()}")
            except Exception as e:
                if not (self.cancel_event and self.cancel_event.is_set()):
                    import traceback
                    self.log_message(f"❌ Error: {e}\n{traceback.format_exc()}")
                    messagebox.showerror("Error", str(e))
            finally:
                self.root.after(0, self._reset_ui)

        threading.Thread(target=run_async, daemon=True).start()

    def stop_download(self):
        if self.cancel_event:
            self.log_message("⏹️ Stopping download...")
            self.cancel_event.set()
            self.stop_btn.config(state=tk.DISABLED)
            self.header_status.config(text="● Stopping", fg=COLORS['accent_red'])

    def preview_site(self):
        folder = self.out_folder.get().strip()
        if not folder:
            messagebox.showerror("Error", "No output directory set.")
            return
        if self.preview_server and self.preview_server.is_running:
            self.preview_server.stop()
        try:
            self.preview_server = PreviewServer(directory=folder, log_callback=self.log_message, spa_mode=True)
            url = self.preview_server.start()
            self.preview_server.open_browser()
            self.log_message(f"🌐 Preview: {url}")
            self.status_label.config(text=f"Preview running: {url}", fg=COLORS['accent_green'])
        except Exception as e:
            self.log_message(f"❌ Preview error: {e}")

    # ═══════════════ HELPERS ═══════════════

    def _reset_ui(self):
        self.download_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress.stop()
        self.download_start_time = None
        self.status_label.config(text="Ready", fg=COLORS['text_secondary'])
        self.header_status.config(text="● Ready", fg=COLORS['accent_green'])

    def _update_timer(self):
        if self.download_start_time:
            elapsed = time.time() - self.download_start_time
            mins, secs = divmod(int(elapsed), 60)
            self.timer_label.config(text=f"⏱ {mins:02d}:{secs:02d}")
            self.root.after(1000, self._update_timer)
        else:
            self.timer_label.config(text="")

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _open_output_folder(self):
        folder = self.out_folder.get().strip()
        if folder and os.path.isdir(folder):
            os.startfile(folder)
        else:
            messagebox.showwarning("Warning", "Output folder does not exist yet.")

    def _show_about(self):
        messagebox.showinfo("About WebGrabber",
                            "WebGrabber v2.0\n"
                            "Deep Source Recovery Engine\n\n"
                            "Features:\n"
                            "• Source Map Brute-force Scanner\n"
                            "• Webpack Bundle Debundler\n"
                            "• Next.js Deep Reconnaissance\n"
                            "• Git Repository Discovery\n"
                            "• Multi-page Deep Crawl\n"
                            "• API Interception\n"
                            "• Stealth Anti-bot Bypass\n\n"
                            "Built by QtusDev")

    def _run_playwright_install(self):
        win = Toplevel(self.root)
        win.title("Installing Playwright Browsers")
        win.geometry("700x400")
        win.configure(bg=COLORS['bg_dark'])
        win.transient(self.root)
        win.grab_set()

        log_area = tk.Text(win, font=FONTS['mono'], bg=COLORS['log_bg'],
                            fg=COLORS['accent_green'], relief='flat', borderwidth=10,
                            state=tk.DISABLED, wrap=tk.WORD)
        log_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        def log_w(msg):
            log_area.config(state=tk.NORMAL)
            log_area.insert(tk.END, msg)
            log_area.see(tk.END)
            log_area.config(state=tk.DISABLED)

        def run():
            self.root.after(0, log_w, "Running 'python -m playwright install'...\n\n")
            try:
                flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                proc = subprocess.Popen(
                    ['python', '-m', 'playwright', 'install'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', creationflags=flags
                )
                for line in iter(proc.stdout.readline, ''):
                    self.root.after(0, log_w, line)
                proc.stdout.close()
                rc = proc.wait()
                if rc == 0:
                    self.root.after(0, lambda: messagebox.showinfo("Done", "Browsers installed!", parent=win))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed (code {rc})", parent=win))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e), parent=win))

        threading.Thread(target=run, daemon=True).start()


class SettingsWindow(Toplevel):
    def __init__(self, parent, config_manager):
        super().__init__(parent)
        self.config_manager = config_manager
        self.title("⚙️ Advanced Settings")
        self.geometry("650x450")
        self.configure(bg=COLORS['bg_dark'])

        tk.Label(self, text="Configuration (JSON)", font=FONTS['label'],
                 bg=COLORS['bg_dark'], fg=COLORS['accent_blue']).pack(anchor='w', padx=12, pady=(12, 4))

        self.text_editor = tk.Text(self, wrap='word', font=FONTS['mono'],
                                    bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                                    insertbackground=COLORS['text_primary'],
                                    relief='flat', borderwidth=10,
                                    selectbackground=COLORS['accent_blue'])
        self.text_editor.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self.text_editor.insert('1.0', json.dumps(self.config_manager.get_config(), indent=4))

        btn_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        btn_frame.pack(pady=(0, 12))
        ttk.Button(btn_frame, text="💾  Save & Close", style='Primary.TButton',
                    command=self._save).pack()

    def _save(self):
        try:
            new_config = json.loads(self.text_editor.get('1.0', 'end'))
            self.config_manager.save_config(new_config)
            self.destroy()
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON format.", parent=self)


if __name__ == '__main__':
    root = tk.Tk()
    app = WebGrabberGUI(root)
    root.mainloop()
