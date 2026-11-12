"""
Profile Enricher Module
=======================
Extracts emails, engagement rates, and niche keywords from raw Instagram
profile data, producing validated ``EnrichedProfile`` Pydantic models.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Pydantic model
# ------------------------------------------------------------------

class EnrichedProfile(BaseModel):
    """A fully enriched influencer profile ready for scoring and outreach."""

    username: str
    full_name: str = ""
    bio: str = ""
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    profile_url: str = ""
    email: Optional[str] = None
    engagement_rate: float = 0.0
    niche_keywords: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    is_business: bool = False
    is_verified: bool = False
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------
# Enricher
# ------------------------------------------------------------------

class ProfileEnricher:
    """Extracts structured data from raw Instagram profile dictionaries."""

    # Regex to match most common email patterns
    _EMAIL_RE = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    )

    # Common niche / topic keywords to look for in bios and captions
    _COMMON_NICHE_TERMS: list[str] = [
        "skincare", "beauty", "makeup", "wellness", "fitness", "fashion",
        "lifestyle", "travel", "food", "health", "yoga", "self-care",
        "clean beauty", "dermatology", "vegan", "organic", "sustainable",
        "hair care", "nail art", "photography", "tech", "parenting",
        "nutrition", "meditation", "mental health", "blogger", "influencer",
        "content creator", "entrepreneur",
    ]

    # ------------------------------------------------------------------
    # Email extraction
    # ------------------------------------------------------------------
    @classmethod
    def extract_email(cls, bio: str, external_url: str | None = None) -> str | None:
        """Extract the first email address found in *bio* text or *external_url*.

        Checks:
        1. Regex search over the bio string.
        2. ``mailto:`` links in *external_url*.

        Returns:
            The first email found (lowercased), or ``None``.
        """
        # Search bio
        if bio:
            # Handle common anti-scrape obfuscations like user[at]domain[dot]com
            normalized_bio = re.sub(r"\[at\]|\(at\)", "@", bio, flags=re.IGNORECASE)
            normalized_bio = re.sub(r"\[dot\]|\(dot\)", ".", normalized_bio, flags=re.IGNORECASE)
            match = cls._EMAIL_RE.search(normalized_bio)
            if match:
                return match.group(0).lower()

        # Check external_url for mailto: links
        if external_url:
            url_lower = external_url.lower()
            if "mailto:" in url_lower:
                mailto_part = url_lower.split("mailto:")[-1].split("?")[0].strip()
                match = cls._EMAIL_RE.search(mailto_part)
                if match:
                    return match.group(0).lower()

            # Also try a plain regex on the URL (sometimes email is in query params)
            match = cls._EMAIL_RE.search(external_url)
            if match:
                return match.group(0).lower()

        return None

    # ------------------------------------------------------------------
    # Engagement rate
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_engagement_rate(
        likes: int | float,
        comments: int | float,
        followers: int | float,
    ) -> float:
        """Calculate engagement rate as a percentage.

        Formula: ``(likes + comments) / followers * 100``

        Returns:
            Engagement rate rounded to two decimal places.
            Returns ``0.0`` when *followers* is zero.
        """
        if followers <= 0:
            return 0.0
        return round((likes + comments) / followers * 100, 2)

    # ------------------------------------------------------------------
    # Niche keyword extraction
    # ------------------------------------------------------------------
    @classmethod
    def extract_niche_keywords(
        cls,
        bio: str,
        captions: list[str] | None = None,
    ) -> list[str]:
        """Extract niche keywords from a bio and optional list of captions.

        Strategy:
        1. Extract hashtags (``#keyword``).
        2. Match known niche terms against combined text.
        3. Return a deduplicated, sorted list.
        """
        combined_text = (bio or "").lower()
        if captions:
            combined_text += " " + " ".join(c.lower() for c in captions if c)

        keywords: set[str] = set()

        # Pull out hashtags
        hashtags = re.findall(r"#(\w+)", combined_text)
        for tag in hashtags:
            # Only keep tags that look meaningful (length > 2)
            if len(tag) > 2:
                keywords.add(tag)

        # Match known niche terms
        for term in cls._COMMON_NICHE_TERMS:
            if term in combined_text:
                keywords.add(term)

        return sorted(keywords)

    # ------------------------------------------------------------------
    # Full enrichment
    # ------------------------------------------------------------------
    def enrich_profile(self, raw_profile: dict[str, Any]) -> EnrichedProfile:
        """Convert a raw profile dict into a validated :class:`EnrichedProfile`.

        Args:
            raw_profile: Dict containing at minimum ``username``.
                         May contain ``recent_posts`` (list of dicts with
                         ``likes`` and ``comments``) for engagement calculation,
                         and ``captions`` (list of strings) for keyword extraction.

        Returns:
            An :class:`EnrichedProfile` instance.
        """
        bio: str = raw_profile.get("bio", "") or ""
        external_url: str | None = raw_profile.get("external_url") or None
        follower_count: int = int(raw_profile.get("follower_count", 0))

        # Extract email
        email = self.extract_email(bio, external_url)

        # Calculate engagement rate from recent posts if available
        recent_posts: list[dict] = raw_profile.get("recent_posts", [])
        if recent_posts:
            total_likes = sum(int(p.get("likes", 0)) for p in recent_posts)
            total_comments = sum(int(p.get("comments", 0)) for p in recent_posts)
            avg_likes = total_likes / len(recent_posts) if recent_posts else 0
            avg_comments = total_comments / len(recent_posts) if recent_posts else 0
            engagement_rate = self.calculate_engagement_rate(avg_likes, avg_comments, follower_count)
        else:
            # Use raw engagement_rate if already provided
            engagement_rate = float(raw_profile.get("engagement_rate", 0.0))

        # Extract niche keywords
        captions: list[str] = raw_profile.get("captions", [])
        niche_keywords = self.extract_niche_keywords(bio, captions)

        enriched = EnrichedProfile(
            username=raw_profile.get("username", ""),
            full_name=raw_profile.get("full_name", ""),
            bio=bio,
            follower_count=follower_count,
            following_count=int(raw_profile.get("following_count", 0)),
            post_count=int(raw_profile.get("post_count", 0)),
            profile_url=raw_profile.get("profile_url", ""),
            email=email,
            engagement_rate=engagement_rate,
            niche_keywords=niche_keywords,
            location=raw_profile.get("location"),
            is_business=bool(raw_profile.get("is_business", False)),
            is_verified=bool(raw_profile.get("is_verified", False)),
        )

        logger.debug("Enriched profile: @%s (email=%s, ER=%.2f%%)", enriched.username, enriched.email, enriched.engagement_rate)
        return enriched
