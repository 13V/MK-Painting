"""
Google Business Profile (GBP) Auto-Poster.

Uses the Google My Business API to automatically generate and publish
location-specific SEO updates and call-to-action posts to the Local Map Pack.
Driving consistent map activity boosts local pack rankings.
"""

import json
import os
import random
import datetime

import anthropic

from config import CLAUDE_MODEL, SITE_URL, SERVICES, SUBURBS_TIER1


def _get_gbp_credentials():
    """Get service account credentials with GBP scope."""
    from google.oauth2 import service_account

    creds_json = os.environ.get("GSC_CREDENTIALS_JSON")
    if not creds_json:
        creds_path = os.environ.get("GSC_CREDENTIALS_PATH", "credentials.json")
        if not os.path.exists(creds_path):
            raise FileNotFoundError("No Google credentials found.")
        with open(creds_path, "r", encoding="utf-8") as f:
            creds_json = f.read()

    creds_info = json.loads(creds_json)
    return service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/business.manage"],
    )


def generate_gbp_post(target_suburb=None, target_service=None, target_keyword=None):
    """Use Claude to generate a localized, persuasive Map Pack post.

    If target_suburb/service/keyword are provided (from GSC data), use them
    for maximum relevance. Otherwise falls back to random selection.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)

    service = target_service or random.choice(list(SERVICES.keys()))
    suburb = target_suburb or random.choice(SUBURBS_TIER1)

    # UTM-tracked CTA URL for measuring GBP click-through
    cta_url = f"{SITE_URL}?utm_source=gbp&utm_medium=post&utm_campaign=seo-agent"

    keyword_hint = ""
    if target_keyword:
        keyword_hint = f"\nTarget keyword to naturally include: \"{target_keyword}\""

    prompt = f"""Write a highly engaging, SEO-optimized Google Business Profile update post for M&K Painting Services.
Target Service: {service.title()} Painting
Target Suburb: {suburb.title()}, Adelaide{keyword_hint}

RULES:
1. Max 1400 characters (strictly).
2. Write as if you just completed a great project locally. Mention {suburb.title()} specifically to build hyper-local relevance.
3. Must end with a clear Call to Action: "Call us at 0405 352 932 or visit {cta_url} to get a free quote."
4. Output ONLY the raw post body text. No markdown formatting, no emojis unless highly relevant, and NO explanation.
"""

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"   ⚠ Claude API Error during GBP post generation: {e}")
        return None


def _pick_gbp_target(analysis):
    """Pick the best suburb/service/keyword to target based on GSC data.

    Prioritizes: highest-impression zero-click queries for suburbs we serve.
    """
    if not analysis or not isinstance(analysis, dict):
        return None, None, None

    # Look at zero-click queries for suburb-specific targeting
    zero_click = analysis.get("zero_click", [])
    map_pack = analysis.get("map_pack_queries", [])

    # Combine map pack + zero click, sort by impressions
    candidates = sorted(
        zero_click + map_pack,
        key=lambda q: q.get("impressions", 0),
        reverse=True,
    )

    for q in candidates:
        query = q["query"].lower()
        # Find if a tier-1 suburb is mentioned
        for suburb in SUBURBS_TIER1:
            if suburb in query:
                # Try to detect the service
                for svc, keywords in SERVICES.items():
                    if any(kw in query for kw in keywords):
                        return suburb, svc, q["query"]
                return suburb, None, q["query"]

    return None, None, None


def publish_gbp_post(repo_root, analysis=None):
    """Generate and push a post to Google Business Profile."""
    print("\n📍 Preparing Google Business Profile (Map Pack) Update...")
    suburb, service, keyword = _pick_gbp_target(analysis)
    if suburb:
        print(f"   → Data-driven target: {suburb.title()} / {keyword or 'general'}")
    post_text = generate_gbp_post(target_suburb=suburb, target_service=service, target_keyword=keyword)
    if not post_text:
        print("   ⚠ Failed to generate GBP post.")
        return False

    preview = post_text[:75].replace('\n', ' ')
    print(f"   → Generated Post: \"{preview}...\"")

    # Always save a draft for the record
    draft_path = os.path.join(
        repo_root, "reports",
        f"gbp_draft_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.txt"
    )
    os.makedirs(os.path.dirname(draft_path), exist_ok=True)
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(post_text)
    print(f"   ✓ Draft saved to {os.path.relpath(draft_path, repo_root)}")

    account_id = os.environ.get("GBP_ACCOUNT_ID")
    location_id = os.environ.get("GBP_LOCATION_ID")

    if not account_id or not location_id:
        print("   ⚠ GBP_ACCOUNT_ID or GBP_LOCATION_ID not set — draft saved, skipping live publish.")
        return False

    try:
        from google.auth.transport.requests import AuthorizedSession

        credentials = _get_gbp_credentials()
        session = AuthorizedSession(credentials)

        url = (
            f"https://mybusiness.googleapis.com/v4/"
            f"accounts/{account_id}/locations/{location_id}/localPosts"
        )
        body = {
            "languageCode": "en-AU",
            "summary": post_text,
            "callToAction": {
                "actionType": "CALL",
            },
            "topicType": "STANDARD",
        }

        print("   → Pushing post to Google Business Profile API...")
        response = session.post(url, json=body)
        response.raise_for_status()

        data = response.json()
        post_name = data.get("name", "unknown")
        print(f"   ✓ Published successfully! Post: {post_name}")
        return True

    except Exception as e:
        print(f"   ⚠ Google Business Profile API Error: {e}")
        print("   → Draft saved — publish manually if needed.")
        return False
