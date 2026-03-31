"""
Internal Anchor Text Optimizer.

Finds generic internal links and uses Claude to rewrite the 
surrounding paragraph with exact-match, keyword-rich anchor text.
"""

import json
import os
import re
import anthropic

from config import CLAUDE_MODEL, EXISTING_PAGES, MAX_TOKENS


WEAK_ANCHORS = {
    "click here", "read more", "learn more", "services", 
    "contact us", "more details", "find out more", "here",
    "our services", "more info", "website", "link"
}

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

    weak_links_found = []

    # Regex to find <p>...</p> tags that contain <a href="...">...</a>
    # Note: this is a basic heuristic for paragraphs containing links
    paragraph_pattern = re.compile(r"<p[^>]*>(.*?<a\s+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>.*?)</p>", re.IGNORECASE | re.DOTALL)

    for slug, target_keyword in EXISTING_PAGES.items():
        # Iterate over all HTML files to find links pointing TO this slug
        for root, dirs, files in os.walk(repo_root):
            # purely prevent crawling into massive unknown dirs
            if ".git" in root or "__pycache__" in root:
                continue

            for file in files:
                if not file.endswith(".html"):
                    continue

                filepath = os.path.join(root, file)
                # Compute relative path for reporting
                rel_file = os.path.relpath(filepath, repo_root)

                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Find all paragraphs in this file
                for match in paragraph_pattern.finditer(content):
                    full_p_inner = match.group(1).strip()
                    href = match.group(2).strip()
                    anchor_text = match.group(3).strip()

                    # Check if this link points to our target slug
                    # Handle full URL, relative URL, or slug
                    # Also ensuring the slug matches exactly or ends with
                    normalized_href = href.replace("https://www.mandkpaintingservices.com.au", "")
                    if normalized_href == "" and slug == "/":
                        normalized_href = "/"
                    
                    if not normalized_href.startswith("/"):
                        normalized_href = "/" + normalized_href

                    if normalized_href == slug:
                        if anchor_text.lower().strip() in WEAK_ANCHORS:
                            # It's a weak link pointing to a known page!
                            weak_links_found.append({
                                "file": rel_file,
                                "target_slug": slug,
                                "target_keyword": target_keyword,
                                "current_anchor": anchor_text,
                                "full_paragraph": f"<p>{full_p_inner}</p>"
                            })

    if not weak_links_found:
        print("   → No weak anchor texts found across site paragraphs.")
        return []

    print(f"   → Found {len(weak_links_found)} weak internal links. Asking Claude to optimize...")

    # We batch them so Claude can do them in one go
    # Max out at 10 to avoid giant token/context size
    batch = weak_links_found[:10]
    
    return _ask_claude_to_rewrite(batch, api_key)


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
            # Strip markdown block
            import re
            match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
            if match:
                text = match.group(1)
        
        start = text.find("[")
        end = text.rfind("]") + 1
        return json.loads(text[start:end])
    except Exception as e:
        print(f"   ⚠ Failed to optimize anchor text: {e}")
        return []
