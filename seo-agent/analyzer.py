"""
SEO data analyzer.

Takes raw GSC data and produces structured opportunity findings:
- Striking distance keywords
- CTR optimization opportunities
- Service × suburb clusters
- Missing landing page gaps
"""

from config import (
    ALL_SUBURBS,
    CTR_BENCHMARKS,
    EXISTING_PAGES,
    SERVICES,
    SITE_URL,
    STRIKING_DISTANCE_MAX,
    STRIKING_DISTANCE_MIN,
    STRIKING_DISTANCE_MIN_IMPRESSIONS,
    SUBURBS_TIER1,
    SUBURBS_TIER2,
)


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

        if not has_page and total_impressions >= 30:
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
            if suburb in query:
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


def run_full_analysis(query_data, page_data):
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
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_expected_ctr(position):
    """Return expected CTR for a given position."""
    for (low, high), ctr in CTR_BENCHMARKS.items():
        if low <= position <= high:
            return ctr
    return None


def _detect_services(query):
    """Detect which services a query relates to."""
    found = []
    for service, keywords in SERVICES.items():
        if any(kw in query for kw in keywords):
            found.append(service)
    # If nothing specific detected, mark as general "painting"
    if not found and ("paint" in query or "painter" in query):
        found.append("general")
    return found if found else ["unknown"]


def _detect_suburbs(query):
    """Detect which suburbs are mentioned in a query."""
    found = []
    for suburb in ALL_SUBURBS:
        if suburb in query:
            found.append(suburb)
    return found if found else ["adelaide"]


def _suggest_action(row):
    """Suggest an action for a striking distance keyword."""
    pos = row["position"]
    if pos <= 5:
        return f"Almost top 3 — strengthen on-page content and build 1-2 internal links"
    elif pos <= 10:
        return f"Page 1 but below fold — add FAQ schema, improve content depth, get a backlink"
    else:
        return f"Page 2 — needs dedicated content section or new landing page"
