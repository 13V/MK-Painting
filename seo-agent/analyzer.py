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
    # Build set of suburbs that already have pages
    existing_slugs = set(EXISTING_PAGES.keys())
    suburbs_with_pages = set()
    for slug in existing_slugs:
        slug_lower = slug.lower().replace("/", "").replace(".html", "")
        for suburb in ALL_SUBURBS:
            if suburb.replace(" ", "-") == slug_lower:
                suburbs_with_pages.add(suburb)

    suburb_impressions = {}

    for row in query_data:
        query = row["query"].lower()
        for suburb in SUBURBS_TIER2:
            if suburb in suburbs_with_pages:
                continue  # Skip suburbs that already have a page
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
        if data["impressions"] >= 15:  # Lowered from 20 to catch emerging suburbs
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


def classify_map_pack_queries(query_data):
    """
    Identify queries dominated by the Google Maps 3-Pack.

    These are queries where we rank position 1-3 organically but get 0 clicks
    because the local map pack sits above organic results and absorbs all traffic.
    Optimizing title tags for these queries is futile — GBP optimization is needed instead.

    Returns (map_pack_queries, organic_queries) tuple.
    """
    MAP_PACK_PATTERNS = [
        re.compile(r"\bnear me\b", re.IGNORECASE),
        re.compile(r"^painters?$", re.IGNORECASE),
        re.compile(r"^house painters?$", re.IGNORECASE),
        re.compile(r"^local painters?\b", re.IGNORECASE),
        re.compile(r"^painting\b", re.IGNORECASE),
    ]

    map_pack = []
    organic = []

    for row in query_data:
        is_map_pack = (
            row["position"] <= 3
            and row["clicks"] == 0
            and row["impressions"] >= 30
            and any(p.search(row["query"]) for p in MAP_PACK_PATTERNS)
        )
        if is_map_pack:
            map_pack.append({**row, "map_pack_dominated": True})
        else:
            organic.append(row)

    return map_pack, organic


def find_blog_opportunities(query_data):
    """
    Find informational queries that could be answered by blog articles.

    Targets queries with "how to", "cost", "guide", "tips", "best", "vs",
    "difference", "ideas", etc. that don't already have a matching blog article.
    """
    INFORMATIONAL_PATTERNS = [
        re.compile(r"\bhow (to|much|long|do)\b", re.IGNORECASE),
        re.compile(r"\bcost\b", re.IGNORECASE),
        re.compile(r"\bprice\b", re.IGNORECASE),
        re.compile(r"\btips?\b", re.IGNORECASE),
        re.compile(r"\bguide\b", re.IGNORECASE),
        re.compile(r"\bbest\b", re.IGNORECASE),
        re.compile(r"\bideas?\b", re.IGNORECASE),
        re.compile(r"\bvs\.?\b", re.IGNORECASE),
        re.compile(r"\bdifference\b", re.IGNORECASE),
        re.compile(r"\bwhat (is|are|does)\b", re.IGNORECASE),
        re.compile(r"\bshould i\b", re.IGNORECASE),
        re.compile(r"\bchoose|choosing\b", re.IGNORECASE),
        re.compile(r"\bworth\b", re.IGNORECASE),
        re.compile(r"\bcolou?rs?\b", re.IGNORECASE),
        re.compile(r"\btrends?\b", re.IGNORECASE),
        re.compile(r"\bprepare|preparation\b", re.IGNORECASE),
        re.compile(r"\bdiy\b", re.IGNORECASE),
    ]

    # Build set of existing blog slugs for matching
    existing_blog_slugs = [
        slug for slug in EXISTING_PAGES.keys()
        if "guide" in slug or "choosing" in slug or "blog" in slug
    ]

    # Cluster informational queries by topic
    topic_clusters = {}
    for row in query_data:
        query = row["query"].lower()
        if not any(p.search(query) for p in INFORMATIONAL_PATTERNS):
            continue
        # Skip if we already have a page ranking well for this query
        if row["position"] <= 10 and row["clicks"] > 0:
            continue

        # Normalize to a topic key (strip suburb names, common words)
        topic = query
        for suburb in ALL_SUBURBS:
            topic = topic.replace(suburb, "").strip()
        topic = re.sub(r"\b(adelaide|sa|south australia)\b", "", topic).strip()
        topic = re.sub(r"\s+", " ", topic).strip()

        if not topic or len(topic) < 5:
            continue

        if topic not in topic_clusters:
            topic_clusters[topic] = {
                "impressions": 0,
                "clicks": 0,
                "queries": [],
            }
        topic_clusters[topic]["impressions"] += row["impressions"]
        topic_clusters[topic]["clicks"] += row["clicks"]
        topic_clusters[topic]["queries"].append(row["query"])

    results = []
    for topic, data in topic_clusters.items():
        if data["impressions"] >= 10:
            results.append({
                "topic": topic,
                "impressions": data["impressions"],
                "clicks": data["clicks"],
                "query_count": len(data["queries"]),
                "top_queries": data["queries"][:5],
            })

    return sorted(results, key=lambda r: r["impressions"], reverse=True)


def find_missing_service_pages(query_data):
    """
    Find services with search demand but no dedicated service page.

    For example, "interior painting" gets impressions but there's no
    /interior-painting.html — only commercial, kitchen, and strata have pages.
    """
    # Determine which services already have a dedicated service page
    # (not suburb pages, not blog guides — actual service pages)
    services_with_pages = set()
    for slug in EXISTING_PAGES:
        slug_lower = slug.lower()
        # Skip suburb pages, guides, and blog articles
        if "guide" in slug_lower or any(
            s.replace(" ", "-") in slug_lower
            for s in ALL_SUBURBS
        ):
            continue
        for service in SERVICES:
            # Match service keywords in the slug
            service_slug = service.replace(" ", "-")
            if service_slug in slug_lower:
                services_with_pages.add(service)

    results = []
    for service, keywords in SERVICES.items():
        if service in services_with_pages:
            continue  # Already has a page

        # Sum impressions for queries mentioning this service
        total_imp = 0
        total_clicks = 0
        matching_queries = []

        for row in query_data:
            query = row["query"].lower()
            if any(re.search(r"\b" + re.escape(kw) + r"\b", query, re.IGNORECASE) for kw in keywords):
                total_imp += row["impressions"]
                total_clicks += row["clicks"]
                matching_queries.append(row["query"])

        if total_imp >= 10:
            results.append({
                "service": service,
                "impressions": total_imp,
                "clicks": total_clicks,
                "query_count": len(matching_queries),
                "top_queries": matching_queries[:5],
            })

    return sorted(results, key=lambda r: r["impressions"], reverse=True)


def run_full_analysis(query_data, page_data, query_page_data=None):
    """
    Run the complete analysis pipeline and return all findings.
    """
    map_pack, organic_queries = classify_map_pack_queries(query_data)
    clusters = cluster_by_service_suburb(query_data)
    return {
        "summary": generate_summary_stats(query_data, page_data),
        "striking_distance": find_striking_distance(query_data),
        "ctr_gaps": find_ctr_gaps(organic_queries),  # Exclude map-pack queries from CTR gaps
        "zero_click": find_high_impression_zero_click(query_data),
        "clusters": clusters,
        "missing_pages": find_missing_pages(clusters),
        "suburb_opportunities": find_suburb_opportunities(query_data),
        "blog_opportunities": find_blog_opportunities(query_data),
        "missing_service_pages": find_missing_service_pages(query_data),
        "cannibalization": detect_cannibalization(query_page_data),
        "map_pack_queries": map_pack,
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
