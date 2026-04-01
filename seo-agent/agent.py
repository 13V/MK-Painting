"""
MK Painting SEO Agent — Main entry point.

Connects to Google Search Console, runs the analysis pipeline,
generates a markdown report, optionally implements changes via PR,
and sends Telegram notifications.

Usage:
    python agent.py              # Full run with AI + implementation + Telegram
    python agent.py --no-ai      # Data-only report (no Claude API call)
    python agent.py --no-impl    # Report only, no code changes
    python agent.py --csv data/  # Load from CSV exports instead of API
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from analyzer import run_full_analysis
from config import (
    GITHUB_REPO_URL,
    LOOKBACK_DAYS,
    MAX_BLOG_ARTICLES_PER_RUN,
    MAX_NEW_PAGES_PER_RUN,
    SITE_URL,
)
from gsc_client import (
    fetch_page_data,
    fetch_query_data,
    inspect_and_submit_new_pages,
    load_from_csv,
)
from implementer import (
    apply_changes,
    create_pr,
    create_new_page_pr,
    generate_changes,
    generate_new_page,
    pick_best_new_page,
    write_new_page,
    create_blog_pr,
    generate_blog_article,
    pick_best_blog,
    write_blog_article,
)
from reporter import generate_report, format_site_audit
from telegram_notifier import (
    send_blog_notification,
    send_daily_report,
    send_indexing_update,
    send_new_page_notification,
    send_pr_notification,
)


REPORTS_DIR = Path(__file__).parent.parent / "reports"


def main():
    args = parse_args()

    print("=" * 60)
    print("  MK Painting SEO Agent")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # One-time image optimization mode
    if args.optimize_images:
        from image_optimizer import run_full_optimization
        repo_root = str(Path(__file__).parent.parent)
        run_full_optimization(repo_root)
        print("\n" + "=" * 60)
        print("  Image optimization complete!")
        print("=" * 60)
        return

    if args.csv:
        print(f"\n📂 Loading data from CSV directory: {args.csv}")
        query_data, page_data, query_page_data = load_csv_data(args.csv)
    else:
        print(f"\n🔗 Connecting to Google Search Console ({LOOKBACK_DAYS}-day lookback)...")
        query_data, page_data, query_page_data = fetch_api_data()

    if not query_data:
        print("❌ No query data found. Check your credentials or CSV files.")
        sys.exit(1)

    print(f"   → {len(query_data)} queries, {len(page_data)} pages loaded")

    # ── 2. Analyze ───────────────────────────────────────────────────────────
    print("\n🔍 Running analysis pipeline...")
    analysis = run_full_analysis(query_data, page_data, query_page_data)

    print(f"   → {len(analysis['striking_distance'])} striking distance keywords")
    print(f"   → {len(analysis['ctr_gaps'])} CTR gaps")
    print(f"   → {len(analysis['zero_click'])} zero-click queries")
    print(f"   → {len(analysis['missing_pages'])} missing landing pages")
    print(f"   → {len(analysis['suburb_opportunities'])} suburb opportunities")
    if analysis.get("blog_opportunities"):
        print(f"   → {len(analysis['blog_opportunities'])} blog opportunities")
    if analysis.get("missing_service_pages"):
        print(f"   → {len(analysis['missing_service_pages'])} missing service pages")
    if analysis.get("cannibalization"):
        print(f"   → {len(analysis['cannibalization'])} cannibalization alerts")
    if analysis.get("map_pack_queries"):
        print(f"   → {len(analysis['map_pack_queries'])} map-pack-dominated queries (GBP focus)")

    # ── 2b. Trend tracking ─────────────────────────────────────────────────
    print("\n📊 Saving daily snapshot & computing trends...")
    try:
        from data_store import save_daily_snapshot, load_previous_snapshot, compute_trends
        snapshot_path = save_daily_snapshot(query_data, page_data, analysis["summary"])
        print(f"   → Snapshot saved: {snapshot_path}")

        prev = load_previous_snapshot()
        trends = compute_trends(query_data, prev)
        analysis["trends"] = trends

        if trends["previous_date"]:
            pc = len(trends["position_changes"])
            nk = len(trends["new_keywords"])
            print(f"   → vs {trends['previous_date']}: {pc} position changes, {nk} new keywords")
            if trends["summary_delta"]:
                d = trends["summary_delta"]
                print(f"   → Clicks {d['clicks_delta']:+d}, Impressions {d['impressions_delta']:+d}")
        else:
            print("   → No previous snapshot found (first run)")
    except Exception as e:
        print(f"   ⚠ Trend tracking failed: {e}")
        analysis["trends"] = None

    # ── 2c. GA4 conversion data ──────────────────────────────────────────────
    print("\n📊 Fetching GA4 conversion data...")
    try:
        from ga4_client import fetch_ga4_summary
        ga4_data = fetch_ga4_summary(days=7)
        if ga4_data:
            analysis["ga4"] = ga4_data
            print(f"   → {ga4_data['total_sessions']} sessions ({ga4_data['organic_sessions']} organic)")
            print(f"   → {ga4_data['phone_clicks']} phone call click(s)")
        else:
            print("   → GA4 not configured (set GA4_PROPERTY_ID)")
            analysis["ga4"] = None
    except Exception as e:
        print(f"   ⚠ GA4 fetch failed: {e}")
        analysis["ga4"] = None

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

    # ── 5. URL inspection & indexing ─────────────────────────────────────────
    if not args.csv and not args.no_index:
        print("\n🔎 Checking indexing status of all pages...")
        try:
            index_results = inspect_and_submit_new_pages()
            print(f"   → {len(index_results['already_indexed'])} pages already indexed")
            print(f"   → {len(index_results['submitted'])} pages submitted for crawling")
            if index_results["errors"]:
                print(f"   → {len(index_results['errors'])} errors (see report)")

            # Append indexing section to report
            index_section = _format_indexing_results(index_results)
            report += index_section
            report_path.write_text(report, encoding="utf-8")
            latest_path.write_text(report, encoding="utf-8")

            # Telegram: notify about unindexed pages
            if index_results["submitted"]:
                send_indexing_update(
                    len(index_results["already_indexed"]),
                    index_results["submitted"],
                )
        except Exception as e:
            print(f"   → Indexing check failed: {e}")

    # ── 6. Telegram: daily report summary ────────────────────────────────────
    print("\n📱 Sending Telegram notification...")
    report_github_url = f"{GITHUB_REPO_URL}/blob/main/reports/seo-report-{date_str}.md"
    send_daily_report(analysis, report_url=report_github_url)

    # ── 7. Implement changes via PR ──────────────────────────────────────────
    if use_claude and not args.no_impl and not args.csv:
        has_opportunities = (
            analysis["ctr_gaps"] or analysis["striking_distance"] or analysis["zero_click"]
        )
        if has_opportunities:
            print("\n🔧 Generating SEO changes...")
            repo_root = str(Path(__file__).parent.parent)
            changes = generate_changes(analysis, repo_root=repo_root)

            print("\n🔗 Analyzing internal links for weak anchor text...")
            try:
                from linker import analyze_and_optimize_anchors
                linker_changes = analyze_and_optimize_anchors(repo_root)
                if linker_changes:
                    changes.extend(linker_changes)
            except Exception as e:
                print(f"   ⚠ Anchor optimization error: {e}")

            print("\n🧠 Initiating Generative Engine Optimization (GEO)...")
            try:
                from geo import generate_llm_txt, get_local_business_schema_change
                geo_changes = []
                geo_changes.extend(generate_llm_txt(repo_root))
                geo_changes.extend(get_local_business_schema_change(repo_root))
                if geo_changes:
                    changes.extend(geo_changes)
            except Exception as e:
                print(f"   ⚠ GEO optimization error: {e}")

            if changes:
                print(f"   → {len(changes)} changes proposed")
                applied = apply_changes(changes, repo_root)

                if applied:
                    print(f"\n📦 Committing to main...")
                    commit_url, commit_hash = create_pr(applied, repo_root)

                    if commit_url:
                        print(f"   → Pushed {commit_hash}: {commit_url}")

                        changes_summary = [
                            {
                                "file": c["file"],
                                "change_type": c["change_type"],
                                "description": c["description"],
                            }
                            for c in applied
                        ]
                        send_pr_notification(commit_url, commit_hash, changes_summary)
                    else:
                        print("   → Commit failed")
            else:
                print("   → No actionable changes generated")
        else:
            print("\n   → No CTR gaps or striking distance keywords — skipping implementation")

    # ── 8. Generate new landing pages (up to MAX_NEW_PAGES_PER_RUN) ─────────
    if use_claude and not args.no_impl and not args.csv:
        repo_root = str(Path(__file__).parent.parent)
        created_pages = set()
        pages_created = 0

        for i in range(MAX_NEW_PAGES_PER_RUN):
            opportunity = pick_best_new_page(analysis, repo_root, exclude=created_pages)
            if not opportunity:
                if i == 0:
                    print("\n   → No new page opportunities detected")
                break

            print(f"\n🆕 New page [{i+1}/{MAX_NEW_PAGES_PER_RUN}]: {opportunity['suburb'].title()} "
                  f"({opportunity['impressions']} impressions)")
            print(f"   Target keyword: \"{opportunity['keyword']}\"")
            print(f"   Generating {opportunity['filename']}...")

            html = generate_new_page(opportunity, repo_root)

            if html:
                changed_files = write_new_page(html, opportunity, repo_root)
                print(f"   📦 Committing to main...")
                commit_url, commit_hash = create_new_page_pr(opportunity, changed_files, repo_root)

                if commit_url:
                    print(f"   → Pushed {commit_hash}: {commit_url}")
                    send_new_page_notification(commit_url, commit_hash, opportunity)
                    pages_created += 1
                else:
                    print("   → Commit failed")
            else:
                print("   → Page generation failed")

            created_pages.add(opportunity["filename"])

        if pages_created > 0:
            print(f"\n   → {pages_created} new page(s) created this run")

    # ── 8b. Generate blog articles (up to MAX_BLOG_ARTICLES_PER_RUN) ──────────
    if use_claude and not args.no_impl and not args.csv:
        repo_root = str(Path(__file__).parent.parent)
        created_blogs = set()
        blogs_created = 0

        for i in range(MAX_BLOG_ARTICLES_PER_RUN):
            blog_opp = pick_best_blog(analysis, repo_root, exclude=created_blogs)
            if not blog_opp:
                if i == 0:
                    print("\n   → No blog opportunities detected")
                break

            print(f"\n📝 Blog [{i+1}/{MAX_BLOG_ARTICLES_PER_RUN}]: \"{blog_opp['topic']}\" "
                  f"({blog_opp['impressions']} impressions)")
            print(f"   Target keyword: \"{blog_opp['keyword']}\"")
            print(f"   Generating {blog_opp['filename']}...")

            blog_html = generate_blog_article(blog_opp, repo_root)

            if blog_html:
                blog_changed = write_blog_article(blog_html, blog_opp, repo_root)
                print(f"   📦 Committing to main...")
                blog_url, blog_hash = create_blog_pr(blog_opp, blog_changed, repo_root)

                if blog_url:
                    print(f"   → Pushed {blog_hash}: {blog_url}")
                    send_blog_notification(blog_url, blog_hash, blog_opp)
                    blogs_created += 1
                else:
                    print("   → Commit failed")
            else:
                print("   → Blog generation failed")

            created_blogs.add(blog_opp["filename"])

        if blogs_created > 0:
            print(f"\n   → {blogs_created} blog article(s) created this run")

    # ── 9. Map Pack Update ───────────────────────────────────────────────────
    if use_claude and not args.no_impl and not args.csv:
        try:
            from gbp_agent import publish_gbp_post
            publish_gbp_post(repo_root, analysis=analysis)
        except Exception as e:
            print(f"   ⚠ Map Pack update failed: {e}")

    # ── 9b. Site health audit ─────────────────────────────────────────────────
    if not args.csv:
        print("\n🏥 Running site health audit...")
        try:
            from site_auditor import run_all_audits, auto_repair_sitemap
            audit_root = str(Path(__file__).parent.parent)
            audit_results = run_all_audits(audit_root)

            coord_fixes = audit_results.get("coord_fixes", [])
            faq_issues = audit_results.get("faq_issues", [])
            alt_issues = audit_results.get("alt_issues", [])
            sitemap_issues = audit_results.get("sitemap_issues", {})
            print(
                f"   → {len(coord_fixes)} coord fix(es), "
                f"{len(faq_issues)} FAQ issue(s), "
                f"{len(alt_issues)} alt issue(s), "
                f"sitemap: {len(sitemap_issues.get('missing', []))} missing / "
                f"{len(sitemap_issues.get('orphaned', []))} orphaned"
            )

            # Auto-apply coord fixes (safe, mechanical — no AI needed)
            if coord_fixes:
                print(f"   → Auto-applying {len(coord_fixes)} coord fix(es)...")
                apply_changes(coord_fixes, audit_root)

            # Auto-repair sitemap (add missing pages, remove orphans, update lastmod)
            sitemap_fixes = auto_repair_sitemap(audit_root)
            if sitemap_fixes:
                print(f"   → Auto-repaired sitemap: {len(sitemap_fixes)} fix(es)")
                for fix in sitemap_fixes:
                    print(f"     {fix}")

                # Resubmit sitemap to GSC after repairs
                try:
                    from gsc_client import resubmit_sitemap
                    resubmit_sitemap()
                except Exception as e:
                    print(f"   ⚠ Sitemap resubmission failed: {e}")

            # Append audit section to the saved report
            audit_section = format_site_audit(audit_results)
            if audit_section:
                report += audit_section
                report_path.write_text(report, encoding="utf-8")
                latest_path.write_text(report, encoding="utf-8")

        except Exception as e:
            print(f"   ⚠ Site health audit failed: {e}")

    print("\n" + "=" * 60)
    print("  Done!")
    print("=" * 60)


def fetch_api_data():
    """Fetch data from the GSC API."""
    from gsc_client import get_gsc_service, fetch_query_page_data

    service = get_gsc_service()
    query_data = fetch_query_data(service=service)
    page_data = fetch_page_data(service=service)
    query_page_data = fetch_query_page_data(service=service)
    return query_data, page_data, query_page_data


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

    return query_data, page_data, []


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
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Skip URL inspection and indexing submission",
    )
    parser.add_argument(
        "--no-impl",
        action="store_true",
        help="Skip auto-implementation of changes (report only)",
    )
    parser.add_argument(
        "--optimize-images",
        action="store_true",
        help="One-time: convert oversized images to WebP and fix favicon",
    )
    return parser.parse_args()


def _format_indexing_results(results):
    """Format indexing results as a markdown section."""
    lines = [
        "\n## URL Indexing Status\n",
    ]

    if results["already_indexed"]:
        lines.append(f"### Indexed ({len(results['already_indexed'])})\n")
        for url in results["already_indexed"]:
            short = url.replace(SITE_URL.rstrip("/"), "")
            lines.append(f"- {short}")

    if results["submitted"]:
        lines.append(f"\n### Submitted for Crawling ({len(results['submitted'])})\n")
        for item in results["submitted"]:
            short = item["url"].replace(SITE_URL.rstrip("/"), "")
            lines.append(f"- {short} — {item['status']}")

    if results["errors"]:
        lines.append(f"\n### Errors ({len(results['errors'])})\n")
        for item in results["errors"]:
            short = item["url"].replace(SITE_URL.rstrip("/"), "")
            lines.append(f"- {short} — {item['error']}")

    if results["inspected"]:
        lines.append(f"\n### Inspection Details\n")
        lines.append("| Page | Verdict | Index State | Last Crawl | Fetch State |")
        lines.append("|---|---|---|---|---|")
        for insp in results["inspected"]:
            short = insp["url"].replace(SITE_URL.rstrip("/"), "")
            crawl = insp["last_crawl_time"] or "Never"
            lines.append(
                f"| {short} | {insp['verdict']} | {insp['indexing_state']} | "
                f"{crawl} | {insp['page_fetch_state']} |"
            )

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
