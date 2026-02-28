# webgrabber/webgrabber/core/legal_checker.py

from urllib.robotparser import RobotFileParser
from .audit_logger import log_audit


def check_legal(url: str, ignore_robots: bool = False, consent_callback=None) -> bool:
    """
    Kiểm tra robots.txt trước khi crawl.
    
    Args:
        url: URL cần kiểm tra
        ignore_robots: Bỏ qua robots.txt nếu True
        consent_callback: Hàm callback để hỏi consent (GUI/CLI).
                         Nếu None, mặc định cho phép.
    """
    if ignore_robots:
        log_audit("Ignoring robots.txt as requested.")
        return True

    try:
        rp = RobotFileParser(url.rstrip('/') + '/robots.txt')
        rp.read()
        if rp.can_fetch('*', url):
            log_audit("Allowed by robots.txt.")
            return True
    except Exception as e:
        log_audit(f"Could not read robots.txt: {e}. Proceeding anyway.")
        return True

    log_audit("Disallowed by robots.txt.")

    # Dùng callback thay vì input() trực tiếp
    if consent_callback:
        consent = consent_callback(
            "This URL is disallowed by robots.txt. Do you want to proceed anyway?"
        )
        log_audit(f"User consent: {consent}")
        return consent

    # Nếu không có callback → block (an toàn)
    log_audit("No consent callback provided. Blocking access.")
    return False