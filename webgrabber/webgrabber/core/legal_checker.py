# webgrabber/webgrabber/core/legal_checker.py

from urllib.robotparser import RobotFileParser
from .audit_logger import log_audit


def check_legal(url, ignore_robots):
    if ignore_robots:
        log_audit("Ignoring robots.txt")
        return True
    rp = RobotFileParser(url + '/robots.txt')
    rp.read()
    if not rp.can_fetch('*', url):
        log_audit("Disallowed by robots.txt")
        consent = input("Proceed? (y/n): ").lower() == 'y'
        log_audit(f"Consent: {consent}")
        return consent
    return True