import sqlite3
import re
from typing import Optional
from config import MOVIES_DB_FILE

def get_db_connection():
    """Returns a SQLite connection with dict-like row access."""
    conn = sqlite3.connect(MOVIES_DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite database and Full-Text Search (FTS5) tables."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Primary movies table without requiring poster images
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER UNIQUE NOT NULL,
            title TEXT NOT NULL,
            year INTEGER DEFAULT 2024,
            file_size INTEGER DEFAULT 0,
            duration INTEGER DEFAULT 0,
            mime_type TEXT DEFAULT 'video/mp4',
            file_name TEXT DEFAULT 'movie.mp4',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Full Text Search (FTS5) virtual table
        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS movies_fts USING fts5(
            title,
            content='movies',
            content_rowid='id'
        );
        """)

        # Triggers to keep FTS table in sync
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS movies_ai AFTER INSERT ON movies BEGIN
            INSERT INTO movies_fts(rowid, title) VALUES (new.id, new.title);
        END;
        """)

        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS movies_ad AFTER DELETE ON movies BEGIN
            INSERT INTO movies_fts(movies_fts, rowid, title) VALUES('delete', old.id, old.title);
        END;
        """)

        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS movies_au AFTER UPDATE ON movies BEGIN
            INSERT INTO movies_fts(movies_fts, rowid, title) VALUES('delete', old.id, old.title);
            INSERT INTO movies_fts(rowid, title) VALUES (new.id, new.title);
        END;
        """)

        conn.commit()

def parse_title_and_year(raw_text: str):
    """Parses clean title and 4-digit release year from caption or filename."""
    if not raw_text:
        return ("סרט ללא שם", 2024)

    text = raw_text.strip()
    year_match = re.search(r'\b(19\d\d|20\d\d)\b', text)
    year = int(year_match.group(1)) if year_match else 2024

    # Remove file extensions, dots, quality tags
    clean = re.sub(r'\.(mp4|mkv|avi|mov|wmv|flv|webm)$', '', text, flags=re.IGNORECASE)
    clean = re.sub(r'[\.\_\-]', ' ', clean)
    clean = re.sub(r'\b(19\d\d|20\d\d|720p|1080p|4k|2160p|hdrip|web-dl|bluray|x264|x265|hevc|aac)\b', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+', ' ', clean).strip()

    title = clean if clean else text
    return (title, year)

def add_or_update_movie(
    message_id: int,
    raw_title: str,
    file_size: int = 0,
    duration: int = 0,
    mime_type: str = "video/mp4",
    file_name: str = "movie.mp4"
) -> int:
    """Inserts or updates a movie record in the database."""
    title, year = parse_title_and_year(raw_title)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO movies (message_id, title, year, file_size, duration, mime_type, file_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(message_id) DO UPDATE SET
            title = excluded.title,
            year = excluded.year,
            file_size = excluded.file_size,
            duration = excluded.duration,
            mime_type = excluded.mime_type,
            file_name = excluded.file_name;
        """, (message_id, title, year, file_size, duration, mime_type, file_name))
        conn.commit()
        return cursor.lastrowid

def add_or_update_movies_batch(movies_list: list) -> int:
    """Inserts or updates a list of movies in a single fast SQLite transaction."""
    if not movies_list:
        return 0

    records = []
    for item in movies_list:
        title, year = parse_title_and_year(item["raw_title"])
        records.append((
            item["message_id"],
            title,
            year,
            item.get("file_size", 0),
            item.get("duration", 0),
            item.get("mime_type", "video/mp4"),
            item.get("file_name", f"movie_{item['message_id']}.mp4")
        ))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
        INSERT INTO movies (message_id, title, year, file_size, duration, mime_type, file_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(message_id) DO UPDATE SET
            title = excluded.title,
            year = excluded.year,
            file_size = excluded.file_size,
            duration = excluded.duration,
            mime_type = excluded.mime_type,
            file_name = excluded.file_name;
        """, records)
        conn.commit()
        return len(records)

def search_movies(query: str):
    """Performs FTS5 search with fallback to LIKE search (unlimited)."""
    query = query.strip()
    if not query:
        return get_all_movies()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        words = query.split()
        fts_query = ' AND '.join(f'"{word}"*' for word in words)

        try:
            cursor.execute("""
                SELECT m.* FROM movies m
                JOIN movies_fts fts ON m.id = fts.rowid
                WHERE movies_fts MATCH ?
                ORDER BY m.year DESC, m.id DESC;
            """, (fts_query,))
            rows = cursor.fetchall()
            if rows:
                return [dict(row) for row in rows]
        except Exception:
            pass

        like_pattern = f"%{query}%"
        cursor.execute("""
            SELECT * FROM movies
            WHERE title LIKE ? OR file_name LIKE ?
            ORDER BY year DESC, id DESC;
        """, (like_pattern, like_pattern))
        return [dict(row) for row in cursor.fetchall()]

def get_movie_by_id(movie_id: int):
    """Retrieves a movie by its primary key ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_movies(limit: Optional[int] = None, offset: int = 0):
    """Retrieves all movies sorted by newest year and ID first (unlimited by default)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if limit is not None:
            cursor.execute("SELECT * FROM movies ORDER BY year DESC, id DESC LIMIT ? OFFSET ?", (limit, offset))
        else:
            cursor.execute("SELECT * FROM movies ORDER BY year DESC, id DESC")
        return [dict(row) for row in cursor.fetchall()]

def get_total_count() -> int:
    """Returns total count of movies in database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM movies")
        return cursor.fetchone()[0]
