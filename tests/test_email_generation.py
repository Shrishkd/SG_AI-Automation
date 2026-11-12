"""
Unit tests for Email Drafts and Reply Handling Models.
"""

from src.ai.email_composer import EmailDraft
from src.ai.reply_handler import ReplyClassification


def test_email_draft_model():
    draft = EmailDraft(
        subject="Collaboration Opportunity – Glow Naturals x @aanya_skinglow",
        body="Hi Aanya, we loved your routine reel! Would love to partner on our Summer Glow launch.",
        influencer_username="aanya_skinglow",
    )
    assert draft.influencer_username == "aanya_skinglow"
    assert "Collaboration Opportunity" in draft.subject


def test_reply_classification_model():
    res = ReplyClassification(
        classification="pricing_inquiry",
        confidence=0.95,
        key_points=["Quoted ₹20,000 for 1 reel", "Available in December"],
        extracted_pricing="₹20,000 for 1 reel",
        suggested_crm_status="Interested",
        suggested_next_action="Accept fee within budget and request shipping address",
        draft_reply="Hi! We'd love to proceed at that rate. What's your shipping address?",
        needs_human_review=True,
    )
    assert res.classification == "pricing_inquiry"
    assert res.extracted_pricing == "₹20,000 for 1 reel"
    assert res.suggested_crm_status == "Interested"
    assert res.needs_human_review is True

