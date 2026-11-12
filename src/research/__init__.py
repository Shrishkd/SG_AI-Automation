"""
Research Package
================
Instagram influencer discovery, enrichment, and deduplication.
"""

from .deduplicator import Deduplicator
from .instagram_scraper import InstagramScraper
from .profile_enricher import EnrichedProfile, ProfileEnricher

__all__ = [
    "InstagramScraper",
    "ProfileEnricher",
    "EnrichedProfile",
    "Deduplicator",
]
