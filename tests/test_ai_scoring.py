"""
Unit tests for AI Profile Scoring and Dimension Models.
"""

from src.ai.profile_analyzer import DimensionScores, AnalysisResult, _determine_tier


def test_determine_tier():
    assert _determine_tier(4500) == "nano"
    assert _determine_tier(25000) == "micro"
    assert _determine_tier(150000) == "mid"
    assert _determine_tier(800000) == "macro"


def test_analysis_result_model():
    dims = DimensionScores(
        niche_relevance=90,
        audience_quality=85,
        brand_safety=95,
        collaboration_likelihood=80,
        content_quality=85,
    )
    res = AnalysisResult(
        overall_score=88,
        dimension_scores=dims,
        niche_category="Clean Beauty",
        influencer_tier="micro",
        profile_summary="Strong aesthetic and highly engaged audience for skincare.",
        recommendation="recommend",
        reasoning="High engagement and clean brand-safe content.",
    )
    assert res.overall_score == 88
    assert res.recommendation == "recommend"
    assert res.dimension_scores.niche_relevance == 90

