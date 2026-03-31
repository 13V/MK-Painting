"""
SEO report generator.

Takes analysis results and uses the Claude API to produce
an actionable markdown report with intelligent recommendations.
"""

import os
from datetime import datetime

import anthropic

from config import CLAUDE_MODEL, EXISTING_PAGES, MAX_TOKENS, SITE_URL


def generate_report(analysis, use_claude=True):
    """
    Generate a full markdown SEO report.

    If use_claude=True, sends analysis to Claude for intelligent recommendations.
    Otherwise, generates a data-only report (useful when API key is unavailable).
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_parts = [
        f"# MK Painting SEO Report — {date_str}\n",
        _format_summary(analysis["summary"]),
        _format_striking_distance(analysis["striking_distance"]),
        _format_ctr_gaps(analysis["ctr_gaps"]),
        _format_zero_click(analysis["zero_click"]),
        _format_missing_pages(analysis["missing_pages"]),
        _format_suburb_opportunities(analysis["suburb_opportunities"]),
        _format_cannibalization(analysis.get("cannibalization", [])),
        _format_trends(analysis.get("trends")),
        _format_map_pack(analysis.get("map_pack_queries", [])),
        _format_ga4(analysis.get("ga4")),
    ]

    if use_claude:
        ai_section = _get_claude_recommendations(analysis)
        report_parts.append(ai_section)

    report_parts.append(f"\n---\n*Generated {date_str} by MK Painting SEO Agent*\n")

    return "\n".join(report_parts)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _esc(text):
    """Escape pipe characters so they don't break markdown tables."""
    return str(text).replace("|", "\\|")


# ── Section formatters ───────────────────────────────────────────────────────


def _format_summary(summary):
    lines = [
        "## Performance Summary\n",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total Clicks | {summary['total_clicks']:,} |",
        f"| Total Impressions | {summary['total_impressions']:,} |",
        f"| Average CTR | {summary['avg_ctr']:.1%} |",
        f"| Average Position | {summary['avg_position']} |",
        f"| Tracked Queries | {summary['total_queries']} |",
        f"| Tracked Pages | {summary['total_pages']} |",
        "",
        "### Top Pages by Clicks\n",
        "| Page | Clicks | Impressions | CTR | Position |",
        "|---|---|---|---|---|",
    ]
    for p in summary["top_pages"][:10]:
        page_short = p["page"].replace(SITE_URL, "/")
        lines.append(
            f"| {page_short} | {p['clicks']} | {p['impressions']} | {p['ctr']:.1%} | {p['position']} |"
        )

    lines.extend([
        "",
        "### Top Queries by Clicks\n",
        "| Query | Clicks | Impressions | CTR | Position |",
        "|---|---|---|---|---|",
    ])
    for q in summary["top_queries"][:10]:
        lines.append(
            f"| {_esc(q['query'])} | {q['clicks']} | {q['impressions']} | {q['ctr']:.1%} | {q['position']} |"
        )

    return "\n".join(lines) + "\n"


def _format_striking_distance(keywords):
    if not keywords:
        return "## Striking Distance Keywords\n\nNo striking distance opportunities found.\n"

    lines = [
        "## Striking Distance Keywords (Position 4–15)\n",
        "These keywords are close to page 1 / top 3. Small improvements can unlock significant traffic.\n",
        "| Query | Position | Impressions | Clicks | CTR | Action |",
        "|---|---|---|---|---|---|",
    ]
    for kw in keywords[:20]:
        lines.append(
            f"| {_esc(kw['query'])} | {kw['position']} | {kw['impressions']} | "
            f"{kw['clicks']} | {kw['ctr']:.1%} | {_esc(kw['action'])} |"
        )

    return "\n".join(lines) + "\n"


def _format_ctr_gaps(gaps):
    if not gaps:
        return "## CTR Gaps\n\nNo significant CTR gaps found.\n"

    lines = [
        "## CTR Gaps\n",
        "Keywords where CTR is significantly below benchmark for their position. "
        "Title tag and meta description rewrites needed.\n",
        "| Query | Position | Actual CTR | Expected CTR | Gap | Potential Clicks | Action |",
        "|---|---|---|---|---|---|---|",
    ]
    for g in gaps[:15]:
        lines.append(
            f"| {_esc(g['query'])} | {g['position']} | {g['ctr']:.1%} | "
            f"{g['expected_ctr']:.0%} | {g['ctr_gap']:.1%} | "
            f"+{g['potential_clicks']} | {_esc(g['action'])} |"
        )

    return "\n".join(lines) + "\n"


def _format_zero_click(items):
    if not items:
        return "## Zero-Click Queries\n\nNo high-impression zero-click queries found.\n"

    lines = [
        "## Zero-Click Queries\n",
        "Queries with significant impressions but almost no clicks — pure wasted visibility.\n",
        "| Query | Impressions | Clicks | Position | Action |",
        "|---|---|---|---|---|",
    ]
    for item in items[:15]:
        lines.append(
            f"| {_esc(item['query'])} | {item['impressions']} | {item['clicks']} | "
            f"{item['position']} | {_esc(item['action'])} |"
        )

    return "\n".join(lines) + "\n"


def _format_cannibalization(cannibalizations):
    if not cannibalizations:
        return ""

    lines = [
        "## ⚠️ Keyword Cannibalization Alerts\n",
        "When multiple pages rank for the same exact term, Google splits your authority. Point the 'Loser Pages' canonical tag to the 'Winner', or de-optimize the loser.\n",
        "| Query | Competing Pages | Total Imp. | Winner Page | Loser Pages |",
        "|---|---|---|---|---|",
    ]
    for c in cannibalizations[:10]:
        losers = "<br>".join(f"`{p.replace(SITE_URL, '/')}`" for p in c["loser_pages"])
        lines.append(
            f"| {_esc(c['query'])} | {c['competing_pages']} | {c['total_impressions']} | "
            f"`{c['winner_page'].replace(SITE_URL, '/')}` | {losers} |"
        )

    return "\n".join(lines) + "\n"


def _format_missing_pages(gaps):
    if not gaps:
        return "## Missing Landing Pages\n\nNo landing page gaps detected.\n"

    lines = [
        "## Missing Landing Pages\n",
        "Service × suburb combinations with search demand but no dedicated page.\n",
        "| Service | Suburb | Impressions | Clicks | Queries | Suggested Page |",
        "|---|---|---|---|---|---|",
    ]
    for g in gaps[:15]:
        lines.append(
            f"| {g['service']} | {g['suburb']} | {g['total_impressions']} | "
            f"{g['total_clicks']} | {g['query_count']} | `{g['suggested_page']}` |"
        )

    return "\n".join(lines) + "\n"


def _format_suburb_opportunities(suburbs):
    if not suburbs:
        return "## Suburb Expansion Opportunities\n\nNo tier-2 suburb opportunities detected.\n"

    lines = [
        "## Suburb Expansion Opportunities\n",
        "Tier-2 suburbs with search demand but no dedicated landing page.\n",
        "| Suburb | Impressions | Clicks | Queries | Top Search Terms |",
        "|---|---|---|---|---|",
    ]
    for s in suburbs[:15]:
        top = ", ".join(s["top_queries"][:3])
        lines.append(
            f"| {s['suburb'].title()} | {s['impressions']} | {s['clicks']} | "
            f"{s['query_count']} | {top} |"
        )

    return "\n".join(lines) + "\n"


def _format_trends(trends):
    if not trends or not trends.get("previous_date"):
        return ""

    lines = [
        f"## Trends (vs {trends['previous_date']})\n",
    ]

    # Summary delta
    delta = trends.get("summary_delta")
    if delta:
        lines.append(
            f"**Period change:** Clicks {delta['clicks_delta']:+d} | "
            f"Impressions {delta['impressions_delta']:+d}\n"
        )

    # Position changes
    changes = trends.get("position_changes", [])
    if changes:
        improved = [c for c in changes if c["direction"] == "up"]
        declined = [c for c in changes if c["direction"] == "down"]

        if improved:
            lines.append("### Improved Positions\n")
            lines.append("| Query | Position | Change | Impressions |")
            lines.append("|---|---|---|---|")
            for c in improved[:10]:
                lines.append(
                    f"| {_esc(c['query'])} | {c['position']} | "
                    f"{c['prev_position']} → {c['position']} (+{c['position_delta']:.1f}) | "
                    f"{c['impressions']} |"
                )
            lines.append("")

        if declined:
            lines.append("### Declined Positions\n")
            lines.append("| Query | Position | Change | Impressions |")
            lines.append("|---|---|---|---|")
            for c in declined[:10]:
                lines.append(
                    f"| {_esc(c['query'])} | {c['position']} | "
                    f"{c['prev_position']} → {c['position']} ({c['position_delta']:.1f}) | "
                    f"{c['impressions']} |"
                )
            lines.append("")

    # New keywords
    new_kws = trends.get("new_keywords", [])
    if new_kws:
        lines.append(f"### New Keywords ({len(new_kws)})\n")
        for kw in new_kws[:10]:
            lines.append(f"- \"{kw['query']}\" — pos {kw['position']}, {kw['impressions']} imp")
        lines.append("")

    return "\n".join(lines) + "\n"


def _format_map_pack(map_pack_queries):
    if not map_pack_queries:
        return ""

    lines = [
        "## Map Pack Dominated Queries\n",
        "These queries rank position 1-3 organically but get 0 clicks because the Google Maps "
        "3-Pack absorbs all traffic. Title/meta optimization won't help — focus on Google Business "
        "Profile instead (reviews, posts, photos).\n",
        "| Query | Position | Impressions | Note |",
        "|---|---|---|---|",
    ]
    for q in map_pack_queries[:10]:
        lines.append(
            f"| {_esc(q['query'])} | {q['position']} | {q['impressions']} | GBP focus |"
        )

    return "\n".join(lines) + "\n"


def _format_ga4(ga4_data):
    if not ga4_data:
        return ""

    lines = [
        f"## GA4 Engagement & Conversions (Last {ga4_data['period_days']} Days)\n",
        "| Metric | Value |",
        "|---|---|",
        f"| Total Sessions | {ga4_data['total_sessions']:,} |",
        f"| Total Users | {ga4_data['total_users']:,} |",
        f"| Organic Sessions | {ga4_data['organic_sessions']:,} |",
        f"| Phone Call Clicks | {ga4_data['phone_clicks']} |",
    ]

    # Traffic sources
    sources = ga4_data.get("traffic_sources", [])
    if sources:
        lines.extend([
            "",
            "### Traffic Sources\n",
            "| Channel | Sessions | Phone Clicks |",
            "|---|---|---|",
        ])
        for s in sources:
            lines.append(f"| {s['channel']} | {s['sessions']} | {s['key_events']} |")

    # Top pages
    pages = ga4_data.get("top_pages", [])
    if pages:
        lines.extend([
            "",
            "### Top Pages by Sessions\n",
            "| Page | Sessions | Users | Phone Clicks |",
            "|---|---|---|---|",
        ])
        for p in pages:
            lines.append(f"| {p['page']} | {p['sessions']} | {p['users']} | {p['key_events']} |")

    return "\n".join(lines) + "\n"


def format_site_audit(audit_results):
    """Format the four daily site health audit checks as a markdown section."""
    if not audit_results:
        return ""

    coord_fixes = audit_results.get("coord_fixes", [])
    faq_issues = audit_results.get("faq_issues", [])
    alt_issues = audit_results.get("alt_issues", [])
    sitemap = audit_results.get("sitemap_issues", {})
    missing_sm = sitemap.get("missing", [])
    orphaned_sm = sitemap.get("orphaned", [])

    total = len(coord_fixes) + len(faq_issues) + len(alt_issues) + len(missing_sm) + len(orphaned_sm)
    if total == 0:
        return "\n## Site Health Audit\n\n✅ All checks passed — no issues found.\n"

    lines = ["\n## Site Health Audit\n"]

    # Schema coord fixes
    if coord_fixes:
        lines.append(f"### Schema Coordinate Fixes ({len(coord_fixes)} auto-applied)\n")
        for fix in coord_fixes:
            lines.append(f"- `{fix['file']}` — {fix['description']}")
        lines.append("")
    else:
        lines.append("### Schema Coordinates\n\n✅ All geo coordinates correct.\n")

    # FAQ quality
    if faq_issues:
        lines.append(f"### FAQ Quality Issues ({len(faq_issues)})\n")
        for issue in faq_issues[:10]:
            lines.append(f"- {issue}")
        if len(faq_issues) > 10:
            lines.append(f"- _...and {len(faq_issues) - 10} more_")
        lines.append("")
    else:
        lines.append("### FAQ Quality\n\n✅ All FAQ sections pass suburb mention and length checks.\n")

    # Image alt text
    if alt_issues:
        lines.append(f"### Generic Image Alt Text ({len(alt_issues)} images)\n")
        lines.append("| File | Image src | Current alt |")
        lines.append("|---|---|---|")
        for file_rel, src, alt in alt_issues[:10]:
            src_short = src.split("/")[-1] if "/" in src else src
            lines.append(f"| `{file_rel}` | `{src_short}` | `{alt}` |")
        if len(alt_issues) > 10:
            lines.append(f"\n_...and {len(alt_issues) - 10} more_")
        lines.append("")
    else:
        lines.append("### Image Alt Text\n\n✅ No generic alt text patterns found.\n")

    # Sitemap freshness
    if missing_sm or orphaned_sm:
        lines.append(f"### Sitemap Freshness\n")
        if missing_sm:
            lines.append(f"**Missing from sitemap ({len(missing_sm)}):**")
            for slug in missing_sm:
                lines.append(f"- `{slug}`")
            lines.append("")
        if orphaned_sm:
            lines.append(f"**Orphaned sitemap entries ({len(orphaned_sm)}):**")
            for slug in orphaned_sm:
                lines.append(f"- `{slug}` — file not found")
            lines.append("")
    else:
        lines.append("### Sitemap Freshness\n\n✅ Sitemap matches all HTML files.\n")

    return "\n".join(lines)


# ── Claude AI recommendations ───────────────────────────────────────────────


def _get_claude_recommendations(analysis):
    """Send analysis data to Claude for intelligent SEO recommendations."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ⚠ ANTHROPIC_API_KEY not set — skipping AI recommendations")
        return ""

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = _build_system_prompt()
    user_prompt = _build_analysis_prompt(analysis)

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    ai_text = message.content[0].text
    return f"## AI Recommendations\n\n{ai_text}\n"


def _build_system_prompt():
    existing = "\n".join(f"- `{slug}` → {kw}" for slug, kw in EXISTING_PAGES.items())

    return f"""You are the SEO Growth Agent for M&K Painting Services, a residential and commercial painting company in Adelaide, South Australia.

Website: {SITE_URL}

Existing landing pages:
{existing}

Your job is to analyze Google Search Console data and provide specific, actionable recommendations to increase organic traffic. Focus on:
1. Title tag and meta description rewrites for CTR improvement
2. Content optimizations for striking distance keywords
3. New landing page recommendations for content gaps
4. Quick wins that can be implemented this week

Be specific — include exact title tag suggestions, mention specific pages and keywords by name. No generic SEO advice. Every recommendation must reference actual data from the analysis."""


def _build_analysis_prompt(analysis):
    parts = ["Here is the latest GSC analysis for M&K Painting Services:\n"]

    # Summary
    s = analysis["summary"]
    parts.append(f"**Performance**: {s['total_clicks']} clicks, {s['total_impressions']} impressions, {s['avg_ctr']:.1%} CTR, avg position {s['avg_position']}")

    # Striking distance
    sd = analysis["striking_distance"][:10]
    if sd:
        parts.append(f"\n**Striking Distance Keywords** ({len(analysis['striking_distance'])} total):")
        for kw in sd:
            parts.append(f"- \"{kw['query']}\" — pos {kw['position']}, {kw['impressions']} imp, {kw['clicks']} clicks")

    # CTR gaps
    ctr = analysis["ctr_gaps"][:10]
    if ctr:
        parts.append(f"\n**CTR Gaps** ({len(analysis['ctr_gaps'])} total):")
        for g in ctr:
            parts.append(f"- \"{g['query']}\" — pos {g['position']}, CTR {g['ctr']:.1%} vs expected {g['expected_ctr']:.0%}, +{g['potential_clicks']} potential clicks")

    # Zero click
    zc = analysis["zero_click"][:5]
    if zc:
        parts.append(f"\n**Zero-Click Queries** ({len(analysis['zero_click'])} total):")
        for z in zc:
            parts.append(f"- \"{z['query']}\" — {z['impressions']} impressions, {z['clicks']} clicks")

    # Missing pages
    mp = analysis["missing_pages"][:10]
    if mp:
        parts.append(f"\n**Missing Landing Pages** ({len(analysis['missing_pages'])} total):")
        for g in mp:
            parts.append(f"- {g['service']} × {g['suburb']} — {g['total_impressions']} imp, {g['total_clicks']} clicks")

    # Suburb opportunities
    so = analysis["suburb_opportunities"][:5]
    if so:
        parts.append(f"\n**Suburb Expansion** ({len(analysis['suburb_opportunities'])} total):")
        for sub in so:
            parts.append(f"- {sub['suburb'].title()} — {sub['impressions']} imp, {sub['clicks']} clicks")

    # Cannibalization
    can = analysis.get("cannibalization", [])[:5]
    if can:
        parts.append(f"\n**Keyword Cannibalization Alerts** ({len(analysis.get('cannibalization', []))} total):")
        for c in can:
            parts.append(f"- \"{c['query']}\" has {c['competing_pages']} competing pages. Winner: {c['winner_page']}")

    parts.append("\n---\nProvide your analysis as:\n1. **Top 3 Wins This Week** — the highest-impact actions to take immediately\n2. **Title Tag Rewrites** — specific <title> suggestions for underperforming pages\n3. **Map Pack Strategy** — quick tips for local map ranking based on current data\n4. **Cannibalization Fixes** — how to resolve any detected URL competition\n5. **New Page Recommendations** — which landing pages to create next")

    return "\n".join(parts)
