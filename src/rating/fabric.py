"""
Fabric integration for content rating.

Calls the Fabric CLI to rate content using the rate_content pattern.
"""

import subprocess
import re
from ..models import ContentItem, RatingResult, Rating
from ..config import get_settings


def rate_content_item(item: ContentItem) -> RatingResult:
    """
    Rate a content item using Fabric's rate_content pattern.

    Args:
        item: The content item to rate

    Returns:
        RatingResult with rating (S/A/B/C/D) and reasoning

    Raises:
        ValueError: If rating cannot be parsed from Fabric output
        subprocess.TimeoutExpired: If Fabric takes too long
    """
    settings = get_settings()

    # Build input text: title + description + transcript (truncated)
    input_parts = [f"Title: {item.title}"]

    if item.description:
        input_parts.append(f"Description: {item.description[:500]}")

    if item.transcript:
        input_parts.append(f"Transcript: {item.transcript}")

    input_text = "\n\n".join(input_parts)

    # Call Fabric CLI
    cmd = [
        "fabric",
        "--pattern", settings.fabric.pattern,
        "--model", settings.fabric.model,
    ]

    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=60,  # 1 minute timeout
        )

        if result.returncode != 0:
            raise ValueError(f"Fabric error: {result.stderr}")

        output = result.stdout
        return parse_rating_output(output)

    except subprocess.TimeoutExpired:
        raise ValueError("Fabric rating timed out")


def parse_rating_output(output: str) -> RatingResult:
    """
    Parse Fabric rate_content output to extract rating and reasoning.

    Fabric outputs in format:
    RATING:

    B Tier: (Consume Original When Time Allows)

    Explanation:
    - ...
    - ...
    """
    # Extract the rating letter (S, A, B, C, or D)
    rating_match = re.search(r"([SABCD])\s+Tier:", output)

    if not rating_match:
        # Try alternate format
        rating_match = re.search(r"RATING:\s*([SABCD])", output)

    if not rating_match:
        raise ValueError(f"Could not parse rating from output: {output[:200]}...")

    rating_letter = rating_match.group(1)

    # Extract explanation/reasoning
    explanation_match = re.search(
        r"Explanation:\s*(.*?)(?:CONTENT SCORE:|$)",
        output,
        re.DOTALL
    )

    if explanation_match:
        reasoning = explanation_match.group(1).strip()
        # Clean up bullet points
        reasoning = re.sub(r"^- ", "", reasoning, flags=re.MULTILINE)
        reasoning = reasoning.replace("\n- ", " ")
    else:
        # Fallback: use the tier description
        tier_match = re.search(r"[SABCD] Tier:\s*\(([^)]+)\)", output)
        reasoning = tier_match.group(1) if tier_match else "No explanation provided"

    return RatingResult(
        rating=Rating(rating_letter),
        reasoning=reasoning[:500],  # Truncate to reasonable length
    )


def rate_batch(items: list[ContentItem], delay_seconds: float = 2.0) -> list[tuple[ContentItem, RatingResult | Exception]]:
    """
    Rate multiple items with delay between calls.

    Args:
        items: List of content items to rate
        delay_seconds: Delay between API calls (for rate limiting)

    Returns:
        List of (item, result_or_exception) tuples
    """
    import time

    results = []
    for i, item in enumerate(items):
        try:
            result = rate_content_item(item)
            results.append((item, result))
        except Exception as e:
            results.append((item, e))

        # Delay between calls (except for last item)
        if i < len(items) - 1:
            time.sleep(delay_seconds)

    return results
