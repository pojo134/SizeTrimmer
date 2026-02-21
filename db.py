import os
import sqlite3
from datetime import datetime

DATA_DIR = os.environ.get("DATA_DIR", ".")
DB_FILE = os.path.join(DATA_DIR, "sizetrimmer.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            file_name TEXT NOT NULL,
            media_type TEXT NOT NULL,
            original_size INTEGER,
            new_size INTEGER,
            status TEXT NOT NULL,
            error_msg TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_conversion(file_name, media_type, original_size, new_size, status, error_msg=""):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversions (timestamp, file_name, media_type, original_size, new_size, status, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), file_name, media_type, original_size, new_size, status, error_msg))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database error: {e}")

def get_history(limit=50):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM conversions ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception:
        return []

def get_stats():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(original_size) as total_orig, SUM(new_size) as total_new FROM conversions WHERE status='success'")
        row = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM conversions WHERE status='success'")
        success_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversions WHERE status='error'")
        error_count = cursor.fetchone()[0]
        
        conn.close()
        
        total_orig = row[0] or 0
        total_new = row[1] or 0
        space_saved = total_orig - total_new
        
        return {
            "space_saved_bytes": space_saved,
            "success_count": success_count,
            "error_count": error_count
        }
    except Exception:
        return {
            "space_saved_bytes": 0,
            "success_count": 0,
            "error_count": 0
        }
