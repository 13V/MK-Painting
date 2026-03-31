"""
SEO data analyzer.

Takes raw GSC data and produces structured opportunity findings:
- Striking distance keywords
- CTR optimization opportunities
- Service × suburb clusters
- Missing landing page gaps
"""

import re

from config import (
    ALL_SUBURBS,
    CTR_BENCHMARKS,
    EXISTING_PAGES,
    MISSING_PAGE_MIN_IMPRESSIONS,
    SERVICES,
    SITE_URL,
    STRIKING_DISTANCE_MAX,
    STRIKING_DISTANCE_MIN,
    STRIKING_DISTANCE_MIN_IMPRESSIONS,
    SUBURBS_TIER1,
    SUBURBS_TIER2,
)

# Pre-compile word-boundary patterns for all suburbs and service keywords
_SUBURB_PATTERNS = {
    suburb: re.compile(r"\b" + re.escape(suburb) + r"\b", re.IGNORECASE)
    for suburb in ALL_SUBURBS
}
_SERVICE_PATTERNS = {
    service: [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in kws]
    for service, kws in SERVICES.items()
}


def find_striking_distance(query_data):
    """
    Find keywords at positions 4-15 with meaningful impressions.
    These are the easiest to push to page 1 / top 3.

    Returns list sorted by impressions (highest opportunity first).
    """
    results = []
    for row in query_data:
        pos = row["position"]
        if (
            STRIKING_DISTANCE_MIN <= pos <= STRIKING_DISTANCE_MAX
            and row["impressions"] >= STRIKING_DISTANCE_MIN_IMPRESSIONS
        ):
            results.append({
                **row,
                "opportunity": "striking_distance",
                "action": _suggest_action(row),
            })

    return sorted(results, key=lambda r: r["impressions"], reverse=True)


def find_ctr_gaps(query_data):
    """
    Find keywords where CTR is below the expected benchmark for their position.
    These need title tag / meta description optimization.

    Returns list sorted by wasted clicks potential (highest first).
    """
    results = []
    for row in query_data:
        pos = row["position"]
        expected_ctr = _get_expected_ctr(pos)
        actual_ctr = row["ctr"]

        if expected_ctr and actual_ctr < expected_ctr * 0.6:  # >40% below benchmark
            wasted = int(row["impressions"] * (expected_ctr - actual_ctr))
            results.append({
                **row,
                "opportunity": "ctr_gap",
                "expected_ctr": expected_ctr,
                "ctr_gap": round(expected_ctr - actual_ctr, 4),
                "potential_clicks": wasted,
                "action": f"Rewrite title/meta for '{row['query']}' — "
                          f"current CTR {actual_ctr:.1%} vs expected {expected_ctr:.0%}",
            })

    return sorted(results, key=lambda r: r["potential_clicks"], reverse=True)


def find_high_impression_zero_click(query_data):
    """
    Find queries with significant impressions but 0-1 clicks.
    Pure wasted visibility.
    """
    results = []
    for row in query_data:
        if row["impressions"] >= 50 and row["clicks"] <= 1:
            results.append({
                **row,
                "opportunity": "zero_click",
                "action": f"'{row['query']}' gets {row['impressions']} impressions "
                          f"but only {row['clicks']} clicks — needs snippet optimization or dedicated page",
            })

    return sorted(results, key=lambda r: r["impressions"], reverse=True)


def cluster_by_service_suburb(query_data):
    """
    Group queries into service × suburb clusters.
    Identifies which intersections have search demand.

    Returns dict: {(service, suburb): [queries]}
    """
    clusters = {}

    for row in query_data:
        query = row["query"].lower()
        detected_services = _detect_services(query)
        detected_suburbs = _detect_suburbs(query)

        for service in detected_services:
            for suburb in detected_suburbs:
                key = (service, suburb)
                if key not in clusters:
                    clusters[key] = []
                clusters[key].append(row)

    # Sort clusters by total impressions
    return dict(
        sorted(
            clusters.items(),
            key=lambda item: sum(r["impressions"] for r in item[1]),
            reverse=True,
        )
    )


def find_missing_pages(clusters):
    """
    From service × suburb clusters, identify combos that have search demand
    but no dedicated landing page.

    Returns list of gap opportunities sorted by total impressions.
    """
    existing_slugs = set(EXISTING_PAGES.keys())
    gaps = []

    for (service, suburb), queries in clusters.items():
        total_impressions = sum(q["impressions"] for q in queries)
        total_clicks = sum(q["clicks"] for q in queries)

        # Check if a landing page exists for this combo
        has_page = False
        for slug in existing_slugs:
            slug_lower = slug.lower()
            suburb_slug = suburb.replace(" ", "-")
            if suburb_slug in slug_lower or (suburb in SUBURBS_TIER1 and suburb_slug in slug_lower):
                has_page = True
                break

        if not has_page and total_impressions >= MISSING_PAGE_MIN_IMPRESSIONS:
            gaps.append({
                "service": service,
                "suburb": suburb,
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "query_count": len(queries),
                "top_queries": [q["query"] for q in queries[:5]],
                "suggested_page": f"/{suburb.replace(' ', '-')}-{service.replace(' ', '-')}.html",
                "suggested_title": f"{service.title()} {suburb.title()} | M&K Painting Services",
            })

    return sorted(gaps, key=lambda g: g["total_impressions"], reverse=True)


def find_suburb_opportunities(query_data):
    """
    Find suburbs with high impressions but no dedicated landing page.
    Independent of service — pure geographic opportunity.
    """
    suburb_impressions = {}

    for row in query_data:
        query = row["query"].lower()
        for suburb in SUBURBS_TIER2:  # Only check tier 2 (no page yet)
            if _SUBURB_PATTERNS[suburb].search(query):
                if suburb not in suburb_impressions:
                    suburb_impressions[suburb] = {
                        "impressions": 0,
                        "clicks": 0,
                        "queries": [],
                    }
                suburb_impressions[suburb]["impressions"] += row["impressions"]
                suburb_impressions[suburb]["clicks"] += row["clicks"]
                suburb_impressions[suburb]["queries"].append(row["query"])

    results = []
    for suburb, data in suburb_impressions.items():
        if data["impressions"] >= 20:
            results.append({
                "suburb": suburb,
                "impressions": data["impressions"],
                "clicks": data["clicks"],
                "query_count": len(data["queries"]),
                "top_queries": data["queries"][:5],
            })

    return sorted(results, key=lambda r: r["impressions"], reverse=True)


def generate_summary_stats(query_data, page_data):
    """Generate high-level performance summary."""
    total_clicks = sum(r["clicks"] for r in query_data)
    total_impressions = sum(r["impressions"] for r in query_data)
    avg_ctr = total_clicks / total_impressions if total_impressions else 0
    avg_position = (
        sum(r["position"] * r["impressions"] for r in query_data) / total_impressions
        if total_impressions
        else 0
    )

    top_pages = sorted(page_data, key=lambda r: r["clicks"], reverse=True)[:10]
    top_queries = sorted(query_data, key=lambda r: r["clicks"], reverse=True)[:10]

    return {
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr": round(avg_ctr, 4),
        "avg_position": round(avg_position, 1),
        "total_queries": len(query_data),
        "total_pages": len(page_data),
        "top_pages": top_pages,
        "top_queries": top_queries,
    }


def detect_cannibalization(query_page_data):
    """
    Find queries where impressions are split across multiple pages.
    Google gets confused when two pages compete for the exact same term.
    """
    if not query_page_data:
        return []
        
    query_map = {}
    for row in query_page_data:
        q = row["query"]
        if q not in query_map:
            query_map[q] = []
        query_map[q].append(row)
        
    results = []
    for q, rows in query_map.items():
        valid_pages = [r for r in rows if r["impressions"] >= 15]
        if len(valid_pages) > 1:
            total_imp = sum(r["impressions"] for r in valid_pages)
            if total_imp >= 50:
                valid_pages.sort(key=lambda x: (x["clicks"], x["impressions"]), reverse=True)
                winner = valid_pages[0]
                losers = valid_pages[1:]
                results.append({
                    "query": q,
                    "total_impressions": total_imp,
                    "competing_pages": len(valid_pages),
                    "winner_page": winner["page"],
                    "loser_pages": [l["page"] for l in losers],
                    "action": f"De-optimize or canonicalize {len(losers)} competing page(s) pointing to {winner['page']}."
                })
                
    return sorted(results, key=lambda x: x["total_impressions"], reverse=True)


def run_full_analysis(query_data, page_data, query_page_data=None):
    """
    Run the complete analysis pipeline and return all findings.
    """
    clusters = cluster_by_service_suburb(query_data)
    return {
        "summary": generate_summary_stats(query_data, page_data),
        "striking_distance": find_striking_distance(query_data),
        "ctr_gaps": find_ctr_gaps(query_data),
        "zero_click": find_high_impression_zero_click(query_data),
        "clusters": clusters,
        "missing_pages": find_missing_pages(clusters),
        "suburb_opportunities": find_suburb_opportunities(query_data),
        "cannibalization": detect_cannibalization(query_page_data),
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_expected_ctr(position):
    """Return expected CTR for a given position."""
    for (low, high), ctr in CTR_BENCHMARKS.items():
        if low <= position <= high:
            return ctr
    return None


def _detect_services(query):
    """Detect which services a query relates to (word-boundary safe)."""
    found = []
    for service, patterns in _SERVICE_PATTERNS.items():
        if any(p.search(query) for p in patterns):
            found.append(service)
    # If nothing specific detected, mark as general "painting"
    if not found and re.search(r"\bpaint(er|ing|s)?\b", query, re.IGNORECASE):
        found.append("general")
    return found if found else ["unknown"]


def _detect_suburbs(query):
    """Detect which suburbs are mentioned in a query (word-boundary safe)."""
    found = []
    for suburb, pattern in _SUBURB_PATTERNS.items():
        if pattern.search(query):
            found.append(suburb)
    return found if found else []


def _suggest_action(row):
    """Suggest a specific action for a striking distance keyword."""
    pos = row["position"]
    query = row["query"]
    imp = row["impressions"]
    if pos <= 5:
        return (
            f'"{query}" at pos {pos:.1f} ({imp} imp) — almost top 3: '
            f"strengthen on-page content and add 1-2 internal links from related pages"
        )
    elif pos <= 10:
        return (
            f'"{query}" at pos {pos:.1f} ({imp} imp) — page 1 but below fold: '
            f"add FAQ schema targeting this query, deepen content, earn a local backlink"
        )
    else:
        return (
            f'"{query}" at pos {pos:.1f} ({imp} imp) — page 2: '
            f"needs a dedicated landing page or major content expansion"
        )
