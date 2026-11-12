"""
Lead Lifecycle Pipeline Manager.
Defines valid statuses, transition rules, and next actions for influencer prospects.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


class LeadStatus(str, Enum):
    NEW_LEAD = "New Lead"
    EMAIL_AVAILABLE = "Email Available"
    EMAIL_SENT = "Email Sent"
    FOLLOWUP_DUE = "Follow-up Due"
    REPLIED = "Replied"
    INTERESTED = "Interested"
    NOT_INTERESTED = "Not Interested"
    COLLABORATION_CONFIRMED = "Collaboration Confirmed"


# Allowed state transitions
VALID_TRANSITIONS: dict[str, list[str]] = {
    LeadStatus.NEW_LEAD.value: [
        LeadStatus.EMAIL_AVAILABLE.value,
        LeadStatus.NOT_INTERESTED.value,
    ],
    LeadStatus.EMAIL_AVAILABLE.value: [
        LeadStatus.EMAIL_SENT.value,
        LeadStatus.NOT_INTERESTED.value,
    ],
    LeadStatus.EMAIL_SENT.value: [
        LeadStatus.FOLLOWUP_DUE.value,
        LeadStatus.REPLIED.value,
        LeadStatus.INTERESTED.value,
        LeadStatus.NOT_INTERESTED.value,
    ],
    LeadStatus.FOLLOWUP_DUE.value: [
        LeadStatus.EMAIL_SENT.value,
        LeadStatus.REPLIED.value,
        LeadStatus.NOT_INTERESTED.value,
    ],
    LeadStatus.REPLIED.value: [
        LeadStatus.INTERESTED.value,
        LeadStatus.NOT_INTERESTED.value,
        LeadStatus.COLLABORATION_CONFIRMED.value,
        LeadStatus.FOLLOWUP_DUE.value,
    ],
    LeadStatus.INTERESTED.value: [
        LeadStatus.COLLABORATION_CONFIRMED.value,
        LeadStatus.NOT_INTERESTED.value,
        LeadStatus.REPLIED.value,
    ],
    LeadStatus.NOT_INTERESTED.value: [
        LeadStatus.NEW_LEAD.value,  # Allow manual re-activation if needed
    ],
    LeadStatus.COLLABORATION_CONFIRMED.value: [
        LeadStatus.NOT_INTERESTED.value,  # If deal falls through
    ],
}

# Next actions recommended per status
STATUS_ACTIONS: dict[str, list[str]] = {
    LeadStatus.NEW_LEAD.value: [
        "Run AI Profile Analyzer to evaluate suitability and extract email",
        "Disqualify if score < 35 or irrelevance",
    ],
    LeadStatus.EMAIL_AVAILABLE.value: [
        "Generate personalized initial outreach email",
        "Review and approve email draft for dispatch",
    ],
    LeadStatus.EMAIL_SENT.value: [
        "Monitor for incoming reply",
        "Queue for Follow-up #1 after scheduled delay (3-5 days)",
    ],
    LeadStatus.FOLLOWUP_DUE.value: [
        "Generate value-add follow-up email",
        "Send follow-up #1 or #2 within sending window",
    ],
    LeadStatus.REPLIED.value: [
        "Run AI Reply Handler to classify intent",
        "Review AI draft response and dispatch",
    ],
    LeadStatus.INTERESTED.value: [
        "Send collaboration agreement / product shipment form",
        "Schedule brief onboarding call if required",
    ],
    LeadStatus.NOT_INTERESTED.value: [
        "Archive record",
        "Record feedback or decline reason in notes",
    ],
    LeadStatus.COLLABORATION_CONFIRMED.value: [
        "Dispatch product package / track delivery",
        "Set content delivery deadline and deliverables tracker",
    ],
}


class PipelineManager:
    """Manages lead lifecycle state transitions and pipeline integrity."""

    @staticmethod
    def get_all_statuses() -> list[str]:
        """Return all valid pipeline statuses in funnel order."""
        return [s.value for s in LeadStatus]

    @staticmethod
    def can_transition(current_status: str, new_status: str) -> bool:
        """Check if transitioning from `current_status` to `new_status` is permitted."""
        if current_status == new_status:
            return True
        allowed = VALID_TRANSITIONS.get(current_status, [])
        return new_status in allowed

    @staticmethod
    def get_next_actions(status: str) -> list[str]:
        """Return recommended actions for an influencer in the given state."""
        return STATUS_ACTIONS.get(status, ["Review influencer profile in CRM"])

    @classmethod
    def transition(
        cls,
        sheets_manager: Any,
        username: str,
        new_status: str,
        notes: str = "",
        force: bool = False,
    ) -> bool:
        """Execute a state transition in the CRM.

        Parameters
        ----------
        sheets_manager : SheetsManager
            Google Sheets manager instance.
        username : str
            Instagram handle of the influencer.
        new_status : str
            Target status.
        notes : str, optional
            Additional context or notes for the activity log.
        force : bool, default False
            If True, bypass transition validation checks.

        Returns
        -------
        bool
            True if the status was successfully updated.
        """
        record = sheets_manager.find_influencer(username)
        if not record:
            logger.warning("Influencer @%s not found in CRM.", username)
            return False

        current_status = record.get("Status", LeadStatus.NEW_LEAD.value)

        if not force and not cls.can_transition(current_status, new_status):
            logger.error(
                "Invalid transition for @%s: cannot move from '%s' to '%s'",
                username,
                current_status,
                new_status,
            )
            return False

        try:
            sheets_manager.update_status(username, new_status, notes=notes)
            sheets_manager.log_activity(
                username=username,
                action="Status Changed",
                details=f"Moved from '{current_status}' to '{new_status}'. {notes}".strip(),
            )
            console.log(
                f"[green]✔ Transitioned @{username}:[/] '{current_status}' ➜ [bold]{new_status}[/]"
            )
            return True
        except Exception as exc:
            logger.exception("Failed to update status for @%s: %s", username, exc)
            return False

    @staticmethod
    def get_funnel_counts(influencers: list[dict[str, Any]]) -> dict[str, int]:
        """Aggregate counts across all pipeline stages."""
        counts = {status.value: 0 for status in LeadStatus}
        for inf in influencers:
            st = inf.get("Status") or inf.get("status")
            if st in counts:
                counts[st] += 1
            else:
                counts[LeadStatus.NEW_LEAD.value] += 1
        return counts

