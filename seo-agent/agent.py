"""
MK Painting SEO Agent — Main entry point.

Connects to Google Search Console, runs the analysis pipeline,
generates a markdown report, and saves it to the reports directory.

Usage:
    python agent.py              # Full run with Claude AI recommendations
    python agent.py --no-ai      # Data-only report (no Claude API call)
    python agent.py --csv data/  # Load from CSV exports instead of API
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from analyzer import run_full_analysis
from config import LOOKBACK_DAYS
from gsc_client import fetch_page_data, fetch_query_data, load_from_csv
from reporter import generate_report


REPORTS_DIR = Path(__file__).parent.parent / "reports"


def main():
    args = parse_args()

    print("=" * 60)
    print("  MK Painting SEO Agent")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # ── 1. Fetch data ────────────────────────────────────────────────────────
    if args.csv:
        print(f"\n📂 Loading data from CSV directory: {args.csv}")
        query_data, page_data = load_csv_data(args.csv)
    else:
        print(f"\n🔗 Connecting to Google Search Console ({LOOKBACK_DAYS}-day lookback)...")
        query_data, page_data = fetch_api_data()

    if not query_data:
        print("❌ No query data found. Check your credentials or CSV files.")
        sys.exit(1)

    print(f"   → {len(query_data)} queries, {len(page_data)} pages loaded")

    # ── 2. Analyze ───────────────────────────────────────────────────────────
    print("\n🔍 Running analysis pipeline...")
    analysis = run_full_analysis(query_data, page_data)

    print(f"   → {len(analysis['striking_distance'])} striking distance keywords")
    print(f"   → {len(analysis['ctr_gaps'])} CTR gaps")
    print(f"   → {len(analysis['zero_click'])} zero-click queries")
    print(f"   → {len(analysis['missing_pages'])} missing landing pages")
    print(f"   → {len(analysis['suburb_opportunities'])} suburb opportunities")

    # ── 3. Generate report ───────────────────────────────────────────────────
    use_claude = not args.no_ai
    if use_claude:
        print("\n🤖 Generating AI recommendations via Claude...")
    else:
        print("\n📝 Generating data-only report (AI disabled)...")

    report = generate_report(analysis, use_claude=use_claude)

    # ── 4. Save report ───────────────────────────────────────────────────────
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"seo-report-{date_str}.md"

    report_path.write_text(report, encoding="utf-8")
    print(f"\n✅ Report saved to: {report_path}")

    # Also save as latest for easy access
    latest_path = REPORTS_DIR / "latest.md"
    latest_path.write_text(report, encoding="utf-8")
    print(f"   → Also saved as: {latest_path}")

    print("\n" + "=" * 60)
    print("  Done!")
    print("=" * 60)


def fetch_api_data():
    """Fetch data from the GSC API."""
    from gsc_client import get_gsc_service

    service = get_gsc_service()
    query_data = fetch_query_data(service=service)
    page_data = fetch_page_data(service=service)
    return query_data, page_data


def load_csv_data(csv_dir):
    """Load data from CSV files in the given directory."""
    csv_path = Path(csv_dir)
    query_data = []
    page_data = []

    # Look for query CSV
    for name in ["Queries.csv", "queries.csv", "Top queries.csv"]:
        path = csv_path / name
        if path.exists():
            query_data = load_from_csv(str(path))
            print(f"   → Loaded queries from {name}")
            break

    # Look for page CSV
    for name in ["Pages.csv", "pages.csv", "Top pages.csv"]:
        path = csv_path / name
        if path.exists():
            page_data = load_from_csv(str(path))
            print(f"   → Loaded pages from {name}")
            break

    if not query_data:
        # Try loading any CSV as query data
        csvs = list(csv_path.glob("*.csv"))
        if csvs:
            query_data = load_from_csv(str(csvs[0]))
            print(f"   → Loaded data from {csvs[0].name}")

    return query_data, page_data


def parse_args():
    parser = argparse.ArgumentParser(description="MK Painting SEO Agent")
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip Claude AI recommendations (data-only report)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to directory containing GSC CSV exports",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
