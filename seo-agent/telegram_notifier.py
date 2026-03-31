"""
Telegram notification sender.

Sends SEO report summaries and PR approval requests via Telegram Bot API.
"""

import json
import os
import urllib.request
import urllib.parse

from config import SITE_URL


def get_bot_config():
    """Get Telegram bot token and chat ID from environment."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    return token, chat_id


def send_message(text, parse_mode="Markdown", reply_markup=None):
    """Send a text message via Telegram Bot API."""
    token, chat_id = get_bot_config()
    if not token or not chat_id:
        print("   ⚠ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping notification")
        return None

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"   ⚠ Telegram send failed: {e}")
        return None


def send_daily_report(analysis, report_url=None):
    """Send an actionable daily SEO summary with alerts and top opportunities."""
    summary = analysis["summary"] if isinstance(analysis, dict) and "summary" in analysis else analysis

    date_str = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    text = f"📊 *MK Painting — Daily SEO Report* ({date_str})\n\n"

    # ── Alerts ────────────────────────────────────────────────────────────────
    alerts = _build_alerts(summary, analysis if isinstance(analysis, dict) else {})
    if alerts:
        text += "⚠️ *Alerts:*\n"
        for alert in alerts:
            text += f"  • {alert}\n"
        text += "\n"

    # ── Core stats ────────────────────────────────────────────────────────────
    text += (
        f"📈 *Today's Data:*\n"
        f"  🔍 {summary['total_queries']} tracked queries\n"
        f"  👆 {summary['total_clicks']:,} click{'s' if summary['total_clicks'] != 1 else ''}"
        f"  |  👁 {summary['total_impressions']:,} impressions\n"
        f"  📍 Avg position {summary['avg_position']} | CTR {summary['avg_ctr']:.2%}\n\n"
    )

    # ── Top opportunities ─────────────────────────────────────────────────────
    opps = _build_top_opportunities(analysis if isinstance(analysis, dict) else {})
    if opps:
        text += "🎯 *Top Opportunities:*\n"
        for opp in opps[:3]:
            text += f"  • {opp}\n"
        text += "\n"

    # ── Trends ──────────────────────────────────────────────────────────────
    if isinstance(analysis, dict) and analysis.get("trends"):
        trends = analysis["trends"]
        if trends.get("previous_date"):
            trend_parts = []
            delta = trends.get("summary_delta")
            if delta:
                c_sign = "+" if delta["clicks_delta"] >= 0 else ""
                i_sign = "+" if delta["impressions_delta"] >= 0 else ""
                trend_parts.append(
                    f"vs {trends['previous_date']}: "
                    f"{c_sign}{delta['clicks_delta']} clicks, "
                    f"{i_sign}{delta['impressions_delta']} impressions"
                )

            improved = [c for c in trends.get("position_changes", []) if c["direction"] == "up"]
            declined = [c for c in trends.get("position_changes", []) if c["direction"] == "down"]
            if improved:
                best = improved[0]
                trend_parts.append(
                    f'Best mover: "{best["query"]}" '
                    f'{best["prev_position"]}→{best["position"]} (+{best["position_delta"]:.1f})'
                )
            if declined:
                worst = declined[0]
                trend_parts.append(
                    f'Biggest drop: "{worst["query"]}" '
                    f'{worst["prev_position"]}→{worst["position"]} ({worst["position_delta"]:.1f})'
                )

            nk = len(trends.get("new_keywords", []))
            if nk:
                trend_parts.append(f"{nk} new keyword(s) appeared")

            if trend_parts:
                text += "📉 *Trends:*\n"
                for tp in trend_parts:
                    text += f"  • {tp}\n"
                text += "\n"

    # ── Map Pack note ──────────────────────────────────────────────────────
    if isinstance(analysis, dict):
        mp = analysis.get("map_pack_queries", [])
        if mp:
            text += f"🗺 _{len(mp)} keyword(s) at pos 1\\-3 with 0 clicks — Map Pack dominated, focus GBP_\n"

    # ── Opportunity counts ────────────────────────────────────────────────────
    if isinstance(analysis, dict):
        sd = len(analysis.get("striking_distance", []))
        cg = len(analysis.get("ctr_gaps", []))
        zc = len(analysis.get("zero_click", []))
        if sd or cg or zc:
            text += f"_{sd} striking distance | {cg} CTR gaps | {zc} zero\\-click_\n"

    buttons = []
    if report_url:
        buttons.append([{"text": "📄 View Full Report", "url": report_url}])

    reply_markup = {"inline_keyboard": buttons} if buttons else None
    return send_message(text, reply_markup=reply_markup)


def _build_alerts(summary, analysis):
    """Return list of alert strings for abnormal conditions."""
    alerts = []

    # CTR well below healthy threshold
    if summary.get("avg_ctr", 1) < 0.003:
        alerts.append(f"Avg CTR {summary['avg_ctr']:.2%} — critically low")

    # Multiple position-1 keywords with 0% CTR
    zero_ctr_top = [
        q for q in summary.get("top_queries", [])
        if q.get("position", 99) <= 3 and q.get("clicks", 0) == 0 and q.get("impressions", 0) >= 30
    ]
    if zero_ctr_top:
        alerts.append(
            f"{len(zero_ctr_top)} keyword(s) rank top 3 with 0 clicks — title/meta needs work"
        )

    # Cannibalization detected
    cannibal = analysis.get("cannibalization", [])
    if cannibal:
        alerts.append(f"{len(cannibal)} keyword cannibalization issue(s) detected")

    return alerts


def _build_top_opportunities(analysis):
    """Return top 3 opportunity strings ranked by potential impact."""
    opps = []

    # CTR gaps — highest potential clicks
    for gap in sorted(analysis.get("ctr_gaps", []), key=lambda x: x.get("potential_clicks", 0), reverse=True)[:2]:
        opps.append(
            f'"{gap["query"]}" — pos {gap["position"]:.1f}, '
            f'+{gap["potential_clicks"]} potential clicks'
        )

    # Missing pages with most impressions
    for mp in analysis.get("missing_pages", [])[:1]:
        opps.append(
            f'"{mp["suburb"]} {mp["service"]}" — {mp["total_impressions"]} imp, no landing page'
        )

    # Highest striking distance keyword not already in CTR gaps
    ctr_gap_queries = {g["query"] for g in analysis.get("ctr_gaps", [])}
    for kw in analysis.get("striking_distance", []):
        if kw["query"] not in ctr_gap_queries:
            opps.append(
                f'"{kw["query"]}" — pos {kw["position"]:.1f}, {kw["impressions"]} imp'
            )
            break

    return opps[:3]


def send_pr_notification(pr_url, pr_number, changes_summary):
    """
    Send a PR notification with approve button.

    changes_summary: list of dicts with 'file', 'change_type', 'description'
    """
    text = (
        "🔧 *MK Painting — SEO Changes Ready*\n\n"
        "The SEO agent has prepared changes based on today's analysis:\n\n"
    )

    for change in changes_summary[:10]:
        emoji = {"title": "🏷", "meta": "📝", "content": "📄"}.get(change["change_type"], "✏️")
        text += f"{emoji} `{change['file']}` — {change['description']}\n"

    if len(changes_summary) > 10:
        text += f"\n_...and {len(changes_summary) - 10} more changes_\n"

    text += f"\n*PR #{pr_number}* is ready for review."

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Review & Approve", "url": pr_url},
                {"text": "📋 View Diff", "url": f"{pr_url}/files"},
            ]
        ]
    }

    return send_message(text, reply_markup=reply_markup)


def send_indexing_update(indexed_count, unindexed_pages):
    """Send indexing status update if there are unindexed pages."""
    if not unindexed_pages:
        return None

    text = (
        "🔎 *Indexing Status Update*\n\n"
        f"✅ {indexed_count} pages indexed\n"
        f"⏳ {len(unindexed_pages)} pages awaiting crawl:\n"
    )

    for page in unindexed_pages[:7]:
        short = page.get("url", "").replace(SITE_URL.rstrip("/"), "")
        text += f"  • `{short}`\n"

    text += "\n_Sitemap pinged — Google should crawl within a few days._"
    return send_message(text)


def send_new_page_notification(pr_url, pr_number, opportunity):
    """Send notification about a new landing page PR."""
    suburb = opportunity["suburb"].title()
    text = (
        "🆕 *MK Painting — New Landing Page Ready*\n\n"
        f"The SEO agent detected search demand for *{suburb}* "
        f"({opportunity['impressions']} impressions) and generated a new landing page.\n\n"
        f"📄 `{opportunity['filename']}`\n"
        f"🎯 Target: _{opportunity['keyword']}_\n"
    )

    queries = opportunity.get("top_queries", [])[:3]
    if queries:
        text += "\n*Top queries:*\n"
        for q in queries:
            text += f"  • _{q}_\n"

    text += f"\n*PR #{pr_number}* is ready for review."

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Review & Approve", "url": pr_url},
                {"text": "📋 View Page", "url": f"{pr_url}/files"},
            ]
        ]
    }

    return send_message(text, reply_markup=reply_markup)
