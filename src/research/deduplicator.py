"""
Deduplicator Module
===================
Removes duplicate influencer profiles by exact username match and
normalised email comparison.
"""

import logging

from .profile_enricher import EnrichedProfile

logger = logging.getLogger(__name__)


class Deduplicator:
    """Removes duplicate :class:`EnrichedProfile` entries."""

    @staticmethod
    def _normalize_email(email: str | None) -> str:
        """Lowercase and strip an email for comparison.

        Returns an empty string for ``None`` so that two profiles
        *without* emails are never treated as duplicates of each other
        by email alone.
        """
        if not email:
            return ""
        return email.strip().lower()

    def deduplicate(self, profiles: list[EnrichedProfile]) -> list[EnrichedProfile]:
        """Remove duplicate profiles from *profiles*.

        Duplicates are identified by:
        1. **Exact username match** (case-insensitive).
        2. **Normalised email match** — if two profiles share the same
           non-empty email (after lowercasing and stripping), the later
           one is dropped.

        Args:
            profiles: List of enriched profiles, potentially with duplicates.

        Returns:
            A new list with duplicates removed (first occurrence kept).
        """
        seen_usernames: set[str] = set()
        seen_emails: set[str] = set()
        unique: list[EnrichedProfile] = []
        duplicate_count = 0

        for profile in profiles:
            username_key = profile.username.strip().lower()

            # Check username duplicate
            if username_key in seen_usernames:
                duplicate_count += 1
                logger.debug("Duplicate (username): @%s", profile.username)
                continue

            # Check email duplicate (only for non-empty emails)
            email_key = self._normalize_email(profile.email)
            if email_key and email_key in seen_emails:
                duplicate_count += 1
                logger.debug(
                    "Duplicate (email): @%s (%s)", profile.username, email_key
                )
                continue

            # Not a duplicate — keep it
            seen_usernames.add(username_key)
            if email_key:
                seen_emails.add(email_key)
            unique.append(profile)

        logger.info(
            "Deduplication complete: %d input → %d unique (%d duplicates removed).",
            len(profiles),
            len(unique),
            duplicate_count,
        )
        return unique
