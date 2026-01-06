"""
YouTube content fetcher using yt-dlp.

Fetches recent videos from YouTube channels, extracts metadata
and transcripts (when available).
"""

import json
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from ..models import ContentItem
from ..config import get_settings


def fetch_channel_videos(
    channel_url: str,
    source_id: int,
    days_back: int | None = None,
) -> list[ContentItem]:
    """
    Fetch recent videos from a YouTube channel.

    Args:
        channel_url: YouTube channel URL (e.g., https://www.youtube.com/@ThePrimeTimeagen)
        source_id: Database source ID for this channel
        days_back: How many days of videos to fetch (default from settings)

    Returns:
        List of ContentItem objects with video metadata
    """
    settings = get_settings()
    if days_back is None:
        days_back = settings.fetch.days_back

    # Calculate date filter
    date_after = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

    # Create temp directory for yt-dlp output
    with tempfile.TemporaryDirectory() as tmpdir:
        # yt-dlp command to fetch video metadata without downloading
        cmd = [
            "yt-dlp",
            "--skip-download",           # Don't download video
            "--write-info-json",         # Write metadata to JSON
            "--write-auto-sub",          # Get auto-generated subtitles
            "--sub-lang", "en",          # English subtitles only
            "--sub-format", "vtt",       # VTT format
            "--dateafter", date_after,   # Only videos after this date
            "--playlist-end", "20",      # Max 20 videos per channel
            "--ignore-errors",           # Continue on errors
            "-o", f"{tmpdir}/%(id)s.%(ext)s",  # Output template
            channel_url,
        ]

        print(f"Running yt-dlp for {channel_url}...")  # Debug

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )

            if result.returncode != 0:
                print(f"yt-dlp error: {result.stderr}")
                # Don't fail completely - we might get partial results

        except subprocess.TimeoutExpired:
            print(f"yt-dlp timed out for {channel_url}")
            return []

        # Parse the JSON files yt-dlp created
        items = []
        tmpdir_path = Path(tmpdir)

        json_files = list(tmpdir_path.glob("*.info.json"))
        print(f"Found {len(json_files)} JSON files")  # Debug

        for json_file in json_files:
            try:
                # Skip playlist metadata files (they have channel ID, not video ID)
                if "[UC" in json_file.name and "Videos" in json_file.name:
                    print(f"  Skipping playlist file: {json_file.name}")
                    continue

                item = _parse_video_json(json_file, source_id, settings)
                if item:
                    items.append(item)
                    print(f"  Parsed: {item.title[:50]}...")
            except Exception as e:
                print(f"Error parsing {json_file.name}: {e}")
                continue

        return items


def _parse_video_json(
    json_path: Path,
    source_id: int,
    settings,
) -> ContentItem | None:
    """Parse a yt-dlp info.json file into a ContentItem."""
    with open(json_path) as f:
        data = json.load(f)

    # Skip non-video content (playlists, etc.)
    if data.get("_type") == "playlist":
        return None

    # Extract video ID for transcript lookup
    video_id = data.get("id")
    if not video_id:
        return None

    # Try to load transcript from .vtt file
    transcript = None
    vtt_path = json_path.parent / f"{video_id}.en.vtt"
    if vtt_path.exists():
        transcript = _parse_vtt_transcript(vtt_path, settings.fetch.max_transcript_chars)

    # Parse upload date
    upload_date = None
    if data.get("upload_date"):
        try:
            upload_date = datetime.strptime(data["upload_date"], "%Y%m%d")
        except ValueError:
            pass

    # Build the content item
    return ContentItem(
        source_id=source_id,
        title=data.get("title", "Unknown Title"),
        url=data.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}",
        description=data.get("description", "")[:2000],  # Truncate long descriptions
        transcript=transcript,
        published_date=upload_date,
        duration_minutes=int(data.get("duration", 0) // 60) if data.get("duration") else None,
    )


def _parse_vtt_transcript(vtt_path: Path, max_chars: int) -> str:
    """
    Parse a VTT subtitle file into plain text.

    VTT format has timing lines we need to skip:
    00:00:00.000 --> 00:00:02.000
    Hello world

    00:00:02.000 --> 00:00:04.000
    This is a test
    """
    lines = []

    with open(vtt_path) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines, timing lines, and WEBVTT header
            if not line:
                continue
            if line.startswith("WEBVTT"):
                continue
            if "-->" in line:
                continue
            if line.startswith("Kind:") or line.startswith("Language:"):
                continue

            # This is actual transcript text
            lines.append(line)

    # Join and truncate
    full_text = " ".join(lines)

    # Remove duplicate consecutive words (common in auto-captions)
    words = full_text.split()
    cleaned_words = []
    prev_word = None
    for word in words:
        if word != prev_word:
            cleaned_words.append(word)
        prev_word = word

    cleaned_text = " ".join(cleaned_words)

    if len(cleaned_text) > max_chars:
        cleaned_text = cleaned_text[:max_chars] + "..."

    return cleaned_text


def fetch_single_video(video_url: str, source_id: int) -> ContentItem | None:
    """
    Fetch a single video by URL.

    Useful for testing or adding individual videos.
    """
    settings = get_settings()

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-info-json",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--no-warnings",
            "--quiet",
            "-o", f"{tmpdir}/%(id)s.%(ext)s",
            video_url,
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            return None

        # Find the JSON file
        json_files = list(Path(tmpdir).glob("*.info.json"))
        if not json_files:
            return None

        return _parse_video_json(json_files[0], source_id, settings)
