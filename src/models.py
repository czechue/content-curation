"""
Data models for Content Curation System.

Uses Pydantic for validation and serialization.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, HttpUrl


class SourceType(str, Enum):
    """Type of content source."""
    YOUTUBE = "youtube"
    PODCAST = "podcast"
    RSS = "rss"


class Rating(str, Enum):
    """Content rating from Fabric."""
    S = "S"  # Must consume - exceptional content
    A = "A"  # High value - definitely worth time
    B = "B"  # Good - consume if time permits
    C = "C"  # Average - skip unless specifically relevant
    D = "D"  # Low value - skip


class Source(BaseModel):
    """A content source we monitor."""
    id: int | None = None
    name: str
    type: SourceType
    url: str
    enabled: bool = True
    last_fetch_at: datetime | None = None


class ContentItem(BaseModel):
    """
    A piece of content (video, episode, post).

    This is the main entity - one per video/episode/post.
    """
    id: int | None = None
    source_id: int

    # Content metadata
    title: str
    url: str
    description: str | None = None
    transcript: str | None = None
    published_date: datetime | None = None
    duration_minutes: int | None = None

    # Rating (filled after Fabric processing)
    rating: Rating | None = None
    rating_reasoning: str | None = None
    rated_at: datetime | None = None

    # Output tracking
    published_to_obsidian: bool = False
    digest_id: int | None = None

    # Timestamps
    fetched_at: datetime | None = None


class RatingResult(BaseModel):
    """Result from Fabric rating."""
    rating: Rating
    reasoning: str


class Digest(BaseModel):
    """A generated weekly digest."""
    id: int | None = None
    week_start_date: datetime
    week_end_date: datetime
    item_count: int
    s_tier_count: int
    a_tier_count: int
    obsidian_path: str | None = None
    created_at: datetime | None = None
