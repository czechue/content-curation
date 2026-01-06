"""
Obsidian writer for digest output.

Writes markdown digests to the Obsidian vault.
"""

from datetime import datetime
from pathlib import Path

from ..config import get_settings


def write_to_obsidian(content: str, filename: str | None = None) -> Path:
    """
    Write digest content to Obsidian vault.

    Args:
        content: Markdown content to write
        filename: Optional filename (defaults to "Curated Digest YYYY-MM-DD.md")

    Returns:
        Path to the written file
    """
    settings = get_settings()

    # Build output path
    reading_list_dir = settings.obsidian.reading_list_path

    # Create directory if it doesn't exist
    reading_list_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    if filename is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"Curated Digest {date_str}.md"

    output_path = reading_list_dir / filename

    # Handle duplicate filenames (add counter)
    counter = 1
    base_name = output_path.stem
    while output_path.exists():
        output_path = reading_list_dir / f"{base_name} ({counter}).md"
        counter += 1

    # Write the file
    output_path.write_text(content)

    # Set permissions (644)
    output_path.chmod(0o644)

    return output_path


def get_digest_path(date: datetime | None = None) -> Path:
    """
    Get the expected path for a digest file.

    Args:
        date: Date for the digest (defaults to today)

    Returns:
        Path where the digest would be written
    """
    settings = get_settings()

    if date is None:
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")
    filename = f"Curated Digest {date_str}.md"

    return settings.obsidian.reading_list_path / filename
