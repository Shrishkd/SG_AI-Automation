"""
Email compliance & anti-spam utilities.

Enforces sending limits, validates email content, detects opt-out signals,
and tracks send volume via a lightweight JSON log.
"""

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

SENDING_LOG_PATH = Path("sending_log.json")

# Words / phrases that trigger spam filters — keep lowercase.
SPAM_TRIGGER_WORDS: list[str] = [
    "act now",
    "buy now",
    "click here",
    "congratulations",
    "dear friend",
    "free offer",
    "guaranteed",
    "limited time",
    "no obligation",
    "urgent",
    "winner",
    "you have been selected",
    "100% free",
    "earn money",
    "make money fast",
]

# Phrases that signal the recipient wants out — keep lowercase.
OPT_OUT_SIGNALS: list[str] = [
    "unsubscribe",
    "stop emailing",
    "remove me",
    "not interested",
    "opt out",
    "opt-out",
    "take me off",
    "don't contact",
    "do not contact",
    "don't email",
    "do not email",
    "no thanks",
    "leave me alone",
    "stop contacting",
    "remove from list",
    "please stop",
]

MAX_SUBJECT_LENGTH = 200
MAX_BODY_LENGTH = 5000


# ======================================================================
# Sending Tracker
# ======================================================================

class SendingTracker:
    """Tracks emails sent per hour and per day using a JSON file."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        self.log_path = Path(log_path) if log_path else SENDING_LOG_PATH
        self._ensure_log()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def record_send(self, email: str) -> None:
        """Append a send event to the log."""
        log = self._load()
        log["sends"].append(
            {
                "email": email,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._save(log)

    def get_hourly_count(self) -> int:
        """Number of emails sent in the current UTC hour."""
        now = datetime.now(timezone.utc)
        start_of_hour = now.replace(minute=0, second=0, microsecond=0)
        return self._count_since(start_of_hour)

    def get_daily_count(self) -> int:
        """Number of emails sent today (UTC)."""
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._count_since(start_of_day)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _count_since(self, since: datetime) -> int:
        log = self._load()
        count = 0
        for entry in log.get("sends", []):
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts >= since:
                    count += 1
            except (KeyError, ValueError):
                continue
        return count

    def _ensure_log(self) -> None:
        if not self.log_path.exists():
            self._save({"sends": []})

    def _load(self) -> dict[str, Any]:
        try:
            with open(self.log_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"sends": []}

    def _save(self, data: dict[str, Any]) -> None:
        with open(self.log_path, "w") as f:
            json.dump(data, f, indent=2)


# ======================================================================
# Compliance Checker
# ======================================================================

class ComplianceChecker:
    """Ensures email sending follows anti-spam rules and rate limits."""

    def __init__(
        self,
        daily_limit: int | None = None,
        hourly_limit: int | None = None,
    ) -> None:
        self.daily_limit: int = (
            daily_limit
            if daily_limit is not None
            else int(os.getenv("GMAIL_DAILY_LIMIT", "50"))
        )
        self.hourly_limit: int = (
            hourly_limit
            if hourly_limit is not None
            else int(os.getenv("GMAIL_HOURLY_LIMIT", "20"))
        )
        self.tracker = SendingTracker()

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def can_send(self, daily_sent: int, hourly_sent: int) -> bool:
        """Return ``True`` if sending another email is within both limits."""
        return daily_sent < self.daily_limit and hourly_sent < self.hourly_limit

    def get_sending_stats(self) -> dict[str, int]:
        """Current counts and remaining capacity."""
        hourly = self.tracker.get_hourly_count()
        daily = self.tracker.get_daily_count()
        return {
            "hourly_sent": hourly,
            "hourly_limit": self.hourly_limit,
            "hourly_remaining": max(0, self.hourly_limit - hourly),
            "daily_sent": daily,
            "daily_limit": self.daily_limit,
            "daily_remaining": max(0, self.daily_limit - daily),
        }

    # ------------------------------------------------------------------
    # Delays
    # ------------------------------------------------------------------

    @staticmethod
    def get_random_delay() -> float:
        """Return a random delay between 30 and 90 seconds."""
        return random.uniform(30.0, 90.0)

    # ------------------------------------------------------------------
    # Content validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_email_content(subject: str, body: str) -> tuple[bool, list[str]]:
        """Validate an email against anti-spam / compliance rules.

        Returns ``(is_valid, issues)`` where *issues* is a list of
        human-readable problem descriptions (empty when valid).
        """
        issues: list[str] = []

        # 1. Opt-out / unsubscribe notice
        body_lower = body.lower()
        if "unsubscribe" not in body_lower and "opt out" not in body_lower:
            issues.append("Email body must include an opt-out / unsubscribe option.")

        # 2. Sender identification
        has_identification = any(
            marker in body_lower
            for marker in ["--\n", "regards", "best,", "sincerely", "cheers"]
        )
        if not has_identification:
            issues.append("Email body should include a sender signature / identification.")

        # 3. Length checks
        if len(subject) > MAX_SUBJECT_LENGTH:
            issues.append(f"Subject too long ({len(subject)} chars, max {MAX_SUBJECT_LENGTH}).")

        if len(body) > MAX_BODY_LENGTH:
            issues.append(f"Body too long ({len(body)} chars, max {MAX_BODY_LENGTH}).")

        if not subject.strip():
            issues.append("Subject line is empty.")

        if not body.strip():
            issues.append("Email body is empty.")

        # 4. Spam trigger words
        found_spam: list[str] = []
        combined = f"{subject} {body}".lower()
        for trigger in SPAM_TRIGGER_WORDS:
            if trigger in combined:
                found_spam.append(trigger)
        if found_spam:
            issues.append(f"Contains spam trigger words: {', '.join(found_spam)}.")

        return (len(issues) == 0, issues)

    # ------------------------------------------------------------------
    # Opt-out detection
    # ------------------------------------------------------------------

    @staticmethod
    def check_opt_out(reply_text: str) -> bool:
        """Return ``True`` if *reply_text* contains opt-out signals."""
        text_lower = reply_text.lower()
        return any(signal in text_lower for signal in OPT_OUT_SIGNALS)

