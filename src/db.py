"""
Database operations for Content Curation System.

All SQLite interactions go through this module.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from .models import Source, ContentItem, SourceType, Rating, Digest
from .config import get_settings


def get_db_path() -> Path:
    """Get the database path from settings."""
    settings = get_settings()
    # Resolve relative to the project root (where we run from)
    return Path(settings.database.path).resolve()


@contextmanager
def get_connection():
    """
    Context manager for database connections.

    Usage:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM sources")
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ============================================
# SOURCE OPERATIONS
# ============================================

def get_sources(enabled_only: bool = True) -> list[Source]:
    """Get all content sources."""
    with get_connection() as conn:
        if enabled_only:
            cursor = conn.execute(
                "SELECT * FROM sources WHERE enabled = 1"
            )
        else:
            cursor = conn.execute("SELECT * FROM sources")

        return [
            Source(
                id=row["id"],
                name=row["name"],
                type=SourceType(row["type"]),
                url=row["url"],
                enabled=bool(row["enabled"]),
                last_fetch_at=datetime.fromisoformat(row["last_fetch_at"])
                if row["last_fetch_at"] else None,
            )
            for row in cursor.fetchall()
        ]


def get_source_by_name(name: str) -> Source | None:
    """Get a source by name."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM sources WHERE name = ?", (name,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return Source(
            id=row["id"],
            name=row["name"],
            type=SourceType(row["type"]),
            url=row["url"],
            enabled=bool(row["enabled"]),
            last_fetch_at=datetime.fromisoformat(row["last_fetch_at"])
            if row["last_fetch_at"] else None,
        )


def update_source_last_fetch(source_id: int) -> None:
    """Update the last_fetch_at timestamp for a source."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE sources SET last_fetch_at = ? WHERE id = ?",
            (datetime.now().isoformat(), source_id),
        )


# ============================================
# CONTENT ITEM OPERATIONS
# ============================================

def content_exists(url: str) -> bool:
    """Check if a content item already exists (deduplication)."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM content_items WHERE url = ?", (url,)
        )
        return cursor.fetchone() is not None


def insert_content_item(item: ContentItem) -> int:
    """
    Insert a new content item.

    Returns the new item's ID.
    Raises sqlite3.IntegrityError if URL already exists.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO content_items (
                source_id, title, url, description, transcript,
                published_date, duration_minutes, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.source_id,
                item.title,
                item.url,
                item.description,
                item.transcript,
                item.published_date.isoformat() if item.published_date else None,
                item.duration_minutes,
                datetime.now().isoformat(),
            ),
        )
        return cursor.lastrowid


def get_unrated_items(limit: int = 10) -> list[ContentItem]:
    """Get content items that haven't been rated yet."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM content_items
            WHERE rating IS NULL
            ORDER BY fetched_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [_row_to_content_item(row) for row in cursor.fetchall()]


def update_rating(item_id: int, rating: Rating, reasoning: str) -> None:
    """Update the rating for a content item."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE content_items
            SET rating = ?, rating_reasoning = ?, rated_at = ?
            WHERE id = ?
            """,
            (rating.value, reasoning, datetime.now().isoformat(), item_id),
        )


def get_unpublished_top_tier(days: int = 7) -> list[ContentItem]:
    """
    Get A/S-tier items that haven't been published to Obsidian yet.

    Used for digest generation.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM content_items
            WHERE rating IN ('A', 'S')
            AND published_to_obsidian = 0
            AND fetched_at >= datetime('now', ?)
            ORDER BY
                CASE rating WHEN 'S' THEN 0 ELSE 1 END,
                published_date DESC
            """,
            (f"-{days} days",),
        )
        return [_row_to_content_item(row) for row in cursor.fetchall()]


def mark_items_published(item_ids: list[int], digest_id: int) -> None:
    """Mark items as published in a digest."""
    with get_connection() as conn:
        placeholders = ",".join("?" * len(item_ids))
        conn.execute(
            f"""
            UPDATE content_items
            SET published_to_obsidian = 1, digest_id = ?
            WHERE id IN ({placeholders})
            """,
            [digest_id] + item_ids,
        )


def _row_to_content_item(row: sqlite3.Row) -> ContentItem:
    """Convert a database row to a ContentItem model."""
    return ContentItem(
        id=row["id"],
        source_id=row["source_id"],
        title=row["title"],
        url=row["url"],
        description=row["description"],
        transcript=row["transcript"],
        published_date=datetime.fromisoformat(row["published_date"])
        if row["published_date"] else None,
        duration_minutes=row["duration_minutes"],
        rating=Rating(row["rating"]) if row["rating"] else None,
        rating_reasoning=row["rating_reasoning"],
        rated_at=datetime.fromisoformat(row["rated_at"])
        if row["rated_at"] else None,
        published_to_obsidian=bool(row["published_to_obsidian"]),
        digest_id=row["digest_id"],
        fetched_at=datetime.fromisoformat(row["fetched_at"])
        if row["fetched_at"] else None,
    )


# ============================================
# DIGEST OPERATIONS
# ============================================

def create_digest(digest: Digest) -> int:
    """Create a new digest record."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO digests (
                week_start_date, week_end_date, item_count,
                s_tier_count, a_tier_count, obsidian_path
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                digest.week_start_date.isoformat(),
                digest.week_end_date.isoformat(),
                digest.item_count,
                digest.s_tier_count,
                digest.a_tier_count,
                digest.obsidian_path,
            ),
        )
        return cursor.lastrowid


# ============================================
# FETCH LOG OPERATIONS
# ============================================

def log_fetch(
    source_id: int,
    items_fetched: int,
    success: bool,
    error_message: str | None = None,
) -> None:
    """Log a fetch attempt."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO fetch_logs (
                source_id, items_fetched, success, error_message,
                started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                items_fetched,
                1 if success else 0,
                error_message,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )


# ============================================
# STATISTICS
# ============================================

def get_stats() -> dict:
    """Get database statistics."""
    with get_connection() as conn:
        stats = {}

        # Total items
        cursor = conn.execute("SELECT COUNT(*) FROM content_items")
        stats["total_items"] = cursor.fetchone()[0]

        # Rated items
        cursor = conn.execute(
            "SELECT COUNT(*) FROM content_items WHERE rating IS NOT NULL"
        )
        stats["rated_items"] = cursor.fetchone()[0]

        # By rating
        cursor = conn.execute(
            """
            SELECT rating, COUNT(*) as count
            FROM content_items
            WHERE rating IS NOT NULL
            GROUP BY rating
            """
        )
        stats["by_rating"] = {row["rating"]: row["count"] for row in cursor.fetchall()}

        # Unpublished A/S tier
        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM content_items
            WHERE rating IN ('A', 'S') AND published_to_obsidian = 0
            """
        )
        stats["unpublished_top_tier"] = cursor.fetchone()[0]

        return stats
