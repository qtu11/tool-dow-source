import click
import asyncio
from pathlib import Path

from ..core.orchestrator import run_intelligent_capture
from ..core.session_manager import SessionManager
from .validators import validate_url, validate_out


@click.group()
def main():
    """WebGrabber Intelligent Downloader v2.0"""
    pass


@main.command()
@click.argument('url', callback=validate_url)
@click.option('--out', required=True, callback=validate_out, help="Thư mục lưu trữ output.")
@click.option('--import-cookies', type=click.Choice(['chrome', 'firefox', 'edge', 'brave']),
              help="Tự động import cookie từ trình duyệt được chỉ định.")
@click.option('--interactive-login', is_flag=True, help="Mở trình duyệt để đăng nhập thủ công.")
@click.option('--proxy', help="Proxy URL (ví dụ: http://user:pass@host:port).")
def capture(url, out, import_cookies, interactive_login, proxy):
    """
    Tự động phát hiện nền tảng và tải source code bằng chiến lược tối ưu nhất.
    """
    click.echo(f"🚀 Bắt đầu quá trình tải thông minh cho: {url}")

    def cli_log_callback(msg):
        click.echo(f"   {msg}")

    def cli_token_callback(platform):
        return click.prompt(
            f"Vui lòng nhập Personal Access Token cho {platform.title()}",
            hide_input=True
        )

    session_manager = SessionManager(url, cli_log_callback)

    # Xử lý session options trước khi chạy
    if import_cookies:
        click.echo(f"🔍 Đang thử import cookie từ {import_cookies}...")
        if session_manager.load_cookies_from_browser(import_cookies):
            click.secho("✅ Import cookie thành công!", fg='green')
        else:
            click.secho("⚠️ Không tìm thấy cookie phù hợp.", fg='yellow')

    if interactive_login:
        click.echo("🔄 Vui lòng làm theo hướng dẫn để đăng nhập thủ công...")
        asyncio.run(session_manager.interactive_login())

    try:
        asyncio.run(
            run_intelligent_capture(
                url=url,
                output_dir=out,
                log_callback=cli_log_callback,
                token_callback=cli_token_callback,
            )
        )
        click.secho(f"\n✅ Hoàn tất! Source code đã được lưu tại: {out}", fg='green')
    except Exception as e:
        click.secho(f"\n❌ Lỗi nghiêm trọng: {e}", fg='red')
        import traceback
        click.echo(traceback.format_exc())


@main.command()
def ui():
    """Mở giao diện đồ hoạ (GUI) của WebGrabber."""
    import tkinter as tk
    from ..core.gui import WebGrabberGUI
    root = tk.Tk()
    app = WebGrabberGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
