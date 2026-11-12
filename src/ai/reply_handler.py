"""
AI Email Reply Management — Classifies incoming influencer replies and drafts contextual responses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field
from rich.console import Console

from src.ai.claude_client import ClaudeClient

console = Console()

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

ReplyType = Literal[
    "interested",
    "not_interested",
    "pricing_inquiry",
    "question",
    "out_of_office",
    "opt_out",
    "spam",
]


class ReplyClassification(BaseModel):
    """Structured result of an AI reply classification."""

    classification: ReplyType
    confidence: float = Field(..., ge=0.0, le=1.0)
    key_points: list[str] = Field(default_factory=list)
    extracted_pricing: Optional[str] = None
    suggested_crm_status: str
    suggested_next_action: str
    draft_reply: Optional[str] = None
    needs_human_review: bool = True
    reasoning: str = ""


class ReplyHandler:
    """Classifies incoming influencer replies and generates context-aware draft responses."""

    def __init__(self, client: ClaudeClient, config_dir: Path | str | None = None) -> None:
        self.client = client
        base = Path(config_dir) if config_dir else CONFIG_DIR

        with open(base / "email_templates.yaml", encoding="utf-8") as f:
            self.templates: dict[str, Any] = yaml.safe_load(f)

        with open(base / "campaign.yaml", encoding="utf-8") as f:
            self.campaign: dict[str, Any] = yaml.safe_load(f)

        self._brand = self.campaign["brand"]
        self._campaign_info = self.campaign["campaign"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_reply(
        self,
        original_email: str,
        reply_text: str,
        influencer_data: dict[str, Any],
    ) -> ReplyClassification:
        """Classify an incoming reply and generate an action plan + draft response.

        Parameters
        ----------
        original_email : str
            The text of our outreach email that the influencer is replying to.
        reply_text : str
            The incoming reply text from the influencer.
        influencer_data : dict
            Metadata about the influencer (name, username, niche, etc.).

        Returns
        -------
        ReplyClassification
            Structured evaluation with category, action, and draft reply.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(original_email, reply_text, influencer_data)

        raw = self.client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1500,
        )

        return self._build_result(raw)

    def batch_classify(
        self,
        replies: list[dict[str, Any]],
    ) -> list[ReplyClassification]:
        """Classify multiple replies in sequence.

        Each element of `replies` should be a dict containing:
          - original_email: str
          - reply_text: str
          - influencer_data: dict
        """
        results: list[ReplyClassification] = []
        for item in replies:
            res = self.classify_reply(
                original_email=item.get("original_email", ""),
                reply_text=item.get("reply_text", ""),
                influencer_data=item.get("influencer_data", {}),
            )
            results.append(res)
        return results

    # ------------------------------------------------------------------
    # Prompt Construction
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        tmpl = self.templates.get("reply_drafts", {})
        base_prompt = tmpl.get(
            "system_prompt",
            "You are an AI assistant managing influencer collaboration replies.",
        )
        tone_guidelines = "\n".join(f"- {g}" for g in tmpl.get("tone_matching", []))

        return f"""{base_prompt}

You represent the brand:
- Brand: {self._brand.get('name')}
- Tagline: {self._brand.get('tagline')}
- Description: {self._brand.get('description')}
- Website: {self._brand.get('website')}
- Sender: {self._brand.get('contact_name')}, {self._brand.get('contact_title')} ({self._brand.get('contact_email')})
- Campaign: {self._campaign_info.get('name')}
- Collaboration types: {', '.join(self._campaign_info.get('collaboration_types', []))}
- Budget range: {self._campaign_info.get('budget_range')}

Tone guidelines:
{tone_guidelines}

Your task:
1. Carefully analyze the influencer's response in the context of the outreach email thread.
2. Classify the reply into exactly one of:
   - "interested": Influencer shows enthusiasm, wants to collaborate, or asks how to proceed.
   - "not_interested": Direct rejection, polite decline, or bad timing without interest.
   - "pricing_inquiry": Influencer shares their rate card, asks for budget/compensation, or quotes rates.
   - "question": Influencer asks specific questions about the product, deliverables, or brand before deciding.
   - "out_of_office": Automated vacation, out-of-office, or temporary leave response.
   - "opt_out": Influencer requests to be removed from future emails or states "unsubscribe".
   - "spam": Irrelevant, promotional pitch from an agency/bot, or unrelated email.
3. Extract any pricing or rates mentioned (e.g., "$250 per reel", "₹15,000 per post").
4. Determine the suggested CRM status:
   - "Interested"
   - "Not Interested"
   - "Replied"
   - "Collaboration Confirmed"
   - "Follow-up Due"
5. Suggest the immediate next action for the brand manager.
6. Draft a high-touch, human, context-aware reply (if appropriate).
   - If not interested or opt-out, draft a graceful, warm closing (or empty if spam/autoresponder).
   - If pricing inquiry, acknowledge their rates professionally and suggest next steps aligned with budget.
   - If interested or question, provide enthusiastic, clear answers and offer a link/call or shipping details.
   - Always sign off warmly as {self._brand.get('contact_name')}.

Return ONLY a valid JSON object with the following schema:
{{
  "classification": "interested | not_interested | pricing_inquiry | question | out_of_office | opt_out | spam",
  "confidence": 0.95,
  "key_points": ["point 1", "point 2"],
  "extracted_pricing": "extracted rate string or null",
  "suggested_crm_status": "Interested | Not Interested | Replied",
  "suggested_next_action": "action description",
  "draft_reply": "email body draft or null",
  "needs_human_review": true,
  "reasoning": "1-2 sentence explanation of why this classification was chosen"
}}"""

    def _build_user_prompt(
        self,
        original_email: str,
        reply_text: str,
        influencer_data: dict[str, Any],
    ) -> str:
        name = influencer_data.get("full_name") or influencer_data.get("name") or "there"
        username = influencer_data.get("username", "")
        niche = influencer_data.get("niche", "content creator")
        followers = influencer_data.get("follower_count") or influencer_data.get("followers", "N/A")

        return f"""Influencer Details:
- Name: {name}
- Instagram: @{username}
- Niche: {niche}
- Followers: {followers}

Original Outreach Email Sent:
----------------------------------------
{original_email.strip()}
----------------------------------------

Incoming Reply Received:
----------------------------------------
{reply_text.strip()}
----------------------------------------

Please analyze this reply and output the JSON classification with draft reply."""

    # ------------------------------------------------------------------
    # Response Parsing & Fallbacks
    # ------------------------------------------------------------------

    def _build_result(self, raw: dict[str, Any]) -> ReplyClassification:
        valid_types = {
            "interested",
            "not_interested",
            "pricing_inquiry",
            "question",
            "out_of_office",
            "opt_out",
            "spam",
        }
        cls_val = str(raw.get("classification", "replied")).lower().strip()
        if cls_val not in valid_types:
            if "interest" in cls_val:
                cls_val = "interested"
            elif "not" in cls_val or "decline" in cls_val:
                cls_val = "not_interested"
            elif "price" in cls_val or "rate" in cls_val:
                cls_val = "pricing_inquiry"
            elif "opt" in cls_val or "unsub" in cls_val:
                cls_val = "opt_out"
            else:
                cls_val = "question"

        return ReplyClassification(
            classification=cls_val,  # type: ignore[arg-type]
            confidence=float(raw.get("confidence", 0.9)),
            key_points=list(raw.get("key_points", [])),
            extracted_pricing=raw.get("extracted_pricing"),
            suggested_crm_status=str(raw.get("suggested_crm_status", "Replied")),
            suggested_next_action=str(raw.get("suggested_next_action", "Review draft reply")),
            draft_reply=raw.get("draft_reply"),
            needs_human_review=bool(raw.get("needs_human_review", True)),
            reasoning=str(raw.get("reasoning", "")),
        )

