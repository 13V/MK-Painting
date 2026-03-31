"""
Google Analytics 4 Data API client.

Pulls conversion and engagement data to correlate with GSC rankings.
Requires the service account to be added as a Viewer in GA4 property settings.
"""

import json
import os
from datetime import datetime, timedelta

from config import SITE_URL


def _get_ga4_property_id():
    """Get GA4 property ID from environment."""
    prop_id = os.environ.get("GA4_PROPERTY_ID")
    if not prop_id:
        return None
    return prop_id


def _get_ga4_client():
    """Build a GA4 Data API client using service account credentials."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account

    creds_json = os.environ.get("GSC_CREDENTIALS_JSON")
    if not creds_json:
        creds_path = os.environ.get("GSC_CREDENTIALS_PATH", "credentials.json")
        if not os.path.exists(creds_path):
            raise FileNotFoundError("No Google credentials found.")
        with open(creds_path, "r", encoding="utf-8") as f:
            creds_json = f.read()

    creds_info = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )

    return BetaAnalyticsDataClient(credentials=credentials)


def fetch_ga4_summary(days=7):
    """
    Fetch key engagement and conversion metrics from GA4.

    Returns dict with sessions, users, key events, top pages, and traffic sources.
    Returns None if GA4 is not configured.
    """
    property_id = _get_ga4_property_id()
    if not property_id:
        return None

    try:
        client = _get_ga4_client()
    except Exception as e:
        print(f"   ⚠ GA4 client init failed: {e}")
        return None

    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        RunReportRequest,
        FilterExpression,
        Filter,
    )

    date_range = DateRange(
        start_date=f"{days}daysAgo",
        end_date="yesterday",
    )
    property_name = f"properties/{property_id}"

    result = {
        "period_days": days,
        "total_sessions": 0,
        "organic_sessions": 0,
        "total_users": 0,
        "phone_clicks": 0,
        "top_pages": [],
        "traffic_sources": [],
    }

    try:
        # 1. Overall sessions + users
        overview = client.run_report(RunReportRequest(
            property=property_name,
            date_ranges=[date_range],
            metrics=[
                Metric(name="sessions"),
                Metric(name="activeUsers"),
                Metric(name="keyEvents"),
            ],
        ))
        if overview.rows:
            row = overview.rows[0]
            result["total_sessions"] = int(row.metric_values[0].value)
            result["total_users"] = int(row.metric_values[1].value)
            result["phone_clicks"] = int(row.metric_values[2].value)

        # 2. Organic search sessions
        organic = client.run_report(RunReportRequest(
            property=property_name,
            date_ranges=[date_range],
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name="sessionDefaultChannelGroup",
                    string_filter=Filter.StringFilter(
                        value="Organic Search",
                        match_type=Filter.StringFilter.MatchType.EXACT,
                    ),
                )
            ),
        ))
        if organic.rows:
            result["organic_sessions"] = int(organic.rows[0].metric_values[0].value)

        # 3. Top pages by sessions
        pages = client.run_report(RunReportRequest(
            property=property_name,
            date_ranges=[date_range],
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="activeUsers"),
                Metric(name="keyEvents"),
            ],
            order_bys=[{
                "metric": {"metric_name": "sessions"},
                "desc": True,
            }],
            limit=10,
        ))
        for row in pages.rows:
            result["top_pages"].append({
                "page": row.dimension_values[0].value,
                "sessions": int(row.metric_values[0].value),
                "users": int(row.metric_values[1].value),
                "key_events": int(row.metric_values[2].value),
            })

        # 4. Traffic source breakdown
        sources = client.run_report(RunReportRequest(
            property=property_name,
            date_ranges=[date_range],
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="keyEvents"),
            ],
            order_bys=[{
                "metric": {"metric_name": "sessions"},
                "desc": True,
            }],
            limit=8,
        ))
        for row in sources.rows:
            result["traffic_sources"].append({
                "channel": row.dimension_values[0].value,
                "sessions": int(row.metric_values[0].value),
                "key_events": int(row.metric_values[1].value),
            })

    except Exception as e:
        print(f"   ⚠ GA4 API error: {e}")
        return None

    return result
