"""
Daily data persistence layer.

Saves JSON snapshots of GSC data for trend analysis.
Enables week-over-week comparison, position tracking, and regression detection.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def save_daily_snapshot(query_data, page_data, analysis_summary):
    """Save today's raw data and summary as JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")

    snapshot = {
        "date": date_str,
        "queries": query_data,
        "pages": page_data,
        "summary": analysis_summary,
    }

    path = DATA_DIR / f"snapshot-{date_str}.json"
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    # Prune snapshots older than 90 days
    _prune_old_snapshots(90)

    return str(path)


def load_snapshot(date_str):
    """Load a specific day's snapshot."""
    path = DATA_DIR / f"snapshot-{date_str}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_previous_snapshot(days_ago=1):
    """
    Load the most recent snapshot up to days_ago days back.
    Tries each day in case some days have no data (weekends, failures).
    """
    for offset in range(days_ago, days_ago + 7):
        target = datetime.now() - timedelta(days=offset)
        snapshot = load_snapshot(target.strftime("%Y-%m-%d"))
        if snapshot:
            return snapshot
    return None


def compute_trends(current_queries, previous_snapshot):
    """
    Compare current data with previous snapshot and find movers.

    Returns dict with:
        - new_keywords: queries appearing for the first time
        - lost_keywords: queries that disappeared
        - position_changes: queries that moved >=2 positions
        - summary_delta: click/impression changes vs previous period
    """
    if not previous_snapshot:
        return {
            "new_keywords": [],
            "lost_keywords": [],
            "position_changes": [],
            "summary_delta": None,
            "previous_date": None,
        }

    prev_queries = previous_snapshot.get("queries", [])
    prev_map = {q["query"]: q for q in prev_queries}
    curr_map = {q["query"]: q for q in current_queries}

    position_changes = []
    new_keywords = []

    for q in current_queries:
        query = q["query"]
        if query not in prev_map:
            new_keywords.append(q)
        else:
            prev = prev_map[query]
            pos_delta = prev["position"] - q["position"]  # positive = improved
            if abs(pos_delta) >= 2.0:
                position_changes.append({
                    **q,
                    "prev_position": prev["position"],
                    "position_delta": round(pos_delta, 1),
                    "direction": "up" if pos_delta > 0 else "down",
                })

    # Keywords that disappeared
    lost_keywords = [
        prev_map[query] for query in prev_map
        if query not in curr_map
    ]

    # Summary-level deltas
    prev_summary = previous_snapshot.get("summary", {})
    summary_delta = None
    if prev_summary:
        summary_delta = {
            "clicks_delta": (
                sum(q["clicks"] for q in current_queries)
                - prev_summary.get("total_clicks", 0)
            ),
            "impressions_delta": (
                sum(q["impressions"] for q in current_queries)
                - prev_summary.get("total_impressions", 0)
            ),
        }

    position_changes.sort(key=lambda x: abs(x["position_delta"]), reverse=True)

    return {
        "new_keywords": new_keywords[:10],
        "lost_keywords": lost_keywords[:10],
        "position_changes": position_changes[:15],
        "summary_delta": summary_delta,
        "previous_date": previous_snapshot.get("date"),
    }


def _prune_old_snapshots(max_days):
    """Remove snapshots older than max_days."""
    if not DATA_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=max_days)
    for path in DATA_DIR.glob("snapshot-*.json"):
        try:
            date_str = path.stem.replace("snapshot-", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                path.unlink()
        except (ValueError, OSError):
            pass
