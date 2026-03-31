"""
Internal Anchor Text Optimizer.

Finds generic internal links and uses Claude to rewrite the
surrounding paragraph with exact-match, keyword-rich anchor text.
"""

import json
import os
import re
import anthropic

from config import CLAUDE_MODEL, EXISTING_PAGES, MAX_TOKENS, SITE_URL


WEAK_ANCHORS = {
    "click here", "read more", "learn more", "services",
    "contact us", "more details", "find out more", "here",
    "our services", "more info", "website", "link"
}

# Compiled once at module level for performance
_PARAGRAPH_PATTERN = re.compile(
    r"<p[^>]*>(.*?<a\s+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)

# Strip domain prefix for href normalisation
_DOMAIN_PREFIX = SITE_URL.rstrip("/")


def analyze_and_optimize_anchors(repo_root):
    """
    Scans all HTML files for weak anchor texts pointing to target pages.
    Sends them to Claude for NLP-based rewriting.
    Returns a list of change dicts to be applied via implementer.py.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ⚠ ANTHROPIC_API_KEY not set — skipping anchor optimization")
        return []

    # Walk the repo once and cache all HTML content
    html_files = {}
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for file in files:
            if file.endswith(".html"):
                filepath = os.path.join(root, file)
                rel_file = os.path.relpath(filepath, repo_root)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        html_files[rel_file] = f.read()
                except Exception:
                    pass

    weak_links_found = []

    for rel_file, content in html_files.items():
        for match in _PARAGRAPH_PATTERN.finditer(content):
            full_p_inner = match.group(1).strip()
            href = match.group(2).strip()
            anchor_text = match.group(3).strip()

            if anchor_text.lower().strip() not in WEAK_ANCHORS:
                continue

            # Normalise href to a slug
            normalized_href = href.replace(_DOMAIN_PREFIX, "")
            if not normalized_href.startswith("/"):
                normalized_href = "/" + normalized_href
            if normalized_href == "":
                normalized_href = "/"

            # Check if it points to a known page
            if normalized_href in EXISTING_PAGES:
                weak_links_found.append({
                    "file": rel_file,
                    "target_slug": normalized_href,
                    "target_keyword": EXISTING_PAGES[normalized_href],
                    "current_anchor": anchor_text,
                    "full_paragraph": f"<p>{full_p_inner}</p>",
                })

    if not weak_links_found:
        print("   → No weak anchor texts found across site paragraphs.")
        return []

    print(f"   → Found {len(weak_links_found)} weak internal links. Asking Claude to optimize...")
    return _ask_claude_to_rewrite(weak_links_found[:10], api_key)


def _ask_claude_to_rewrite(weak_links_batch, api_key):
    client = anthropic.Anthropic(api_key=api_key)

    links_text = []
    for i, link in enumerate(weak_links_batch):
        links_text.append(
            f"--- ITEM {i} ---\n"
            f"File: {link['file']}\n"
            f"Target URL: {link['target_slug']}\n"
            f"Target Keyword it SHOULD rank for: \"{link['target_keyword']}\"\n"
            f"Current Weak Anchor: \"{link['current_anchor']}\"\n"
            f"Full Paragraph HTML:\n```html\n{link['full_paragraph']}\n```\n"
        )

    system_prompt = (
        "You are an expert SEO internal linking agent. "
        "You will receive a list of HTML paragraphs containing 'weak' anchor text (like 'click here' or 'services'). "
        "Your task is to completely rewrite ONLY the paragraph's inner text so that the link anchor naturally contains the 'Target Keyword'.\n\n"
        "RULES:\n"
        "- Return ONLY a raw JSON array.\n"
        "- Each JSON object must have: 'file', 'change_type' (must be 'anchor_text'), 'old_value' (the EXACT original paragraph HTML you received), and 'new_value' (the rewritten paragraph HTML).\n"
        "- 'description' should briefly explain how the anchor text was improved.\n"
        "- Maintain all existing CSS classes or attributes on the <p> and <a> tags.\n"
        "- Make sure the text flows naturally and persuasively."
    )

    user_prompt = "Rewrite these paragraphs to fix the weak anchor texts:\n\n" + "\n".join(links_text)

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = message.content[0].text.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
            if m:
                text = m.group(1)

        start = text.find("[")
        end = text.rfind("]") + 1
        if start < 0 or end <= start:
            return []
        return json.loads(text[start:end])
    except json.JSONDecodeError as e:
        print(f"   ⚠ Failed to parse anchor optimization response: {e}")
        return []
    except Exception as e:
        print(f"   ⚠ Failed to optimize anchor text: {e}")
        return []
