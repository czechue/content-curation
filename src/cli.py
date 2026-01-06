"""
Command-line interface for Content Curation System.

Usage:
    python -m src.cli fetch ThePrimeagen
    python -m src.cli fetch --all
    python -m src.cli rate --limit 10
    python -m src.cli digest
    python -m src.cli stats
"""

import click
from datetime import datetime

from . import db
from .models import SourceType


@click.group()
def cli():
    """Content Curation System CLI."""
    pass


@cli.command()
@click.argument("source_name", required=False)
@click.option("--all", "fetch_all", is_flag=True, help="Fetch from all enabled sources")
@click.option("--type", "source_type", type=click.Choice(["youtube", "podcast", "rss"]),
              help="Fetch only sources of this type")
def fetch(source_name: str | None, fetch_all: bool, source_type: str | None):
    """
    Fetch content from sources.

    Examples:
        python -m src.cli fetch ThePrimeagen
        python -m src.cli fetch --all
        python -m src.cli fetch --type youtube
    """
    sources = db.get_sources(enabled_only=True)

    if source_name:
        # Fetch single source by name
        source = db.get_source_by_name(source_name)
        if not source:
            click.echo(f"Source '{source_name}' not found", err=True)
            return
        sources = [source]

    elif source_type:
        # Filter by type
        sources = [s for s in sources if s.type.value == source_type]

    elif not fetch_all:
        click.echo("Specify a source name, --all, or --type", err=True)
        return

    if not sources:
        click.echo("No sources to fetch")
        return

    click.echo(f"Fetching from {len(sources)} source(s)...\n")

    total_new = 0
    total_skipped = 0

    for source in sources:
        click.echo(f"[{source.type.value}] {source.name}")

        if source.type == SourceType.YOUTUBE:
            from .fetchers.youtube import fetch_channel_videos
            items = fetch_channel_videos(source.url, source.id)

        elif source.type == SourceType.PODCAST:
            # TODO: Implement podcast fetcher
            click.echo("  -> Podcast fetcher not implemented yet")
            continue

        elif source.type == SourceType.RSS:
            # TODO: Implement RSS fetcher
            click.echo("  -> RSS fetcher not implemented yet")
            continue

        new_count = 0
        skip_count = 0

        for item in items:
            if db.content_exists(item.url):
                skip_count += 1
                continue

            try:
                db.insert_content_item(item)
                new_count += 1
            except Exception as e:
                click.echo(f"  -> Error inserting: {e}")

        # Update last fetch timestamp
        db.update_source_last_fetch(source.id)

        # Log the fetch
        db.log_fetch(source.id, new_count, success=True)

        click.echo(f"  -> {new_count} new, {skip_count} skipped (duplicates)")
        total_new += new_count
        total_skipped += skip_count

    click.echo(f"\nTotal: {total_new} new items, {total_skipped} duplicates skipped")


@cli.command()
@click.option("--limit", default=10, help="Number of items to rate")
def rate(limit: int):
    """
    Rate unrated content using Fabric.

    Examples:
        python -m src.cli rate
        python -m src.cli rate --limit 5
    """
    from .rating.fabric import rate_content_item

    items = db.get_unrated_items(limit=limit)

    if not items:
        click.echo("No unrated items to process")
        return

    click.echo(f"Rating {len(items)} item(s)...\n")

    for item in items:
        click.echo(f"Rating: {item.title[:60]}...")

        try:
            result = rate_content_item(item)
            db.update_rating(item.id, result.rating, result.reasoning)
            click.echo(f"  -> {result.rating.value}: {result.reasoning[:80]}...")
        except Exception as e:
            click.echo(f"  -> Error: {e}")


@cli.command()
def digest():
    """
    Generate weekly digest for Obsidian.

    Creates a markdown file with A/S-tier content.
    """
    from .digest.generator import generate_digest
    from .digest.writer import write_to_obsidian

    items = db.get_unpublished_top_tier(days=7)

    if not items:
        click.echo("No A/S-tier content to publish")
        return

    click.echo(f"Generating digest with {len(items)} item(s)...")

    # Generate markdown
    markdown = generate_digest(items)

    # Write to Obsidian
    output_path = write_to_obsidian(markdown)
    click.echo(f"Digest written to: {output_path}")

    # Record in database
    s_count = sum(1 for i in items if i.rating.value == "S")
    a_count = sum(1 for i in items if i.rating.value == "A")

    from .models import Digest
    digest_record = Digest(
        week_start_date=datetime.now(),
        week_end_date=datetime.now(),
        item_count=len(items),
        s_tier_count=s_count,
        a_tier_count=a_count,
        obsidian_path=str(output_path),
    )
    digest_id = db.create_digest(digest_record)

    # Mark items as published
    item_ids = [i.id for i in items]
    db.mark_items_published(item_ids, digest_id)

    click.echo(f"Published {len(items)} items ({s_count} S-tier, {a_count} A-tier)")


@cli.command()
def stats():
    """Show database statistics."""
    statistics = db.get_stats()

    click.echo("Content Curation Statistics")
    click.echo("=" * 40)
    click.echo(f"Total items:           {statistics['total_items']}")
    click.echo(f"Rated items:           {statistics['rated_items']}")
    click.echo(f"Unpublished A/S-tier:  {statistics['unpublished_top_tier']}")

    if statistics['by_rating']:
        click.echo("\nBy rating:")
        for rating, count in sorted(statistics['by_rating'].items()):
            click.echo(f"  {rating}: {count}")


@cli.command()
def sources():
    """List all configured sources."""
    all_sources = db.get_sources(enabled_only=False)

    click.echo("Configured Sources")
    click.echo("=" * 40)

    for source in all_sources:
        status = "enabled" if source.enabled else "disabled"
        last_fetch = source.last_fetch_at.strftime("%Y-%m-%d %H:%M") if source.last_fetch_at else "never"
        click.echo(f"[{source.type.value:8}] {source.name}")
        click.echo(f"           URL: {source.url[:50]}...")
        click.echo(f"           Status: {status}, Last fetch: {last_fetch}")
        click.echo()


if __name__ == "__main__":
    cli()
