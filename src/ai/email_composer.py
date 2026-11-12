"""
Personalized email composer for influencer outreach using Claude.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from rich.console import Console

from src.ai.claude_client import ClaudeClient

console = Console()

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


# ── Pydantic models ────────────────────────────────────────────────


class EmailDraft(BaseModel):
    subject: str
    body: str
    influencer_username: str


# ── Main class ──────────────────────────────────────────────────────


class EmailComposer:
    """Generates personalised outreach emails via ClaudeClient."""

    def __init__(self, client: ClaudeClient):
        self.client = client

        with open(CONFIG_DIR / "email_templates.yaml", encoding="utf-8") as f:
            self.templates: dict[str, Any] = yaml.safe_load(f)

        with open(CONFIG_DIR / "campaign.yaml", encoding="utf-8") as f:
            self.campaign: dict[str, Any] = yaml.safe_load(f)

        self._brand = self.campaign["brand"]
        self._campaign_info = self.campaign["campaign"]
        self._email_cfg = self.campaign["email"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose_initial_email(
        self,
        influencer_data: dict,
        analysis: dict,
    ) -> EmailDraft:
        """Compose the first outreach email to an influencer."""
        tmpl = self.templates["initial_email"]
        username = influencer_data.get("username", "")

        system_prompt = self._enrich_system_prompt(
            tmpl["system_prompt"],
            tmpl.get("guidelines", []),
            tmpl.get("structure", []),
        )

        user_prompt = (
            "Write an initial outreach email for the influencer below.\n\n"
            f"## Influencer data\n```json\n{json.dumps(influencer_data, indent=2, default=str)}\n```\n\n"
            f"## AI Analysis\n```json\n{json.dumps(analysis, indent=2, default=str)}\n```\n\n"
            "Return ONLY a JSON object with two fields:\n"
            '  "subject": the email subject line,\n'
            '  "body": the full email body text (plain text, no HTML).'
        )

        raw = self.client.generate_json(system_prompt, user_prompt)

        subject = raw.get("subject") or self._default_subject(username)
        body = raw.get("body", "")
        body = self._append_footer(body)

        return EmailDraft(subject=subject, body=body, influencer_username=username)

    def compose_followup(
        self,
        influencer_data: dict,
        original_email: str,
        followup_number: int,
    ) -> EmailDraft:
        """Compose a follow-up email (1 or 2)."""
        key = f"followup_{followup_number}"
        tmpl = self.templates.get(key)
        if tmpl is None:
            raise ValueError(f"No template found for followup number {followup_number}")

        username = influencer_data.get("username", "")

        system_prompt = self._enrich_system_prompt(
            tmpl["system_prompt"],
            tmpl.get("guidelines", []),
        )

        user_prompt = (
            f"Write follow-up #{followup_number} for the influencer below.\n\n"
            f"## Influencer data\n```json\n{json.dumps(influencer_data, indent=2, default=str)}\n```\n\n"
            f"## Original email sent\n{original_email}\n\n"
            "Return ONLY a JSON object with two fields:\n"
            '  "subject": the email subject line,\n'
            '  "body": the full email body text (plain text, no HTML).'
        )

        raw = self.client.generate_json(system_prompt, user_prompt)

        subject = raw.get("subject") or f"Re: {self._default_subject(username)}"
        body = raw.get("body", "")
        body = self._append_footer(body)

        return EmailDraft(subject=subject, body=body, influencer_username=username)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enrich_system_prompt(
        self,
        base_prompt: str,
        guidelines: list[str] | None = None,
        structure: list[str] | None = None,
    ) -> str:
        parts = [base_prompt.strip()]

        # Brand context
        parts.append(
            f"\n## Brand Context\n"
            f"Brand: {self._brand['name']} — {self._brand['tagline']}\n"
            f"Description: {self._brand['description'].strip()}\n"
            f"Campaign: {self._campaign_info['name']}\n"
            f"Goal: {self._campaign_info['goal'].strip()}\n"
            f"Collaboration types: {', '.join(self._campaign_info['collaboration_types'])}\n"
            f"Budget range: {self._campaign_info['budget_range']}"
        )

        if guidelines:
            parts.append("\n## Guidelines\n" + "\n".join(f"- {g}" for g in guidelines))

        if structure:
            parts.append("\n## Email Structure\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(structure)))

        return "\n".join(parts)

    def _default_subject(self, username: str) -> str:
        template = self._email_cfg.get(
            "subject_template",
            "Collaboration Opportunity – {brand_name} x @{username}",
        )
        return template.format(brand_name=self._brand["name"], username=username)

    def _append_footer(self, body: str) -> str:
        footer_tmpl: str = self.templates["initial_email"].get("footer", "")
        if not footer_tmpl:
            return body

        footer = footer_tmpl.format(
            contact_name=self._brand["contact_name"],
            contact_title=self._brand["contact_title"],
            brand_name=self._brand["name"],
            brand_website=self._brand["website"],
        )
        return f"{body}\n\n{footer.rstrip()}"
