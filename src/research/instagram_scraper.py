"""
Instagram Scraper Module
========================
Searches for influencer profiles using Apify API (primary) and RapidAPI (fallback).
"""

import logging
import os
import time
from pathlib import Path
from typing import Any

import requests
import yaml
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class InstagramScraper:
    """Searches Instagram for influencer profiles via Apify (primary) and RapidAPI (fallback)."""

    # Apify actor IDs for Instagram scraping
    APIFY_HASHTAG_ACTOR = "apify/instagram-hashtag-scraper"
    APIFY_PROFILE_ACTOR = "apify/instagram-profile-scraper"
    APIFY_SEARCH_ACTOR = "apify/instagram-scraper"

    # Rate-limit defaults (seconds between API calls)
    DEFAULT_RATE_LIMIT = 1.0

    def __init__(
        self,
        apify_token: str | None = None,
        rapidapi_key: str | None = None,
        rapidapi_host: str | None = None,
        rate_limit: float = DEFAULT_RATE_LIMIT,
    ):
        self.apify_token = apify_token or os.getenv("APIFY_API_TOKEN")
        self.rapidapi_key = rapidapi_key or os.getenv("RAPIDAPI_KEY")
        self.rapidapi_host = rapidapi_host or os.getenv(
            "RAPIDAPI_HOST", "instagram-scraper-api2.p.rapidapi.com"
        )
        self.rate_limit = rate_limit
        self._last_request_time: float = 0.0

        if self.apify_token:
            self.apify_client = ApifyClient(self.apify_token)
            logger.info("Apify client initialised (primary source).")
        else:
            self.apify_client = None
            logger.warning("No APIFY_API_TOKEN found – Apify unavailable.")

        if not self.rapidapi_key:
            logger.warning("No RAPIDAPI_KEY found – RapidAPI fallback unavailable.")

    # ------------------------------------------------------------------
    # Rate-limiting helper
    # ------------------------------------------------------------------
    def _wait_for_rate_limit(self) -> None:
        """Block until at least ``self.rate_limit`` seconds have elapsed since the last request."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            logger.debug("Rate-limiting: sleeping %.2fs", sleep_time)
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
        """Map varying API response shapes into a consistent profile dict."""
        return {
            "username": raw.get("username") or raw.get("ownerUsername") or "",
            "full_name": raw.get("fullName") or raw.get("full_name") or raw.get("ownerFullName") or "",
            "bio": raw.get("biography") or raw.get("bio") or "",
            "follower_count": int(raw.get("followersCount") or raw.get("follower_count") or raw.get("edge_followed_by", {}).get("count", 0)),
            "following_count": int(raw.get("followsCount") or raw.get("following_count") or raw.get("edge_follow", {}).get("count", 0)),
            "post_count": int(raw.get("postsCount") or raw.get("post_count") or raw.get("edge_owner_to_timeline_media", {}).get("count", 0)),
            "profile_url": raw.get("url") or raw.get("profile_url") or f"https://www.instagram.com/{raw.get('username', '')}/",
            "external_url": raw.get("externalUrl") or raw.get("external_url") or "",
            "is_business": bool(raw.get("isBusinessAccount") or raw.get("is_business_account") or raw.get("is_business", False)),
            "is_verified": bool(raw.get("verified") or raw.get("is_verified", False)),
        }

    # ------------------------------------------------------------------
    # Apify methods
    # ------------------------------------------------------------------
    def _apify_search_by_hashtag(self, hashtag: str, max_results: int) -> list[dict[str, Any]]:
        """Use Apify Instagram Hashtag Scraper to find profiles posting with *hashtag*."""
        if not self.apify_client:
            raise RuntimeError("Apify client not initialised.")

        self._wait_for_rate_limit()
        logger.info("Apify hashtag search: #%s (max %d)", hashtag, max_results)

        run_input = {
            "hashtags": [hashtag],
            "resultsLimit": max_results,
            "resultsType": "posts",
        }

        try:
            run = self.apify_client.actor(self.APIFY_HASHTAG_ACTOR).call(run_input=run_input)
            items: list[dict] = list(
                self.apify_client.dataset(run["defaultDatasetId"]).iterate_items()
            )
            logger.info("Apify returned %d items for #%s", len(items), hashtag)
            return [self._normalize_profile(item) for item in items[:max_results]]
        except Exception:
            logger.exception("Apify hashtag search failed for #%s", hashtag)
            raise

    def _apify_search_by_keyword(self, keyword: str, max_results: int) -> list[dict[str, Any]]:
        """Use Apify Instagram Scraper to search by *keyword*."""
        if not self.apify_client:
            raise RuntimeError("Apify client not initialised.")

        self._wait_for_rate_limit()
        logger.info("Apify keyword search: '%s' (max %d)", keyword, max_results)

        run_input = {
            "search": keyword,
            "resultsLimit": max_results,
            "resultsType": "users",
            "searchType": "user",
        }

        try:
            run = self.apify_client.actor(self.APIFY_SEARCH_ACTOR).call(run_input=run_input)
            items: list[dict] = list(
                self.apify_client.dataset(run["defaultDatasetId"]).iterate_items()
            )
            logger.info("Apify returned %d items for '%s'", len(items), keyword)
            return [self._normalize_profile(item) for item in items[:max_results]]
        except Exception:
            logger.exception("Apify keyword search failed for '%s'", keyword)
            raise

    # ------------------------------------------------------------------
    # RapidAPI fallback methods
    # ------------------------------------------------------------------
    def _rapidapi_search_by_hashtag(self, hashtag: str, max_results: int) -> list[dict[str, Any]]:
        """Fallback: search by hashtag using RapidAPI."""
        if not self.rapidapi_key:
            raise RuntimeError("RapidAPI key not configured.")

        self._wait_for_rate_limit()
        logger.info("RapidAPI hashtag search (fallback): #%s", hashtag)

        url = f"https://{self.rapidapi_host}/v1/hashtag"
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": self.rapidapi_host,
        }
        params = {"hashtag": hashtag}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            items = data.get("data", {}).get("items", data.get("items", []))
            logger.info("RapidAPI returned %d items for #%s", len(items), hashtag)
            return [self._normalize_profile(item) for item in items[:max_results]]
        except requests.RequestException:
            logger.exception("RapidAPI hashtag search failed for #%s", hashtag)
            raise

    def _rapidapi_search_by_keyword(self, keyword: str, max_results: int) -> list[dict[str, Any]]:
        """Fallback: search by keyword using RapidAPI."""
        if not self.rapidapi_key:
            raise RuntimeError("RapidAPI key not configured.")

        self._wait_for_rate_limit()
        logger.info("RapidAPI keyword search (fallback): '%s'", keyword)

        url = f"https://{self.rapidapi_host}/v1.2/search/users"
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": self.rapidapi_host,
        }
        params = {"search": keyword}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            items = data.get("data", {}).get("items", data.get("items", []))
            logger.info("RapidAPI returned %d items for '%s'", len(items), keyword)
            return [self._normalize_profile(item) for item in items[:max_results]]
        except requests.RequestException:
            logger.exception("RapidAPI keyword search failed for '%s'", keyword)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search_by_hashtag(self, hashtag: str, max_results: int = 50) -> list[dict[str, Any]]:
        """Search for influencer profiles by hashtag.

        Tries Apify first; falls back to RapidAPI on failure.

        Returns:
            List of normalised profile dicts.
        """
        hashtag = hashtag.lstrip("#")

        # Try Apify (primary)
        if self.apify_client:
            try:
                return self._apify_search_by_hashtag(hashtag, max_results)
            except Exception:
                logger.warning("Apify failed for #%s – falling back to RapidAPI.", hashtag)

        # Fallback to RapidAPI
        if self.rapidapi_key:
            return self._rapidapi_search_by_hashtag(hashtag, max_results)

        logger.error("No API source available for hashtag search.")
        return []

    def search_by_keyword(self, keyword: str, max_results: int = 50) -> list[dict[str, Any]]:
        """Search for influencer profiles by keyword.

        Tries Apify first; falls back to RapidAPI on failure.

        Returns:
            List of normalised profile dicts.
        """
        # Try Apify (primary)
        if self.apify_client:
            try:
                return self._apify_search_by_keyword(keyword, max_results)
            except Exception:
                logger.warning("Apify failed for '%s' – falling back to RapidAPI.", keyword)

        # Fallback to RapidAPI
        if self.rapidapi_key:
            return self._rapidapi_search_by_keyword(keyword, max_results)

        logger.error("No API source available for keyword search.")
        return []

    def batch_search(self, config_path: str | Path | None = None) -> list[dict[str, Any]]:
        """Run multiple searches defined in a campaign.yaml configuration file.

        The config is expected to contain:
          - ``target_influencers.niches`` — list of hashtag-style niches
          - ``target_influencers.keywords`` — list of keyword queries
          - ``target_influencers.max_results_per_search`` — cap per query

        Results from all queries are merged and deduplicated by username.

        Args:
            config_path: Path to campaign.yaml.  Defaults to ``config/campaign.yaml``
                         relative to the project root.

        Returns:
            Merged list of normalised profile dicts (unique by username).
        """
        if config_path is None:
            config_path = Path(__file__).resolve().parents[2] / "config" / "campaign.yaml"
        else:
            config_path = Path(config_path)

        logger.info("Loading campaign config from %s", config_path)
        with open(config_path, "r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh)

        target = config.get("target_influencers", {})
        niches: list[str] = target.get("niches", [])
        keywords: list[str] = target.get("keywords", [])
        max_results: int = int(target.get("max_results_per_search", 50))

        all_profiles: list[dict[str, Any]] = []

        # Search by niche (treated as hashtags)
        for niche in niches:
            logger.info("Batch search — niche/hashtag: %s", niche)
            try:
                profiles = self.search_by_hashtag(niche, max_results)
                all_profiles.extend(profiles)
            except Exception:
                logger.exception("Batch hashtag search failed for '%s'", niche)

        # Search by keyword
        for kw in keywords:
            logger.info("Batch search — keyword: %s", kw)
            try:
                profiles = self.search_by_keyword(kw, max_results)
                all_profiles.extend(profiles)
            except Exception:
                logger.exception("Batch keyword search failed for '%s'", kw)

        # Deduplicate by username
        seen_usernames: set[str] = set()
        unique_profiles: list[dict[str, Any]] = []
        for profile in all_profiles:
            uname = profile.get("username", "").lower()
            if uname and uname not in seen_usernames:
                seen_usernames.add(uname)
                unique_profiles.append(profile)

        logger.info(
            "Batch search complete: %d total results, %d unique profiles.",
            len(all_profiles),
            len(unique_profiles),
        )
        return unique_profiles
