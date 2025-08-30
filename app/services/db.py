import os
import json
import sqlite3
from contextlib import contextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "app.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            original_name TEXT,
            processed_path TEXT,
            md_path TEXT,
            analysis_text TEXT,
            refs_json TEXT,
            created_at TEXT
        )
        """)
        conn.commit()

def save_analysis(uid: str, original_name: str, processed_path: str, md_path: str,
                  analysis_text: str, refs: List[Dict[str, Any]]):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO analyses (id, original_name, processed_path, md_path, analysis_text, refs_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            uid, original_name, processed_path, md_path,
            analysis_text, json.dumps(refs, ensure_ascii=False),
            datetime.utcnow().isoformat()
        ))
        conn.commit()

def list_analyses(limit: int = 50) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, original_name, md_path, created_at
            FROM analyses
            ORDER BY datetime(created_at) DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
    return [
        {"id": r[0], "original_name": r[1] or "-", "md_path": r[2], "created_at": r[3]}
        for r in rows
    ]

def get_analysis(uid: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, original_name, processed_path, md_path, analysis_text, refs_json, created_at
            FROM analyses WHERE id=?
        """, (uid,))
        r = cur.fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "original_name": r[1],
        "processed_path": r[2],
        "md_path": r[3],
        "analysis_text": r[4],
        "refs": json.loads(r[5] or "[]"),
        "created_at": r[6],
    }

def delete_analysis(uid: str) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM analyses WHERE id=?", (uid,))
        conn.commit()
        return cur.rowcount > 0

init_db()
