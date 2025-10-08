# webgrabber/webgrabber/core/audit_logger.py

import logging
import datetime

logging.basicConfig(filename='audit.log', level=logging.INFO, format='%(asctime)s - %(message)s')


def log_audit(message):
    logging.info(message)