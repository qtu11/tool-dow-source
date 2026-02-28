# webgrabber/webgrabber/core/history_db.py
import sqlite3
import json
from datetime import datetime
from pathlib import Path

class HistoryDB:
    """
    SQLite Database to log download history, keeping track of tasks, 
    their outcomes (success/fail), timestamp, and basic stats.
    """
    
    DB_NAME = 'webgrabber_history.db'
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / self.DB_NAME
        self._init_db()

    def _init_db(self):
        """Create the schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    files_count INTEGER DEFAULT 0,
                    framework TEXT DEFAULT NULL,
                    error_message TEXT DEFAULT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            conn.commit()

    def record_download(self, url: str, output_dir: str, status: str, files_count: int = 0, 
                        framework: str = None, error_message: str = None, metadata: dict = None):
        """Record a single download operation."""
        meta_str = json.dumps(metadata) if metadata else '{}'
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO downloads (url, output_dir, status, files_count, framework, error_message, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (url, output_dir, status, files_count, framework, error_message, meta_str))
            conn.commit()

    def get_history(self, limit: int = 50):
        """Retrieve recent download events."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM downloads 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
