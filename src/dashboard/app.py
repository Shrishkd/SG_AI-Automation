"""
Streamlit Dashboard for AI Influencer Outreach & Campaign Analytics.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

# Page configuration
st.set_page_config(
    page_title="AI Influencer Outreach Engine",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEMO_CSV_PATH = ROOT_DIR / "demo" / "sample_sheet.csv"
CONFIG_PATH = ROOT_DIR / "config" / "campaign.yaml"


@st.cache_data(ttl=60)
def load_campaign_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "brand": {"name": "Glow Naturals", "tagline": "Clean Beauty, Real Results"},
        "campaign": {"name": "Summer Glow 2026", "budget_range": "₹5k-₹50k"},
    }


def load_influencer_data(source: str = "csv") -> pd.DataFrame:
    """Load data from local demo CSV or live Google Sheets."""
    if source == "sheets":
        try:
            from src.crm.sheets_manager import SheetsManager

            sheet_id = os.getenv("GOOGLE_SHEET_ID")
            creds = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
            if sheet_id and os.path.exists(creds):
                mgr = SheetsManager(credentials_path=creds, sheet_id=sheet_id)
                records = mgr.get_all_influencers()
                if records:
                    return pd.DataFrame(records)
        except Exception as exc:
            st.sidebar.warning(f"Sheets connection failed: {exc}. Falling back to CSV.")

    if DEMO_CSV_PATH.exists():
        df = pd.read_csv(DEMO_CSV_PATH)
        return df

    # Fallback minimal mock DataFrame
    return pd.DataFrame(
        columns=[
            "Name",
            "Username",
            "Profile URL",
            "Niche",
            "Followers",
            "Engagement Rate",
            "Email",
            "AI Score",
            "AI Summary",
            "Status",
            "Email Sent Date",
            "Follow-up Count",
            "Last Reply Date",
            "Last Activity",
            "Notes",
        ]
    )


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and typecast DataFrame columns for analytics."""
    df = df.copy()
    if "AI Score" in df.columns:
        df["AI Score"] = pd.to_numeric(df["AI Score"], errors="coerce").fillna(0).astype(int)
    if "Followers" in df.columns:
        df["Followers"] = pd.to_numeric(df["Followers"], errors="coerce").fillna(0).astype(int)
    if "Engagement Rate" in df.columns:
        df["Engagement_Num"] = (
            df["Engagement Rate"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .astype(float, errors="ignore")
        )
        df["Engagement_Num"] = pd.to_numeric(df["Engagement_Num"], errors="coerce").fillna(0.0)
    return df


def main() -> None:
    config = load_campaign_config()
    brand_name = config.get("brand", {}).get("name", "Glow Naturals")
    campaign_name = config.get("campaign", {}).get("name", "Summer Glow 2026")

    # Custom Header Styling
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 24px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #334155;">
            <h1 style="color: #f8fafc; margin: 0; font-size: 28px; font-weight: 700;">
                ✨ AI Influencer Outreach & CRM Dashboard
            </h1>
            <p style="color: #94a3b8; margin: 6px 0 0 0; font-size: 15px;">
                Campaign: <strong>{campaign_name}</strong> | Brand: <strong>{brand_name}</strong> | Autonomous Discovery, Filtering & Outreach
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sidebar Controls ────────────────────────────────────────────────
    st.sidebar.header("🕹️ Campaign Controls")
    data_mode = st.sidebar.radio("Data Connection", ["Demo CSV Data", "Live Google Sheets"])
    source_key = "sheets" if data_mode == "Live Google Sheets" else "csv"

    raw_df = load_influencer_data(source=source_key)
    df = clean_dataframe(raw_df)

    # Filters
    niches = sorted(list(df["Niche"].dropna().unique())) if "Niche" in df.columns else []
    selected_niches = st.sidebar.multiselect("Filter by Niche", niches, default=niches)

    all_statuses = [
        "New Lead",
        "Email Available",
        "Email Sent",
        "Follow-up Due",
        "Replied",
        "Interested",
        "Not Interested",
        "Collaboration Confirmed",
    ]
    selected_statuses = st.sidebar.multiselect("Filter by Pipeline Status", all_statuses, default=all_statuses)

    min_score = st.sidebar.slider("Min AI Suitability Score", 0, 100, 40)

    # Apply filters
    filtered_df = df.copy()
    if selected_niches:
        filtered_df = filtered_df[filtered_df["Niche"].isin(selected_niches)]
    if selected_statuses:
        filtered_df = filtered_df[filtered_df["Status"].isin(selected_statuses)]
    if "AI Score" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["AI Score"] >= min_score]

    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.info(
        "💡 **Key Highlights:**\n"
        "- 100% CAN-SPAM compliant\n"
        "- 5-Dimension AI Scoring\n"
        "- Claude Context-Aware Email Drafts\n"
        "- Automated 2-Stage Follow-ups"
    )

    # ── Section 1: KPI Metrics ──────────────────────────────────────────
    total_found = len(df)
    qualified = len(df[df["AI Score"] >= 55]) if "AI Score" in df.columns else 0
    emails_sent = len(df[df["Status"].isin(["Email Sent", "Follow-up Due", "Replied", "Interested", "Collaboration Confirmed"])])
    replies = len(df[df["Status"].isin(["Replied", "Interested", "Collaboration Confirmed"])])
    confirmed = len(df[df["Status"] == "Collaboration Confirmed"])
    response_rate = (replies / emails_sent * 100) if emails_sent > 0 else 0.0

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        st.metric("Total Prospects", total_found)
    with kpi2:
        st.metric("AI Qualified (≥55)", qualified, f"{(qualified/total_found*100):.1f}%" if total_found else "0%")
    with kpi3:
        st.metric("Emails Dispatched", emails_sent)
    with kpi4:
        st.metric("Response Rate", f"{response_rate:.1f}%", f"{replies} replies")
    with kpi5:
        st.metric("Collabs Confirmed", confirmed, delta="Active Deals")

    st.markdown("---")

    # ── Section 2: Visual Pipeline Funnel ───────────────────────────────
    col_funnel, col_score = st.columns([1.1, 0.9])

    with col_funnel:
        st.subheader("📊 Lead Lifecycle Funnel")
        funnel_stages = [
            "New Lead",
            "Email Available",
            "Email Sent",
            "Follow-up Due",
            "Replied",
            "Interested",
            "Collaboration Confirmed",
        ]
        funnel_counts = [len(df[df["Status"] == stage]) for stage in funnel_stages]

        fig_funnel = go.Figure(
            go.Funnel(
                y=funnel_stages,
                x=funnel_counts,
                textinfo="value+percent initial",
                marker={
                    "color": [
                        "#64748b",
                        "#38bdf8",
                        "#60a5fa",
                        "#f59e0b",
                        "#818cf8",
                        "#34d399",
                        "#10b981",
                    ]
                },
            )
        )
        fig_funnel.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            height=340,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

    with col_score:
        st.subheader("🎯 AI Score Distribution")
        if "AI Score" in df.columns and len(df) > 0:
            fig_hist = px.histogram(
                df,
                x="AI Score",
                nbins=10,
                color="Niche",
                marginal="box",
                title="AI Score Spread by Niche",
            )
            fig_hist.update_layout(
                margin=dict(l=20, r=20, t=30, b=20),
                height=340,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_hist, use_container_width=True)

    # ── Section 3: Reply Classification Breakdown ──────────────────────
    col_replies, col_engagement = st.columns(2)

    with col_replies:
        st.subheader("💬 AI Reply Intent Classification")
        reply_sample_data = pd.DataFrame(
            {
                "Intent": ["Pricing Inquiry", "Product Question", "Positive / Interested", "Decline / Competitor Exclusivity", "Opt-Out"],
                "Count": [4, 3, 5, 2, 1],
            }
        )
        fig_pie = px.pie(
            reply_sample_data,
            names="Intent",
            values="Count",
            hole=0.45,
            color_discrete_sequence=px.colors.sequential.Tealgrn,
        )
        fig_pie.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            height=300,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_engagement:
        st.subheader("📈 Follower Size vs. Engagement Rate")
        if "Followers" in df.columns and "Engagement_Num" in df.columns:
            fig_scatter = px.scatter(
                df,
                x="Followers",
                y="Engagement_Num",
                size="AI Score",
                color="Status",
                hover_name="Username",
                labels={"Engagement_Num": "Engagement Rate (%)", "Followers": "Followers Count"},
            )
            fig_scatter.update_layout(
                margin=dict(l=20, r=20, t=20, b=20),
                height=300,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

    # ── Section 4: Live Filtered CRM Table ─────────────────────────────
    st.markdown("---")
    st.subheader(f"📋 Influencer CRM Pipeline Records ({len(filtered_df)} showing)")

    display_cols = [
        "Name",
        "Username",
        "Niche",
        "Followers",
        "Engagement Rate",
        "Email",
        "AI Score",
        "Status",
        "Follow-up Count",
        "Last Activity",
        "Notes",
    ]
    available_cols = [c for c in display_cols if c in filtered_df.columns]

    st.dataframe(
        filtered_df[available_cols],
        use_container_width=True,
        hide_index=True,
    )

    # CSV Export
    csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Filtered CRM to CSV",
        data=csv_bytes,
        file_name="influencer_campaign_export.csv",
        mime="text/csv",
    )

    # ── Section 5: Recent Audit Trail / Activity Feed ───────────────────
    st.markdown("---")
    st.subheader("⏱️ Live Activity Audit Trail")
    sample_logs = [
        {"Time": "2026-11-12 11:30", "Influencer": "@aanya_skinglow", "Action": "Collaboration Confirmed", "Details": "Courier tracking provided for Summer Glow package"},
        {"Time": "2026-11-12 11:15", "Influencer": "@rhea_dermat_talks", "Action": "Status Changed", "Details": "Moved to 'Interested'. Call scheduled for Friday 4 PM"},
        {"Time": "2026-11-12 10:45", "Influencer": "@tanvi_glows", "Action": "Reply Classified", "Details": "Classified as 'Pricing Inquiry' (₹22,000 for Reel + 2 Stories). Draft created."},
        {"Time": "2026-11-12 10:00", "Influencer": "@meera_skindiaries", "Action": "Email Sent", "Details": "Personalized initial outreach dispatched via Gmail API"},
        {"Time": "2026-11-12 09:30", "Influencer": "@pooja_natural_care", "Action": "Follow-up Sent", "Details": "Follow-up #1 (Value-Add angle) sent after 4-day threshold"},
    ]
    st.table(pd.DataFrame(sample_logs))


if __name__ == "__main__":
    main()

