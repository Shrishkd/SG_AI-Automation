"""
Follow-up scheduling engine for the outreach campaign.

Reads timing rules from campaign.yaml and orchestrates follow-up sends
via the Gmail sender, email composer, and CRM (Sheets) manager.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from zoneinfo import ZoneInfo

console = Console()

IST = ZoneInfo("Asia/Kolkata")

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "campaign.yaml"


class FollowupScheduler:
    """Manages follow-up timing logic based on campaign configuration."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        path = Path(config_path) if config_path else CONFIG_PATH
        with open(path, "r") as f:
            config = yaml.safe_load(f)

        email_cfg = config.get("email", {})
        self.followup_1_delay_days: int = email_cfg.get("followup_1_delay_days", 4)
        self.followup_2_delay_days: int = email_cfg.get("followup_2_delay_days", 6)
        self.max_followups: int = email_cfg.get("max_followups", 2)

        window = email_cfg.get("sending_window", {})
        self.start_hour: int = window.get("start_hour", 9)
        self.end_hour: int = window.get("end_hour", 18)
        self.sending_days: list[str] = [d.lower() for d in window.get("days", ["monday", "tuesday", "wednesday", "thursday", "friday"])]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_followup_candidates(self, sheets_manager: Any) -> list[dict[str, Any]]:
        """Query the CRM for leads that are due for a follow-up.

        Looks for rows with status ``Email Sent`` or ``Follow-up Due`` where
        enough time has elapsed since the last email.

        Parameters
        ----------
        sheets_manager : SheetsManager
            CRM sheets manager with ``get_all_influencers()`` method.

        Returns
        -------
        list[dict]
            Each dict has all influencer fields plus ``followup_number``
            (1 or 2) indicating which follow-up is next.
        """
        candidates: list[dict[str, Any]] = []

        try:
            influencers = sheets_manager.get_all_influencers()
        except Exception as exc:
            console.log(f"[red]Error fetching influencers from CRM:[/] {exc}")
            return candidates

        now = datetime.now(IST)

        for inf in influencers:
            status = (inf.get("status") or "").strip()
            if status not in ("Email Sent", "Follow-up Due"):
                continue

            followups_sent = int(inf.get("followups_sent", 0) or 0)

            if followups_sent >= self.max_followups:
                continue

            followup_number = followups_sent + 1

            if self.should_send_followup(inf, followup_number, now=now):
                candidates.append({**inf, "followup_number": followup_number})

        console.log(f"[cyan]Follow-up candidates found:[/] {len(candidates)}")
        return candidates

    def should_send_followup(
        self,
        influencer: dict[str, Any],
        followup_number: int,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Determine whether a follow-up should be sent right now.

        Checks:
        1. Max follow-ups not exceeded.
        2. Enough time has elapsed since the last email.
        3. Current time is within the allowed sending window.
        """
        if followup_number > self.max_followups:
            return False

        if not self.is_within_sending_window(now=now):
            return False

        now = now or datetime.now(IST)

        last_email_date_str = (
            influencer.get("last_email_date")
            or influencer.get("email_sent_date")
            or ""
        )
        if not last_email_date_str:
            return False

        try:
            last_email_date = self._parse_date(last_email_date_str)
        except ValueError:
            console.log(f"[yellow]Unparseable date '{last_email_date_str}' for {influencer.get('username', '?')}[/]")
            return False

        delay_days = (
            self.followup_1_delay_days if followup_number == 1
            else self.followup_2_delay_days
        )

        return now >= last_email_date + timedelta(days=delay_days)

    def is_within_sending_window(self, *, now: datetime | None = None) -> bool:
        """Return ``True`` if the current IST time is inside the sending window."""
        now = (now or datetime.now(IST)).astimezone(IST)
        day_name = now.strftime("%A").lower()

        if day_name not in self.sending_days:
            return False

        return self.start_hour <= now.hour < self.end_hour

    def schedule_followups(
        self,
        sheets_manager: Any,
        gmail_sender: Any,
        email_composer: Any,
    ) -> list[dict[str, Any]]:
        """Orchestrate a complete follow-up pass.

        1. Find candidates via :meth:`get_followup_candidates`.
        2. Generate the appropriate follow-up email via *email_composer*.
        3. Send via *gmail_sender*.
        4. Update CRM status in *sheets_manager*.

        Returns a list of result dicts for each processed candidate.
        """
        candidates = self.get_followup_candidates(sheets_manager)
        results: list[dict[str, Any]] = []

        for candidate in candidates:
            username = candidate.get("username", "unknown")
            email = candidate.get("email", "")
            followup_number = candidate["followup_number"]
            thread_id = candidate.get("thread_id")

            if not email:
                console.log(f"[yellow]Skipping {username} — no email address[/]")
                continue

            # --- Generate email content ---
            try:
                composed = email_composer.compose_followup(
                    influencer=candidate,
                    followup_number=followup_number,
                )
                subject = composed.get("subject", "")
                body = composed.get("body", "")
            except Exception as exc:
                console.log(f"[red]Failed to compose followup {followup_number} for {username}:[/] {exc}")
                continue

            # --- Send ---
            try:
                send_result = gmail_sender.send_email(
                    to=email,
                    subject=subject,
                    body=body,
                    thread_id=thread_id,
                )
            except Exception as exc:
                console.log(f"[red]Failed to send followup to {username}:[/] {exc}")
                continue

            # --- Update CRM ---
            try:
                now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M")
                sheets_manager.update_influencer_status(
                    username=username,
                    status="Follow-up Sent" if followup_number < self.max_followups else "Max Follow-ups Reached",
                    last_email_date=now_str,
                    followups_sent=followup_number,
                    thread_id=send_result.get("thread_id", thread_id),
                )
            except Exception as exc:
                console.log(f"[yellow]CRM update failed for {username}:[/] {exc}")

            results.append(
                {
                    "username": username,
                    "followup_number": followup_number,
                    "message_id": send_result.get("message_id"),
                    "thread_id": send_result.get("thread_id"),
                    "sent_at": send_result.get("sent_at"),
                }
            )
            console.log(
                f"[green]✓ Follow-up {followup_number} sent to @{username}[/]"
            )

        console.log(f"[bold green]Follow-up pass complete:[/] {len(results)}/{len(candidates)} sent")
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse a date string into a timezone-aware IST datetime."""
        date_str = date_str.strip()
        for fmt in (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ):
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=IST)
                return dt
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {date_str}")

