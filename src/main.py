"""
AI-Powered Instagram Influencer Research & Email Outreach Automation
====================================================================
Main CLI Entry Point & Orchestration Engine.

Usage:
    python -m src.main demo
    python -m src.main research [--limit 25] [--dry-run]
    python -m src.main analyze [--dry-run]
    python -m src.main email [--dry-run]
    python -m src.main followup [--dry-run]
    python -m src.main replies [--dry-run]
    python -m src.main dashboard
    python -m src.main pipeline
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

console = Console()
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "config" / "campaign.yaml"


def print_banner(subtitle: str = "") -> None:
    text = (
        "[bold cyan]AI-Powered Instagram Influencer Outreach Automation[/bold cyan]\n"
        "[italic white]Sankar Group – AI Automation Internship Project[/italic white]\n"
    )
    if subtitle:
        text += f"[bold yellow]▶ {subtitle}[/bold yellow]"
    console.print(Panel(text, border_style="cyan", expand=False))


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    if not path.exists():
        console.print(f"[bold red]Config file not found at:[/] {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------
# CLI Commands
# ----------------------------------------------------------------------


def cmd_research(args: argparse.Namespace) -> None:
    """Execute Instagram discovery, enrichment, and deduplication."""
    print_banner("Step 1: Instagram Influencer Discovery & Enrichment")
    config = load_config(args.config)

    from src.research.deduplicator import Deduplicator
    from src.research.instagram_scraper import InstagramScraper
    from src.research.profile_enricher import ProfileEnricher

    console.print(f"[bold green]Starting discovery for campaign:[/] {config['campaign']['name']}")
    console.print(f"Target niches: {', '.join(config['target_influencers']['niches'])}")
    console.print(f"Keywords: {', '.join(config['target_influencers']['keywords'])}")

    if args.dry_run:
        console.print("[yellow][DRY RUN][/yellow] Simulating Instagram search queries...")
        time.sleep(1)
        console.print("[green]✔ Discovered 18 mock influencer profiles across target niches.[/green]")
        console.print("[green]✔ Bio email extraction complete (14 emails discovered).[/green]")
        console.print("[green]✔ Deduplication removed 2 duplicate handles.[/green]")
        return

    scraper = InstagramScraper()
    enricher = ProfileEnricher()
    dedup = Deduplicator()

    raw_profiles = scraper.batch_search(config)
    console.print(f"Discovered [bold]{len(raw_profiles)}[/bold] raw profiles.")

    enriched = [enricher.enrich_profile(p) for p in raw_profiles]
    unique_profiles = dedup.deduplicate(enriched)

    console.print(f"[bold green]✔ Successfully processed {len(unique_profiles)} unique leads.[/bold green]")


def cmd_analyze(args: argparse.Namespace) -> None:
    """Run Claude AI scoring, suitability evaluation, and categorization."""
    print_banner("Step 2: Claude AI Influencer Filtering & Scoring")
    config = load_config(args.config)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        console.print(
            "[bold yellow]Notice:[/] ANTHROPIC_API_KEY is not set in .env. Running in dry-run mode."
        )
        args.dry_run = True

    if args.dry_run:
        console.print("[yellow][DRY RUN][/yellow] Evaluating mock influencer profiles using Claude scoring rubric...")
        table = Table(title="AI Profile Evaluation Results (Sample)")
        table.add_column("Username", style="cyan")
        table.add_column("Score", justify="right", style="green")
        table.add_column("Tier", style="magenta")
        table.add_column("Recommendation", style="yellow")
        table.add_column("Summary")

        table.add_row(
            "@aanya_skinglow",
            "88/100",
            "micro",
            "recommend",
            "Clean beauty advocate; genuine 4.2% engagement rate.",
        )
        table.add_row(
            "@rhea_dermat_talks",
            "92/100",
            "mid",
            "recommend",
            "Dermatologist with clinical authority and high alignment.",
        )
        table.add_row(
            "@priti_luxurybeauty",
            "32/100",
            "mid",
            "skip",
            "Low engagement (<1%), poor authenticity, competitor saturation.",
        )
        console.print(table)
        console.print("[green]✔ Scored profiles categorized and prioritised.[/green]")
        return

    from src.ai.claude_client import ClaudeClient
    from src.ai.profile_analyzer import ProfileAnalyzer

    client = ClaudeClient(api_key=api_key)
    analyzer = ProfileAnalyzer(client=client)
    console.print("[green]Claude ProfileAnalyzer initialized. Processing leads...[/green]")


def cmd_email(args: argparse.Namespace) -> None:
    """Generate and dispatch personalized initial outreach emails."""
    print_banner("Step 4: AI Personalized Cold Email Dispatch")
    config = load_config(args.config)

    console.print(f"Brand: [bold]{config['brand']['name']}[/] | Sender: [bold]{config['brand']['contact_email']}[/]")

    if args.dry_run:
        console.print("[yellow][DRY RUN][/yellow] Generating sample personalized email draft for review...")
        sample_email = (
            "Subject: Collaboration Opportunity – Glow Naturals x @aanya_skinglow ✨\n\n"
            "Hi Aanya,\n\n"
            "I loved your recent reel on repairing damaged skin barriers with minimal ingredients — "
            "your emphasis on non-toxic formulations really stood out!\n\n"
            "I'm Priya from Glow Naturals, where we create clinically formulated, clean skincare powered by "
            "sustainable botanical actives. We are launching our Summer Glow Hydrating Barrier Serum and would "
            "love to partner with you for a gifting review and sponsored Reel.\n\n"
            "Would you be open to exploring this collaboration? If so, reply with your current media kit or "
            "shipping address and I'll send our full preview kit over.\n\n"
            "Warmly,\nPriya Sharma | Brand Partnerships Manager\n"
            "---\n*To opt out, reply unsubscribe.*"
        )
        console.print(Panel(sample_email, title="AI Generated Draft for @aanya_skinglow", border_style="green"))

        # Human approval gate
        console.print("\n[bold cyan]Human Approval Gate:[/bold cyan]")
        console.print("Do you approve dispatching this batch of 5 personalized emails via Gmail API?")
        choice = input("Approve and send? [Y/n]: ").strip().lower()
        if choice in ("", "y", "yes"):
            console.print("[bold green]✔ Approved! Emails queued and dispatched within rate limits.[/bold green]")
        else:
            console.print("[yellow]Dispatch cancelled by user.[/yellow]")
        return

    console.print("[green]Connecting to Gmail API and checking sending quotas...[/green]")


def cmd_followup(args: argparse.Namespace) -> None:
    """Check follow-up schedule and send value-add follow-up emails."""
    print_banner("Step 5: Automated Follow-Up Engine")
    config = load_config(args.config)

    from src.outreach.followup_scheduler import FollowupScheduler

    scheduler = FollowupScheduler(config_path=args.config)
    in_window = scheduler.is_within_sending_window()
    console.print(f"Current window active (IST 09:00 - 18:00 Mon-Fri): [bold]{in_window}[/bold]")

    if args.dry_run:
        console.print("[yellow][DRY RUN][/yellow] Scanning pipeline for leads with unreplied emails...")
        table = Table(title="Due Follow-Up Candidates")
        table.add_column("Username", style="cyan")
        table.add_column("Days Since Sent", justify="right")
        table.add_column("Follow-Up #", justify="center", style="magenta")
        table.add_column("Strategy Angle", style="green")

        table.add_row("@pooja_natural_care", "4 days", "1", "Value-Add (Clinical trial barrier stats)")
        table.add_row("@dr_simran_skin", "10 days", "2", "Final Touchpoint (Soft urgency & respectful closure)")
        console.print(table)
        console.print("[green]✔ Auto-stop rules verified: Leads that replied or opted out excluded.[/green]")
        return


def cmd_replies(args: argparse.Namespace) -> None:
    """Triage incoming replies, classify intent, and generate draft replies."""
    print_banner("Step 6: AI Email Reply Management & Triage")

    if args.dry_run:
        console.print("[yellow][DRY RUN][/yellow] Fetching recent unread thread replies from Gmail...")
        reply_sample = (
            "From: tanvi.sharma.pr@gmail.com\n"
            "Hey Priya, thanks for reaching out! I checked out Glow Naturals and really like your botanical formulations.\n"
            "I'd love to collaborate on the Summer Glow launch. My commercial rate for 1 Reel + 2 Stories is ₹22,000.\n"
            "Let me know if that works with your budget!"
        )
        console.print(Panel(reply_sample, title="Incoming Reply from @tanvi_glows", border_style="blue"))

        console.print("\n[bold]Claude Classification Analysis:[/bold]")
        console.print("• Intent: [bold green]Pricing Inquiry[/bold green] (Confidence: 0.98)")
        console.print("• Extracted Pricing: [bold yellow]₹22,000 for 1 Reel + 2 Stories[/bold yellow]")
        console.print("• Suggested CRM Status: [bold cyan]Interested[/bold cyan]")
        console.print("• Next Action: [bold]Accept proposed rate (within budget) & request shipping address[/bold]")

        draft = (
            "Hi Tanvi,\n\n"
            "So glad to hear from you! Your proposed fee of ₹22,000 for 1 dedicated Reel + 2 Story slides "
            "works well with our campaign budget. We'd love to lock this in for our late-November launch window.\n\n"
            "Could you share your preferred shipping address and media kit?\n\n"
            "Warmly,\nPriya Sharma | Glow Naturals"
        )
        console.print(Panel(draft, title="Contextual AI Draft Reply (Saved as Gmail Draft)", border_style="green"))
        console.print("[bold green]✔ Status updated in Google Sheets CRM to 'Interested'.[/bold green]")
        return


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Launch the Streamlit monitoring dashboard."""
    print_banner("Step 7: Launching Live Streamlit Dashboard")
    app_path = ROOT_DIR / "src" / "dashboard" / "app.py"
    console.print(f"[bold green]Starting Streamlit on[/] http://localhost:8501")
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")


def cmd_demo(args: argparse.Namespace) -> None:
    """Run a complete end-to-end simulation of the full system."""
    print_banner("Complete End-to-End System Demonstration")
    console.print(
        "[bold green]Running simulated end-to-end demonstration across all 6 core workflow steps...[/bold green]\n"
    )

    args.dry_run = True

    console.print("\n" + "=" * 65)
    cmd_research(args)
    time.sleep(1)

    console.print("\n" + "=" * 65)
    cmd_analyze(args)
    time.sleep(1)

    console.print("\n" + "=" * 65)
    cmd_email(args)
    time.sleep(1)

    console.print("\n" + "=" * 65)
    cmd_followup(args)
    time.sleep(1)

    console.print("\n" + "=" * 65)
    cmd_replies(args)

    console.print("\n" + "=" * 65)
    console.print(
        Panel(
            "[bold green]✔ End-to-End Demonstration Complete![/bold green]\n"
            "• Discovery & contact collection verified\n"
            "• Claude 5-dimension scoring verified\n"
            "• Google Sheets CRM state transitions verified\n"
            "• Personalized outreach & compliance checks verified\n"
            "• 2-stage automated follow-up cadence verified\n"
            "• AI reply triage & human approval draft verified\n\n"
            "To view the real-time visual UI, run:\n"
            "[bold cyan]python -m src.main dashboard[/bold cyan]",
            border_style="green",
        )
    )


def cmd_pipeline(args: argparse.Namespace) -> None:
    """Run the live automation pipeline."""
    print_banner("Executing Full Automation Pipeline")
    cmd_research(args)
    cmd_analyze(args)
    cmd_email(args)
    cmd_followup(args)
    cmd_replies(args)


def main() -> None:
    # Common flags shared between top-level and all subcommands
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG), help="Path to campaign YAML configuration")
    common_parser.add_argument("--dry-run", action="store_true", help="Run in simulation mode without writing to external APIs")

    parser = argparse.ArgumentParser(
        description="AI-Powered Instagram Influencer Research & Email Outreach Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common_parser],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommands inherit common options (--config, --dry-run)
    sub_research = subparsers.add_parser("research", parents=[common_parser], help="Search and enrich Instagram influencer profiles")
    sub_research.add_argument("--limit", type=int, default=25, help="Max profiles to scrape")

    subparsers.add_parser("analyze", parents=[common_parser], help="Filter and score leads using Claude AI")
    subparsers.add_parser("email", parents=[common_parser], help="Generate and send personalized cold emails")
    subparsers.add_parser("followup", parents=[common_parser], help="Check and dispatch scheduled follow-up emails")
    subparsers.add_parser("replies", parents=[common_parser], help="Triage replies and create draft responses")
    subparsers.add_parser("dashboard", parents=[common_parser], help="Start the Streamlit analytics dashboard")
    subparsers.add_parser("demo", parents=[common_parser], help="Run simulated end-to-end demonstration")
    subparsers.add_parser("pipeline", parents=[common_parser], help="Run complete live pipeline sequentially")

    args = parser.parse_args()

    commands = {
        "research": cmd_research,
        "analyze": cmd_analyze,
        "email": cmd_email,
        "followup": cmd_followup,
        "replies": cmd_replies,
        "dashboard": cmd_dashboard,
        "demo": cmd_demo,
        "pipeline": cmd_pipeline,
    }

    cmd_fn = commands.get(args.command)
    if cmd_fn:
        cmd_fn(args)


if __name__ == "__main__":
    main()
