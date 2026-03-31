"""
Daily site health auditor.

Runs four automated checks on every agent run:
1. Schema geo-coordinate validation
2. FAQ quality (suburb mentions, answer length)
3. Image alt text (generic "Project N" patterns)
4. Sitemap freshness (missing entries, orphaned entries)
"""

import json
import os
import re

from config import EXISTING_PAGES, SITE_URL


# ── Correct coordinates per suburb slug ──────────────────────────────────────
SUBURB_COORDS = {
    "mawson-lakes":  (-34.7876, 138.6531),
    "gawler":        (-34.5983, 138.7528),
    "golden-grove":  (-34.7568, 138.7337),
    "west-lakes":    (-34.8722, 138.5041),
    "norwood":       (-34.9183, 138.6365),
    "wingfield":     (-34.8249, 138.5832),
    "grange":        (-34.9028, 138.5089),
    "salisbury":     (-34.7563, 138.6395),
    "burnside":      (-34.9400, 138.6700),
    "unley":         (-34.9534, 138.6000),
    "regency-park":  (-34.8350, 138.5790),
    "edwardstown":   (-34.9850, 138.5790),
    "findon":        (-34.9017, 138.5503),
    "semaphore":     (-34.8411, 138.4869),
    "prospect":      (-34.8912, 138.5996),
    "glenelg":       (-34.9800, 138.5160),
    "morphett-vale": (-35.1292, 138.5397),
}


def audit_schema_coords(repo_root):
    """
    Check LocalBusiness geo coordinates in all suburb HTML files.
    Returns list of change dicts for wrong coords (ready for apply_changes).
    """
    fixes = []

    for slug, slug_name in EXISTING_PAGES.items():
        # Derive the HTML filename slug (e.g. "/west-lakes.html" → "west-lakes")
        file_rel = slug.lstrip("/")
        if not file_rel or not file_rel.endswith(".html"):
            continue
        page_slug = file_rel.replace(".html", "")

        if page_slug not in SUBURB_COORDS:
            continue

        filepath = os.path.join(repo_root, file_rel)
        if not os.path.isfile(filepath):
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        expected_lat, expected_lng = SUBURB_COORDS[page_slug]

        lat_match = re.search(r'"latitude":\s*([-\d.]+)', content)
        lng_match = re.search(r'"longitude":\s*([-\d.]+)', content)

        if not lat_match or not lng_match:
            continue

        actual_lat = float(lat_match.group(1))
        actual_lng = float(lng_match.group(1))

        if abs(actual_lat - expected_lat) > 0.001 or abs(actual_lng - expected_lng) > 0.001:
            old_block = f'"latitude": {actual_lat},\n        "longitude": {actual_lng}'
            new_block = f'"latitude": {expected_lat},\n        "longitude": {expected_lng}'
            fixes.append({
                "file": file_rel,
                "change_type": "schema_coords",
                "old_value": old_block,
                "new_value": new_block,
                "description": (
                    f"Fix geo coords for {page_slug}: "
                    f"({actual_lat}, {actual_lng}) → ({expected_lat}, {expected_lng})"
                ),
            })

    return fixes


def audit_faq_quality(repo_root):
    """
    Check FAQ sections for suburb specificity and answer length.
    Returns list of issue strings for reporting (no auto-fix).
    """
    issues = []

    for slug in EXISTING_PAGES:
        file_rel = slug.lstrip("/")
        if not file_rel or not file_rel.endswith(".html"):
            continue
        page_slug = file_rel.replace(".html", "")
        suburb_name = page_slug.replace("-", " ")

        filepath = os.path.join(repo_root, file_rel)
        if not os.path.isfile(filepath):
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Find FAQ section
        faq_match = re.search(
            r'<section[^>]*class="[^"]*faq[^"]*"[^>]*>(.*?)</section>',
            content, re.IGNORECASE | re.DOTALL,
        )
        if not faq_match:
            continue

        faq_html = faq_match.group(1)

        # Count suburb mentions in FAQ
        suburb_count = len(re.findall(re.escape(suburb_name), faq_html, re.IGNORECASE))
        if suburb_count < 2 and suburb_name not in ("about", "blog", "contact", "privacy"):
            issues.append(
                f"`{file_rel}` FAQ: suburb '{suburb_name}' mentioned only {suburb_count}× "
                f"(target ≥2 for local relevance)"
            )

        # Check answer word counts
        answers = re.findall(
            r'<div[^>]*class="[^"]*faq-answer[^"]*"[^>]*>(.*?)</div>',
            faq_html, re.IGNORECASE | re.DOTALL,
        )
        for i, answer_html in enumerate(answers):
            # Strip tags and count words
            text = re.sub(r"<[^>]+>", " ", answer_html)
            words = len(text.split())
            if words < 80:
                issues.append(
                    f"`{file_rel}` FAQ answer #{i+1}: {words} words (target ≥80 for featured snippet)"
                )

    return issues


def audit_image_alts(repo_root):
    """
    Find images with generic alt text patterns.
    Returns list of (file, src, alt) tuples for reporting (no auto-fix).
    """
    GENERIC_PATTERNS = [
        re.compile(r"^(M&K Painting\s+)?Project\s+\d+$", re.IGNORECASE),
        re.compile(r"^Gallery (image|photo|pic)\s+\d+$", re.IGNORECASE),
        re.compile(r"^image\d+$", re.IGNORECASE),
        re.compile(r"^img\d+$", re.IGNORECASE),
        re.compile(r"^\.{0,5}$"),  # empty or dots only
    ]

    issues = []
    img_pattern = re.compile(r'<img[^>]+>', re.IGNORECASE)
    alt_pattern = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)
    src_pattern = re.compile(r'src=["\']([^"\']*)["\']', re.IGNORECASE)

    for slug in EXISTING_PAGES:
        file_rel = slug.lstrip("/")
        if not file_rel or not file_rel.endswith(".html"):
            continue

        filepath = os.path.join(repo_root, file_rel)
        if not os.path.isfile(filepath):
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        for img_tag in img_pattern.finditer(content):
            tag = img_tag.group(0)
            alt_m = alt_pattern.search(tag)
            src_m = src_pattern.search(tag)
            alt = alt_m.group(1).strip() if alt_m else ""
            src = src_m.group(1) if src_m else ""

            if any(p.match(alt) for p in GENERIC_PATTERNS):
                issues.append((file_rel, src, alt or "(empty)"))

    return issues


def audit_sitemap_freshness(repo_root):
    """
    Cross-check sitemap.xml against actual HTML files.
    Returns dict with 'missing' (in repo but not sitemap) and 'orphaned' (in sitemap but no file).
    """
    sitemap_path = os.path.join(repo_root, "sitemap.xml")
    if not os.path.isfile(sitemap_path):
        return {"missing": [], "orphaned": []}

    with open(sitemap_path, "r", encoding="utf-8") as f:
        sitemap = f.read()

    # Extract all <loc> URLs from sitemap
    loc_urls = set(re.findall(r"<loc>(.*?)</loc>", sitemap))
    sitemap_slugs = set()
    base = SITE_URL.rstrip("/")
    for url in loc_urls:
        slug = url.replace(base, "") or "/"
        sitemap_slugs.add(slug)

    # Find all HTML files in repo root (not in subdirs like seo-agent/)
    repo_html = set()
    for f in os.listdir(repo_root):
        if f.endswith(".html"):
            repo_html.add(f"/{f}")
    repo_html.add("/")  # homepage

    # Missing from sitemap
    missing = [slug for slug in repo_html if slug not in sitemap_slugs]

    # Orphaned in sitemap (no file)
    orphaned = []
    for slug in sitemap_slugs:
        if slug == "/":
            continue
        filepath = os.path.join(repo_root, slug.lstrip("/"))
        if not os.path.isfile(filepath):
            orphaned.append(slug)

    return {"missing": missing, "orphaned": orphaned}


def auto_repair_sitemap(repo_root):
    """
    Fix sitemap.xml: add missing pages, remove orphans, update stale lastmod dates.
    Returns list of change descriptions.
    """
    from datetime import datetime

    sitemap_path = os.path.join(repo_root, "sitemap.xml")
    if not os.path.isfile(sitemap_path):
        return []

    issues = audit_sitemap_freshness(repo_root)

    with open(sitemap_path, "r", encoding="utf-8") as f:
        content = f.read()

    today = datetime.now().strftime("%Y-%m-%d")
    changes = []
    base = SITE_URL.rstrip("/")

    # Pages we intentionally exclude from sitemap
    EXCLUDE = {"/seo-proposal.html"}

    # Remove orphaned entries
    for slug in issues["orphaned"]:
        url = f"{base}{slug}"
        pattern = re.compile(
            r"\s*<url>\s*<loc>" + re.escape(url) + r"</loc>.*?</url>",
            re.DOTALL,
        )
        content = pattern.sub("", content)
        changes.append(f"Removed orphaned: {slug}")

    # Add missing pages
    for slug in issues["missing"]:
        if slug in EXCLUDE:
            continue
        url = f"{base}{slug}" if slug != "/" else SITE_URL
        priority = "1.00" if slug == "/" else "0.80"
        entry = (
            f"  <url>\n"
            f"    <loc>{url}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>\n"
        )
        content = content.replace("</urlset>", f"{entry}</urlset>")
        changes.append(f"Added missing: {slug}")

    # Update stale lastmod dates based on file modification times
    for slug in EXISTING_PAGES:
        file_rel = slug.lstrip("/") or "index.html"
        filepath = os.path.join(repo_root, file_rel)
        if not os.path.isfile(filepath):
            continue
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d")
        url = f"{base}{slug}" if slug != "/" else SITE_URL
        match = re.search(
            r"<url>\s*<loc>" + re.escape(url) + r"</loc>\s*<lastmod>(\d{4}-\d{2}-\d{2})</lastmod>",
            content, re.DOTALL,
        )
        if match and match.group(1) < mtime:
            content = content.replace(
                f"<loc>{url}</loc>\n    <lastmod>{match.group(1)}</lastmod>",
                f"<loc>{url}</loc>\n    <lastmod>{mtime}</lastmod>",
            )
            changes.append(f"Updated lastmod: {slug} ({match.group(1)} → {mtime})")

    if changes:
        with open(sitemap_path, "w", encoding="utf-8") as f:
            f.write(content)

    return changes


def find_meta_length_issues(repo_root):
    """
    Find pages with too-long titles (>60 chars) or meta descriptions (>155 chars).
    Returns list of dicts with file, type, length, and current tag content.
    """
    issues = []

    for slug in EXISTING_PAGES:
        file_rel = slug.lstrip("/") or "index.html"
        if not file_rel.endswith(".html"):
            continue

        filepath = os.path.join(repo_root, file_rel)
        if not os.path.isfile(filepath):
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Check title length (decode &amp; → & for accurate char count)
        title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
        if title_match:
            title_raw = title_match.group(1).strip()
            title_display = title_raw.replace("&amp;", "&")
            if len(title_display) > 60:
                issues.append({
                    "file": file_rel,
                    "type": "title_too_long",
                    "length": len(title_display),
                    "current": title_match.group(0),
                })

        # Check meta description length
        meta_match = re.search(
            r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']',
            content, re.IGNORECASE,
        )
        if not meta_match:
            # Handle multi-line meta tags
            meta_match = re.search(
                r'<meta\s+name=["\']description["\']\s*\n\s*content=["\']([^"\']*)["\']',
                content, re.IGNORECASE,
            )
        if meta_match:
            meta_text = meta_match.group(1).strip().replace("&amp;", "&")
            if len(meta_text) > 155:
                issues.append({
                    "file": file_rel,
                    "type": "meta_too_long",
                    "length": len(meta_text),
                    "current": meta_text[:80] + "...",
                })

    return issues


def run_all_audits(repo_root):
    """Run all four audits and return combined results dict."""
    return {
        "coord_fixes": audit_schema_coords(repo_root),
        "faq_issues": audit_faq_quality(repo_root),
        "alt_issues": audit_image_alts(repo_root),
        "sitemap_issues": audit_sitemap_freshness(repo_root),
    }
