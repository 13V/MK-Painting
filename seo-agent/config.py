"""
MK Painting SEO Agent — Configuration

Site details, known services, target suburbs, and existing landing pages.
"""

SITE_URL = "https://www.mandkpaintingservices.com.au/"
SITE_DOMAIN = "mandkpaintingservices.com.au"
GITHUB_REPO_URL = "https://github.com/13V/MK-Painting"

# Google Search Console property (sc-domain or URL prefix)
GSC_PROPERTY = "sc-domain:mandkpaintingservices.com.au"

# Days of data to pull (max 28 for fresh data, max 16 months historically)
LOOKBACK_DAYS = 28

# ── Services offered ──────────────────────────────────────────────────────────
SERVICES = {
    "interior":    ["interior painting", "interior painter", "interior repaint", "walls and ceilings"],
    "exterior":    ["exterior painting", "exterior painter", "exterior repaint", "house painting", "house painter"],
    "heritage":    ["heritage painting", "heritage painter", "heritage restoration", "federation", "victorian", "edwardian", "sandstone", "bluestone"],
    "commercial":  ["commercial painting", "commercial painter", "office painting", "warehouse painting", "industrial painting"],
    "strata":      ["strata painting", "strata painter", "body corporate", "body corp"],
    "roof":        ["roof painting", "roof restoration", "roof coating", "heat reflective", "cool roof", "iron roof"],
    "kitchen":     ["kitchen respray", "kitchen cabinet", "cabinet painting", "cabinet respray"],
    "deck":        ["deck staining", "deck oiling", "timber deck", "deck painting"],
}

# ── Target suburbs (priority order) ──────────────────────────────────────────
# Tier 1: Have dedicated landing pages
SUBURBS_TIER1 = [
    "mawson lakes", "gawler", "golden grove", "salisbury",
    "west lakes", "norwood", "unley", "burnside",
    "wingfield", "regency park", "edwardstown",
]

# Tier 2: Mentioned on regional pages but no dedicated page yet
SUBURBS_TIER2 = [
    "tea tree gully", "modbury", "elizabeth", "parafield",
    "prospect", "magill", "campbelltown", "paradise", "newton",
    "henley beach", "semaphore", "grange", "findon", "port adelaide",
    "noarlunga", "morphett vale", "hallett cove", "reynella", "seaford",
    "plympton", "kurralta park", "glenelg", "clarence park", "hyde park", "ingle farm", "para hills",
    "malvern", "hawthorn", "tusmore", "beaumont", "rostrevor",
    "dry creek", "mansfield park", "enfield", "melrose park",
]

ALL_SUBURBS = SUBURBS_TIER1 + SUBURBS_TIER2

# ── Existing landing pages ────────────────────────────────────────────────────
# Maps slug → primary keyword target
EXISTING_PAGES = {
    "/": "painters adelaide",
    "/mawson-lakes.html": "painters mawson lakes",
    "/gawler.html": "painters gawler",
    "/golden-grove.html": "painters golden grove",
    "/salisbury.html": "painters salisbury",
    "/northern-suburbs.html": "painters northern suburbs adelaide",
    "/west-lakes.html": "painters west lakes",
    "/norwood.html": "painters norwood",
    "/unley.html": "painters unley",
    "/burnside.html": "painters burnside",
    "/wingfield.html": "commercial painters wingfield",
    "/regency-park.html": "commercial painters regency park",
    "/edwardstown.html": "commercial painters edwardstown",
    "/commercial-painting.html": "commercial painters adelaide",
    "/kitchen-respray.html": "kitchen respray adelaide",
    "/strata-painting.html": "strata painters adelaide",
    "/about.html": "about mk painting adelaide",
    "/contact.html": "painters adelaide contact",
    "/blog.html": "painting tips adelaide",
    "/choosing-colors-mawson-lakes.html": "choosing paint colours mawson lakes",
    "/commercial-painting-guide.html": "commercial painting guide adelaide",
    "/golden-grove-painting-guide.html": "golden grove painting guide",
    "/heritage-painting-gawler.html": "heritage painting gawler",
    "/heritage-painting-guide.html": "heritage painting guide adelaide",
    "/kitchen-respray-guide.html": "kitchen respray guide adelaide",
    "/western-suburbs-painting-guide.html": "western suburbs painting guide",
    "/findon.html": "commercial painters findon",
    "/semaphore.html": "commercial painters semaphore",
    "/grange.html": "commercial painters grange",
    "/heritage-painting.html": "heritage painting adelaide",
}

# ── Analysis thresholds ───────────────────────────────────────────────────────
# Striking distance: keywords at these positions worth pushing to #1
STRIKING_DISTANCE_MIN = 4
STRIKING_DISTANCE_MAX = 15
STRIKING_DISTANCE_MIN_IMPRESSIONS = 20

# CTR benchmarks by position range — calibrated for local home services
# (map pack and featured snippets reduce organic CTR vs. generic benchmarks)
CTR_BENCHMARKS = {
    (1, 1): 0.08,    # Position 1 — local services avg 5-8% (map pack steals clicks)
    (2, 2): 0.06,    # Position 2 ~6%
    (3, 3): 0.05,    # Position 3 ~5%
    (4, 5): 0.04,    # Position 4-5 ~4%
    (6, 10): 0.025,  # Position 6-10 ~2.5%
    (11, 15): 0.012, # Position 11-15 ~1.2%
}

# Minimum impressions to consider a query worth analyzing
MIN_IMPRESSIONS = 10

# Minimum impressions for a service×suburb cluster to be flagged as a missing page
MISSING_PAGE_MIN_IMPRESSIONS = 15

# ── Page generation limits ────────────────────────────────────────────────────
MAX_NEW_PAGES_PER_RUN = 3    # Suburb + service pages per daily run
MAX_BLOG_ARTICLES_PER_RUN = 2  # Blog articles per daily run

# ── Claude API ────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
