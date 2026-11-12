"""
Unit tests for research, enrichment, and deduplication.
"""

from src.research.deduplicator import Deduplicator
from src.research.profile_enricher import EnrichedProfile, ProfileEnricher


def test_email_extraction_from_bio():
    enricher = ProfileEnricher()

    bio_1 = "Skin enthusiast ✨ For collabs: aanya.collabs@gmail.com | Mumbai 📍"
    email_1 = enricher.extract_email(bio=bio_1)
    assert email_1 == "aanya.collabs@gmail.com"

    bio_2 = "DM for queries or write to hello[at]dermatcare.in"
    # Bracketed email format
    email_2 = enricher.extract_email(bio=bio_2)
    assert email_2 == "hello@dermatcare.in"

    bio_3 = "Just living my best life. No business info."
    assert enricher.extract_email(bio=bio_3) is None


def test_engagement_rate_calculation():
    enricher = ProfileEnricher()
    # 5,000 likes + comments on 100,000 followers = 5.0%
    rate = enricher.calculate_engagement_rate(likes=4500, comments=500, followers=100000)
    assert rate == 5.0

    # 0 followers should return 0.0 safely
    assert enricher.calculate_engagement_rate(likes=10, comments=2, followers=0) == 0.0


def test_deduplication():
    dedup = Deduplicator()
    profiles = [
        EnrichedProfile(
            username="skin_guru",
            full_name="Skin Guru",
            bio="Skincare lover",
            follower_count=25000,
            following_count=400,
            post_count=120,
            profile_url="https://instagram.com/skin_guru",
            email="collab@skinguru.com",
            engagement_rate=3.5,
        ),
        EnrichedProfile(
            username="SKIN_GURU",  # Duplicate case variant
            full_name="Skin Guru duplicate",
            bio="Skincare lover duplicate",
            follower_count=25000,
            following_count=400,
            post_count=120,
            profile_url="https://instagram.com/skin_guru",
            email="collab@skinguru.com",
            engagement_rate=3.5,
        ),
        EnrichedProfile(
            username="glow_expert",
            full_name="Glow Expert",
            bio="Glow lover",
            follower_count=15000,
            following_count=200,
            post_count=80,
            profile_url="https://instagram.com/glow_expert",
            email="glow@expert.com",
            engagement_rate=4.2,
        ),
    ]

    unique = dedup.deduplicate(profiles)
    assert len(unique) == 2
    assert {p.username.lower() for p in unique} == {"skin_guru", "glow_expert"}

