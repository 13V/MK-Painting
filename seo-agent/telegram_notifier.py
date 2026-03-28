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


def send_daily_report(summary, report_url=None):
    """Send a concise daily SEO performance summary."""
    text = (
        "📊 *MK Painting — Daily SEO Report*\n\n"
        f"🔍 *{summary['total_queries']}* tracked queries\n"
        f"👆 *{summary['total_clicks']:,}* clicks\n"
        f"👁 *{summary['total_impressions']:,}* impressions\n"
        f"📈 *{summary['avg_ctr']:.1%}* avg CTR\n"
        f"📍 *{summary['avg_position']}* avg position\n"
    )

    if summary.get("top_queries"):
        top = summary["top_queries"][:3]
        text += "\n*Top queries:*\n"
        for q in top:
            text += f"  • _{q['query']}_ — {q['clicks']} clicks, pos {q['position']}\n"

    buttons = []
    if report_url:
        buttons.append([{"text": "📄 View Full Report", "url": report_url}])

    reply_markup = {"inline_keyboard": buttons} if buttons else None
    return send_message(text, reply_markup=reply_markup)


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
