"""
Unit tests for ComplianceChecker and anti-spam rules.
"""

from src.outreach.compliance import ComplianceChecker, OPT_OUT_SIGNALS, SPAM_TRIGGER_WORDS


def test_opt_out_detection():
    assert ComplianceChecker.check_opt_out("Please unsubscribe me from your emails.")
    assert ComplianceChecker.check_opt_out("Not interested, thanks.")
    assert ComplianceChecker.check_opt_out("Stop emailing me!")
    assert not ComplianceChecker.check_opt_out("I would love to collaborate on this launch!")


def test_spam_trigger_words():
    # Clean email with signature and opt-out notice
    clean_body = (
        "Hi Aanya, we admire your skincare tutorials and would love to gift you our new "
        "Summer Glow Hydrating Barrier Serum for your review. Let us know if you'd like to try it.\n\n"
        "Best,\nPriya Sharma\n--\nIf you prefer to opt out, reply unsubscribe."
    )
    is_valid, issues = ComplianceChecker.validate_email_content("Collaboration Opportunity", clean_body)
    assert is_valid, f"Expected clean body to be valid, got issues: {issues}"

    # Spammy email missing opt-out and containing spam words
    spam_body = "CONGRATULATIONS! Act now to earn money fast with our 100% free guaranteed offer! Click here!"
    is_valid_spam, issues_spam = ComplianceChecker.validate_email_content("FREE MONEY", spam_body)
    assert not is_valid_spam
    assert len(issues_spam) > 0


def test_rate_limits():
    checker = ComplianceChecker(daily_limit=50, hourly_limit=20)
    assert checker.can_send(daily_sent=10, hourly_sent=5)
    assert not checker.can_send(daily_sent=50, hourly_sent=5)
    assert not checker.can_send(daily_sent=10, hourly_sent=20)
