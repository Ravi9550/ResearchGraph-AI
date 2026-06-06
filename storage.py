"""SQLite storage for runs, jobs, and local memory fallback."""

from __future__ import annotations

import json
import os
import hashlib
import hmac
import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DATABASE_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_title(text: str, max_words: int = 7) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    cleaned = re.sub(r"^(research|analyze|analyse|explain|write|create|compare)\s+", "", cleaned, flags=re.IGNORECASE)
    if not cleaned:
        return "Untitled research"
    title = " ".join(cleaned.split()[:max_words]).strip(" .,:;!?-")
    return title[:48] or "Untitled research"


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    expected = _hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(expected, password_hash)


def init_db(db_path: Path = DATABASE_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL,
                overall_score INTEGER,
                verifier_verdict TEXT,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result_json TEXT,
                error TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                topic TEXT NOT NULL,
                text TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        _ensure_column(conn, "research_runs", "user_id", "INTEGER")
        _ensure_column(conn, "research_runs", "title", "TEXT")
        _ensure_column(conn, "memory_chunks", "user_id", "INTEGER")
        conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def create_user(username: str, password: str, db_path: Path = DATABASE_PATH) -> int:
    init_db(db_path)
    username = username.strip().lower()
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    with sqlite3.connect(db_path) as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, _hash_password(password), utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username already exists.") from exc
        conn.commit()
        return int(cursor.lastrowid)


def authenticate_user(username: str, password: str, db_path: Path = DATABASE_PATH) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    username = username.strip().lower()
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row or not _verify_password(password, row[2]):
        return None
    return {"id": row[0], "username": row[1]}


def save_run(topic: str, payload: Dict[str, Any], db_path: Path = DATABASE_PATH, user_id: int | None = None) -> int:
    init_db(db_path)
    score = payload.get("scores", {}).get("overall_score")
    verdict = payload.get("verifier", {}).get("verdict", "unknown")
    title = payload.get("history_title") or make_run_title(topic)
    if user_id is not None:
        payload = dict(payload)
        payload["user_id"] = user_id
    payload["history_title"] = title
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO research_runs(user_id, title, topic, created_at, overall_score, verifier_verdict, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, topic, utc_now(), score, verdict, json.dumps(payload)),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_runs(limit: int = 20, db_path: Path = DATABASE_PATH, user_id: int | None = None) -> List[Dict[str, Any]]:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        if user_id is None:
            rows = conn.execute(
                """
                SELECT id, title, topic, created_at, overall_score, verifier_verdict
                FROM research_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, title, topic, created_at, overall_score, verifier_verdict
                FROM research_runs
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
    return [
        {
            "id": row[0],
            "title": row[1] or make_run_title(row[2]),
            "topic": row[2],
            "created_at": row[3],
            "overall_score": row[4],
            "verifier_verdict": row[5],
        }
        for row in rows
    ]


def get_run(run_id: int, db_path: Path = DATABASE_PATH, user_id: int | None = None) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        if user_id is None:
            row = conn.execute("SELECT payload_json FROM research_runs WHERE id = ?", (run_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT payload_json FROM research_runs WHERE id = ? AND user_id = ?",
                (run_id, user_id),
            ).fetchone()
    return json.loads(row[0]) if row else None


def delete_run(run_id: int, db_path: Path = DATABASE_PATH, user_id: int | None = None) -> bool:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        if user_id is None:
            cursor = conn.execute("DELETE FROM research_runs WHERE id = ?", (run_id,))
        else:
            cursor = conn.execute("DELETE FROM research_runs WHERE id = ? AND user_id = ?", (run_id, user_id))
        conn.commit()
        return cursor.rowcount > 0


def create_job(topic: str, db_path: Path = DATABASE_PATH) -> int:
    init_db(db_path)
    now = utc_now()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO research_jobs(topic, status, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (topic, "queued", now, now),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_job(job_id: int, status: str, result: Dict[str, Any] | None = None, error: str | None = None) -> None:
    init_db()
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            UPDATE research_jobs
            SET status = ?, updated_at = ?, result_json = ?, error = ?
            WHERE id = ?
            """,
            (status, utc_now(), json.dumps(result) if result is not None else None, error, job_id),
        )
        conn.commit()


def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    init_db()
    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute(
            "SELECT id, topic, status, created_at, updated_at, result_json, error FROM research_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "topic": row[1],
        "status": row[2],
        "created_at": row[3],
        "updated_at": row[4],
        "result": json.loads(row[5]) if row[5] else None,
        "error": row[6],
    }


def save_memory_chunk(topic: str, text: str, metadata: Dict[str, Any], user_id: int | None = None) -> int:
    init_db()
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO memory_chunks(user_id, topic, text, metadata_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, topic, text, json.dumps(metadata), utc_now()),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_memory_chunks(limit: int = 500, user_id: int | None = None) -> List[Dict[str, Any]]:
    init_db()
    with sqlite3.connect(DATABASE_PATH) as conn:
        if user_id is None:
            rows = conn.execute(
                "SELECT id, user_id, topic, text, metadata_json, created_at FROM memory_chunks ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, user_id, topic, text, metadata_json, created_at
                FROM memory_chunks
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
    return [
        {
            "id": row[0],
            "user_id": row[1],
            "topic": row[2],
            "text": row[3],
            "metadata": json.loads(row[4]),
            "created_at": row[5],
        }
        for row in rows
    ]
