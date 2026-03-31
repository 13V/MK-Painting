"""
Google Search Console API client.

Pulls query and page performance data for the configured property.
Supports both API access (service account) and CSV import fallback.
"""

import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from config import GSC_PROPERTY, LOOKBACK_DAYS, MIN_IMPRESSIONS, SITE_URL


def _get_credentials():
    """Load service account credentials from env or file."""
    from google.oauth2 import service_account

    creds_json = os.environ.get("GSC_CREDENTIALS_JSON")
    if not creds_json:
        creds_path = os.environ.get("GSC_CREDENTIALS_PATH", "credentials.json")
        if not Path(creds_path).exists():
            raise FileNotFoundError(
                f"No GSC credentials found. Set GSC_CREDENTIALS_JSON env var "
                f"or place a service account key at {creds_path}"
            )
        creds_json = Path(creds_path).read_text()

    creds_info = json.loads(creds_json)
    return service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=[
            "https://www.googleapis.com/auth/webmasters",  # read-write (needed for sitemaps API)
        ],
    )


def get_gsc_service():
    """Authenticate and return a GSC API service object."""
    from googleapiclient.discovery import build

    return build("searchconsole", "v1", credentials=_get_credentials())


def fetch_query_data(service=None, days=LOOKBACK_DAYS):
    """
    Fetch query-level performance data from GSC.

    Returns list of dicts with keys:
        query, clicks, impressions, ctr, position
    """
    if service is None:
        service = get_gsc_service()

    end_date = datetime.now() - timedelta(days=3)  # GSC data has 3-day lag
    start_date = end_date - timedelta(days=days)

    response = service.searchanalytics().query(
        siteUrl=GSC_PROPERTY,
        body={
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "dimensions": ["query"],
            "rowLimit": 5000,
            "dataState": "final",
        },
    ).execute()

    rows = []
    for row in response.get("rows", []):
        if row["impressions"] >= MIN_IMPRESSIONS:
            rows.append({
                "query": row["keys"][0],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": round(row["ctr"], 4),
                "position": round(row["position"], 1),
            })

    return sorted(rows, key=lambda r: r["impressions"], reverse=True)


def fetch_page_data(service=None, days=LOOKBACK_DAYS):
    """
    Fetch page-level performance data from GSC.

    Returns list of dicts with keys:
        page, clicks, impressions, ctr, position
    """
    if service is None:
        service = get_gsc_service()

    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    response = service.searchanalytics().query(
        siteUrl=GSC_PROPERTY,
        body={
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "dimensions": ["page"],
            "rowLimit": 1000,
            "dataState": "final",
        },
    ).execute()

    rows = []
    for row in response.get("rows", []):
        if row["impressions"] >= MIN_IMPRESSIONS:
            rows.append({
                "page": row["keys"][0],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": round(row["ctr"], 4),
                "position": round(row["position"], 1),
            })

    return sorted(rows, key=lambda r: r["impressions"], reverse=True)


def fetch_query_page_data(service=None, days=LOOKBACK_DAYS):
    """
    Fetch query+page combined data — shows which page ranks for which query.

    Returns list of dicts with keys:
        query, page, clicks, impressions, ctr, position
    """
    if service is None:
        service = get_gsc_service()

    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    response = service.searchanalytics().query(
        siteUrl=GSC_PROPERTY,
        body={
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "dimensions": ["query", "page"],
            "rowLimit": 5000,
            "dataState": "final",
        },
    ).execute()

    rows = []
    for row in response.get("rows", []):
        if row["impressions"] >= MIN_IMPRESSIONS:
            rows.append({
                "query": row["keys"][0],
                "page": row["keys"][1],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": round(row["ctr"], 4),
                "position": round(row["position"], 1),
            })

    return rows


# ── URL Inspection & Indexing ────────────────────────────────────────────────

def inspect_url(url, service=None):
    """
    Inspect a URL via the GSC URL Inspection API.

    Returns dict with:
        verdict, indexing_state, crawl_time, sitemap, referring_urls
    """
    if service is None:
        service = get_gsc_service()

    result = service.urlInspection().index().inspect(
        body={
            "inspectionUrl": url,
            "siteUrl": GSC_PROPERTY,
        }
    ).execute()

    inspection = result.get("inspectionResult", {})
    index_status = inspection.get("indexStatusResult", {})

    return {
        "url": url,
        "verdict": index_status.get("verdict", "UNKNOWN"),
        "indexing_state": index_status.get("indexingState", "UNKNOWN"),
        "last_crawl_time": index_status.get("lastCrawlTime"),
        "page_fetch_state": index_status.get("pageFetchState", "UNKNOWN"),
        "robots_txt_state": index_status.get("robotsTxtState", "UNKNOWN"),
        "sitemap": index_status.get("sitemap", []),
        "referring_urls": index_status.get("referringUrls", []),
    }


def resubmit_sitemap(service=None):
    """
    Submit sitemap via the GSC Sitemaps API.

    This is the only reliable programmatic method to trigger re-crawl for
    general websites. The Google Indexing API is restricted to JobPosting
    and BroadcastEvent structured data types only.
    """
    if service is None:
        service = get_gsc_service()

    sitemap_url = f"{SITE_URL}sitemap.xml"
    try:
        service.sitemaps().submit(
            siteUrl=GSC_PROPERTY,
            feedpath=sitemap_url,
        ).execute()
        print(f"   ✓ Sitemap resubmitted: {sitemap_url}")
        return {"status": "success", "sitemap": sitemap_url}
    except Exception as e:
        print(f"   ⚠ Sitemap submission failed: {e}")
        return {"status": "error", "error": str(e)}


def inspect_and_submit_new_pages(pages_to_check=None):
    """
    Inspect all site pages and resubmit sitemap if any are unindexed.

    Returns dict with inspection results and submission results.
    """
    if pages_to_check is None:
        from config import EXISTING_PAGES
        pages_to_check = [
            f"{SITE_URL.rstrip('/')}{slug}" for slug in EXISTING_PAGES.keys()
        ]

    service = get_gsc_service()
    results = {"inspected": [], "submitted": [], "already_indexed": [], "errors": []}

    for url in pages_to_check:
        print(f"   Inspecting: {url}")
        try:
            inspection = inspect_url(url, service=service)
            results["inspected"].append(inspection)

            if inspection["indexing_state"] not in ("INDEXING_ALLOWED", "INDEXED"):
                results["submitted"].append({"url": url, "status": "unindexed"})
            else:
                results["already_indexed"].append(url)
        except Exception as e:
            print(f"   → Error: {e}")
            results["errors"].append({"url": url, "error": str(e)})

    # If any pages are unindexed, resubmit the sitemap via GSC Sitemaps API
    if results["submitted"]:
        unindexed_urls = [item["url"] for item in results["submitted"]]
        print(f"   → {len(unindexed_urls)} unindexed pages found — resubmitting sitemap")
        sitemap_result = resubmit_sitemap(service)
        status_msg = (
            "sitemap resubmitted"
            if sitemap_result["status"] == "success"
            else f"sitemap submission failed: {sitemap_result.get('error', 'unknown')}"
        )
        for item in results["submitted"]:
            item["status"] = status_msg

    return results


# ── CSV fallback for manual imports ──────────────────────────────────────────

def load_from_csv(filepath):
    """
    Load GSC data from a CSV export (downloaded from GSC web UI).

    Expected columns: Top queries, Clicks, Impressions, CTR, Position
    OR: Top pages, Clicks, Impressions, CTR, Position

    Returns list of dicts matching the API format.
    """
    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # GSC CSV exports use various column names
            query_or_page = (
                row.get("Top queries")
                or row.get("Top pages")
                or row.get("Query")
                or row.get("Page")
                or ""
            )
            clicks = int(row.get("Clicks", 0))
            impressions = int(row.get("Impressions", 0))
            ctr_raw = row.get("CTR", "0%").replace("%", "").strip()
            ctr = float(ctr_raw) / 100 if float(ctr_raw) > 1 else float(ctr_raw)
            position = float(row.get("Position", 0))

            if impressions >= MIN_IMPRESSIONS:
                key = "query" if "quer" in (list(row.keys())[0]).lower() else "page"
                rows.append({
                    key: query_or_page,
                    "clicks": clicks,
                    "impressions": impressions,
                    "ctr": round(ctr, 4),
                    "position": round(position, 1),
                })

    return sorted(rows, key=lambda r: r["impressions"], reverse=True)
