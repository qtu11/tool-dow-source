import click
import asyncio
import os
from pathlib import Path

# Thay đổi import
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
# === TÙY CHỌN SESSION MỚI ===
@click.option('--import-cookies', type=click.Choice(['chrome', 'firefox', 'edge', 'brave']), help="Tự động import cookie từ trình duyệt được chỉ định.")
@click.option('--interactive-login', is_flag=True, help="Mở trình duyệt để đăng nhập thủ công.")
# Tùy chọn cũ vẫn giữ lại để tương thích
@click.option('--proxy', help="Proxy URL (ví dụ: http://user:pass@host:port).")
def capture(url, out, import_cookies, interactive_login, proxy):
    """
    Tự động phát hiện nền tảng và tải source code bằng chiến lược tối ưu nhất.
    """
    click.echo(f"🚀 Bắt đầu quá trình tải thông minh cho: {url}")
    
    session_manager = SessionManager(url)
    
    # Xử lý các tùy chọn session trước khi chạy
    if import_cookies:
        click.echo(f"🔍 Đang thử import cookie từ {import_cookies}...")
        if session_manager.load_cookies_from_browser(import_cookies):
            click.secho("✅ Import cookie thành công!", fg='green')
        else:
            click.secho("⚠️ Không tìm thấy cookie phù hợp.", fg='yellow')

    # Chạy interactive login nếu được yêu cầu
    if interactive_login:
        click.echo("🔄 Vui lòng làm theo hướng dẫn để đăng nhập thủ công...")
        # Vì CLI chạy đồng bộ, chúng ta có thể gọi trực tiếp hàm async
        asyncio.run(session_manager.interactive_login())

    def cli_file_callback(file_path):
        click.echo(f"   -> Đã tải: {file_path}")
        
    def cli_token_callback(prompt_type, message):
        if prompt_type == "login_prompt":
            return click.confirm(message, default=False)
        return click.prompt(message, hide_input=True)

    try:
        # === THAY ĐỔI LỆNH GỌI CHÍNH ===
        asyncio.run(
            run_intelligent_capture(
                url,
                out,
                file_callback=cli_file_callback,
                token_callback=cli_token_callback
            )
        )
        click.secho(f"\n✅ Hoàn tất! Source code đã được lưu tại: {out}", fg='green')
    except Exception as e:
        click.secho(f"\n❌ Lỗi nghiêm trọng: {e}", fg='red')
        import traceback
        click.echo(traceback.format_exc())

if __name__ == '__main__':
    main()
