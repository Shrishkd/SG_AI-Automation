"""
Unit tests for PipelineManager and state transitions.
"""

from src.crm.pipeline import LeadStatus, PipelineManager, VALID_TRANSITIONS


def test_lead_statuses_exist():
    statuses = PipelineManager.get_all_statuses()
    assert LeadStatus.NEW_LEAD.value in statuses
    assert LeadStatus.EMAIL_AVAILABLE.value in statuses
    assert LeadStatus.EMAIL_SENT.value in statuses
    assert LeadStatus.FOLLOWUP_DUE.value in statuses
    assert LeadStatus.REPLIED.value in statuses
    assert LeadStatus.INTERESTED.value in statuses
    assert LeadStatus.NOT_INTERESTED.value in statuses
    assert LeadStatus.COLLABORATION_CONFIRMED.value in statuses


def test_valid_transitions():
    # New Lead -> Email Available is valid
    assert PipelineManager.can_transition(LeadStatus.NEW_LEAD.value, LeadStatus.EMAIL_AVAILABLE.value)
    # Email Sent -> Replied is valid
    assert PipelineManager.can_transition(LeadStatus.EMAIL_SENT.value, LeadStatus.REPLIED.value)
    # Replied -> Interested is valid
    assert PipelineManager.can_transition(LeadStatus.REPLIED.value, LeadStatus.INTERESTED.value)
    # Interested -> Collaboration Confirmed is valid
    assert PipelineManager.can_transition(LeadStatus.INTERESTED.value, LeadStatus.COLLABORATION_CONFIRMED.value)


def test_invalid_transitions():
    # Collaboration Confirmed cannot jump straight back to New Lead
    assert not PipelineManager.can_transition(LeadStatus.COLLABORATION_CONFIRMED.value, LeadStatus.NEW_LEAD.value)
    # New Lead cannot jump straight to Collaboration Confirmed
    assert not PipelineManager.can_transition(LeadStatus.NEW_LEAD.value, LeadStatus.COLLABORATION_CONFIRMED.value)


def test_funnel_counts():
    mock_records = [
        {"Status": LeadStatus.NEW_LEAD.value},
        {"Status": LeadStatus.NEW_LEAD.value},
        {"Status": LeadStatus.EMAIL_SENT.value},
        {"Status": LeadStatus.INTERESTED.value},
        {"Status": LeadStatus.COLLABORATION_CONFIRMED.value},
    ]
    counts = PipelineManager.get_funnel_counts(mock_records)
    assert counts[LeadStatus.NEW_LEAD.value] == 2
    assert counts[LeadStatus.EMAIL_SENT.value] == 1
    assert counts[LeadStatus.INTERESTED.value] == 1
    assert counts[LeadStatus.COLLABORATION_CONFIRMED.value] == 1
    assert counts[LeadStatus.REPLIED.value] == 0

