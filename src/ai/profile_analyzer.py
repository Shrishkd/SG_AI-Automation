"""
Influencer profile analyzer — scores and classifies profiles using Claude.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import track

from src.ai.claude_client import ClaudeClient

console = Console()

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


# ── Pydantic models ────────────────────────────────────────────────


class DimensionScores(BaseModel):
    niche_relevance: int = Field(..., ge=0, le=100)
    audience_quality: int = Field(..., ge=0, le=100)
    brand_safety: int = Field(..., ge=0, le=100)
    collaboration_likelihood: int = Field(..., ge=0, le=100)
    content_quality: int = Field(..., ge=0, le=100)


class AnalysisResult(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    dimension_scores: DimensionScores
    niche_category: str
    influencer_tier: Literal["nano", "micro", "mid", "macro"]
    profile_summary: str
    recommendation: Literal["recommend", "consider", "skip"]
    reasoning: str


# ── Helpers ─────────────────────────────────────────────────────────


def _determine_tier(follower_count: int) -> str:
    if follower_count < 10_000:
        return "nano"
    if follower_count < 100_000:
        return "micro"
    if follower_count < 500_000:
        return "mid"
    return "macro"


def _build_rubric_text(rubric: dict) -> str:
    """Render the scoring rubric YAML into a human-readable prompt section."""
    lines: list[str] = []
    for dim_name, dim in rubric["scoring"]["dimensions"].items():
        lines.append(f"### {dim_name} (weight {dim['weight']}%)")
        lines.append(dim["description"].strip())
        for range_label, guide in dim["scoring_guide"].items():
            lines.append(f"  {range_label}: {guide}")
        lines.append("")
    return "\n".join(lines)


# ── Main class ──────────────────────────────────────────────────────


class ProfileAnalyzer:
    """Uses ClaudeClient to score and analyze influencer profiles."""

    def __init__(self, client: ClaudeClient):
        self.client = client

        with open(CONFIG_DIR / "scoring_rubric.yaml", encoding="utf-8") as f:
            self.rubric: dict[str, Any] = yaml.safe_load(f)

        with open(CONFIG_DIR / "campaign.yaml", encoding="utf-8") as f:
            self.campaign: dict[str, Any] = yaml.safe_load(f)

        self._rubric_text = _build_rubric_text(self.rubric)
        self._thresholds = self.rubric["scoring"]["thresholds"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_profile(self, profile_data: dict) -> AnalysisResult:
        """Score a single influencer profile and return an AnalysisResult."""
        follower_count: int = profile_data.get("follower_count", 0)
        tier = _determine_tier(follower_count)

        system_prompt = self._system_prompt()
        user_prompt = self._user_prompt(profile_data, tier)

        raw: dict = self.client.generate_json(system_prompt, user_prompt)

        # Inject/override tier (computed from follower count, not Claude)
        raw["influencer_tier"] = tier

        # Derive recommendation from overall_score if Claude didn't provide one
        if "recommendation" not in raw:
            score = raw.get("overall_score", 0)
            if score >= self._thresholds["high_priority"]:
                raw["recommendation"] = "recommend"
            elif score >= self._thresholds["medium_priority"]:
                raw["recommendation"] = "consider"
            else:
                raw["recommendation"] = "skip"

        return AnalysisResult(**raw)

    def batch_analyze(self, profiles: list[dict]) -> list[AnalysisResult]:
        """Analyze a batch of profiles with a progress bar."""
        results: list[AnalysisResult] = []
        for profile in track(profiles, description="Analyzing profiles…"):
            try:
                result = self.analyze_profile(profile)
                results.append(result)
            except Exception as exc:
                username = profile.get("username", "unknown")
                console.log(f"[bold red]✗ Failed to analyze @{username}:[/] {exc}")
        return results

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _system_prompt(self) -> str:
        brand = self.campaign["brand"]
        campaign = self.campaign["campaign"]

        return (
            "You are an expert influencer-marketing analyst. "
            "Given an influencer's profile data and the scoring rubric below, "
            "produce a JSON object that scores the influencer across every dimension.\n\n"
            f"## Brand Context\n"
            f"Brand: {brand['name']} — {brand['tagline']}\n"
            f"Description: {brand['description'].strip()}\n"
            f"Campaign: {campaign['name']}\n"
            f"Goal: {campaign['goal'].strip()}\n\n"
            f"## Scoring Rubric\n{self._rubric_text}\n"
            "## Output Format\n"
            "Return ONLY a JSON object (no markdown fences) with these fields:\n"
            "  overall_score (int 0-100, weighted average of dimension scores),\n"
            "  dimension_scores (object with niche_relevance, audience_quality, brand_safety, "
            "collaboration_likelihood, content_quality — each int 0-100),\n"
            "  niche_category (string),\n"
            "  profile_summary (2-3 sentence summary),\n"
            "  recommendation (\"recommend\", \"consider\", or \"skip\"),\n"
            "  reasoning (string explaining the score)."
        )

    def _user_prompt(self, profile_data: dict, tier: str) -> str:
        import json

        return (
            f"Analyze the following influencer profile.\n"
            f"Follower-based tier: {tier}\n\n"
            f"```json\n{json.dumps(profile_data, indent=2, default=str)}\n```"
        )
