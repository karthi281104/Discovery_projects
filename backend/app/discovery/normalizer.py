import html
import re
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
try:
    from bs4 import BeautifulSoup
except ImportError:
    class BeautifulSoup:  # type: ignore[no-redef]
        def __init__(self, raw_html: str, parser: str = "html.parser"):
            self.raw_html = raw_html or ""

        def get_text(self) -> str:
            return re.sub(r"<[^>]+>", " ", self.raw_html)
from dateutil import parser as date_parser

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")

TAMIL_NADU_DISTRICTS = [
    "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore",
    "Dharmapuri", "Dindigul", "Erode", "Kallakurichi", "Kanchipuram",
    "Kanyakumari", "Karur", "Krishnagiri", "Madurai", "Mayiladuthurai",
    "Nagapattinam", "Namakkal", "Nilgiris", "Perambalur", "Pudukkottai",
    "Ramanathapuram", "Ranipet", "Salem", "Sivaganga", "Tenkasi",
    "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli",
    "Tirupathur", "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Tiruvarur",
    "Vellore", "Viluppuram", "Virudhunagar"
]

DISTRICT_ALIASES = {
    "madras": "Chennai",
    "trichy": "Tiruchirappalli",
    "kovai": "Coimbatore",
    "tuticorin": "Thoothukudi",
    "pondicherry": "Puducherry",
    "tanjore": "Thanjavur",
}

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid"
}

EVENT_TYPE_KEYWORDS = [
    ("hackathon", "hackathon"),
    ("hackfest", "hackathon"),
    ("startup", "startup"),
    ("pitch", "startup"),
    ("entrepreneur", "startup"),
    ("coding", "competition"),
    ("symposium", "symposium"),
    ("fest", "symposium"),
    ("workshop", "workshop"),
    ("bootcamp", "workshop"),
    ("open source", "open_source"),
    ("foss", "open_source"),
    ("conference", "conference"),
    ("summit", "conference"),
    ("webinar", "webinar"),
    ("online talk", "webinar"),
    ("competition", "competition"),
    ("contest", "competition"),
    ("research", "research"),
    ("paper presentation", "research"),
]


def clean_text(raw_text: str | None) -> str:
    """Removes HTML tags, decodes entities, and collapses redundant whitespace."""
    if not raw_text:
        return ""
    # Strip HTML tags
    text = BeautifulSoup(raw_text, "html.parser").get_text()
    # Decode HTML entities
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_url(url: str | None) -> str:
    """Canonicalizes a URL by lowercasing host, removing tracking params, and removing fragment."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()

    filtered_query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS
    ]
    query_str = urlencode(filtered_query)

    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        parsed.params,
        query_str,
        ""  # drop fragment
    ))


def _is_date_only_string(date_str: str) -> bool:
    """Detects whether a date string represents a date-only specification (without hours/minutes)."""
    s = date_str.strip()
    # ISO date only: YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return True
    # DD-MM-YYYY or DD/MM/YYYY
    if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", s):
        return True
    # Month DD, YYYY or DD Month YYYY without time
    if not re.search(r"\d{1,2}:\d{2}", s) and not re.search(r"\b(am|pm)\b", s, re.IGNORECASE):
        # Check if year is present
        if re.search(r"\b(19|20)\d{2}\b", s):
            return True
    return False


def parse_date_with_metadata(
    date_str: str | None,
    default_tz: ZoneInfo = KOLKATA_TZ,
) -> tuple[datetime | None, bool]:
    """
    Parses a string into a timezone-aware UTC datetime and a boolean flag
    indicating if the source supplied a date-only value.

    Rules:
    - ISO 8601 UTC ('Z'): preserved as UTC.
    - Explicit offset: parsed with original offset, then converted to UTC (not reinterpreted).
    - Naive date/datetime: localized to default_tz (Asia/Kolkata) then converted to UTC.
    - Date-only strings: localized at start-of-day (00:00:00) in default_tz, flagged as date_only=True.
    - Returns (None, False) on invalid or unparseable input.
    """
    if not date_str or not str(date_str).strip():
        return None, False

    raw = str(date_str).strip()
    is_date_only = _is_date_only_string(raw)

    try:
        dt = date_parser.parse(raw)
    except Exception:
        # Try custom common Indian formats: e.g. "13th & 14th November 2026" or "13 Nov 2026"
        clean_raw = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", raw, flags=re.IGNORECASE)
        # If range like "13 & 14 November 2026" or "13 - 14 November 2026", take first day
        m = re.search(r"(\d+)\s*(?:&|-|to)\s*(\d+)\s+([A-Za-z]+)\s+(\d{4})", clean_raw, re.IGNORECASE)
        if m:
            first_day, _, month, year = m.groups()
            try:
                dt = date_parser.parse(f"{first_day} {month} {year}")
                is_date_only = True
            except Exception:
                return None, False
        else:
            try:
                dt = date_parser.parse(clean_raw)
            except Exception:
                return None, False

    if dt.tzinfo is None:
        # Naive: apply default_tz (Asia/Kolkata)
        dt = dt.replace(tzinfo=default_tz)

    # Convert to UTC for persistence
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt, is_date_only


def parse_and_localize_date(
    date_str: str | None,
    default_tz: ZoneInfo = KOLKATA_TZ,
) -> datetime | None:
    """Convenience helper returning only the UTC datetime from parse_date_with_metadata."""
    dt, _ = parse_date_with_metadata(date_str, default_tz)
    return dt


def detect_event_type(title: str, description: str | None, explicit_type: str | None = None) -> str:
    """Classifies an event into supported EventType."""
    if explicit_type:
        lowered = explicit_type.lower().strip()
        for kw, etype in EVENT_TYPE_KEYWORDS:
            if kw in lowered:
                return etype

    combined = f"{title} {description or ''}".lower()
    for kw, etype in EVENT_TYPE_KEYWORDS:
        if kw in combined:
            return etype
    return "other"


def _match_district_in_text(text: str) -> str | None:
    """Matches a Tamil Nadu district or alias in text."""
    lowered = text.lower()
    for district in TAMIL_NADU_DISTRICTS:
        pattern = r"\b" + re.escape(district.lower()) + r"\b"
        if re.search(pattern, lowered):
            return district
    for alias, canonical in DISTRICT_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, lowered):
            return canonical
    return None


def detect_district_and_city(
    venue: str | None,
    city: str | None,
    text_context: str | None = None,
    source_region: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Infers district and city strictly adhering to priority:
    1. Explicit venue text.
    2. Explicit city text.
    3. Structured source location / source_region.
    4. Reliable source-specific location metadata.
    5. Unknown (returns None, None).

    Crucially: NEVER infers city from arbitrary description text when explicit
    venue or city information exists. Does not pick arbitrary districts if
    multiple are mentioned in context.
    """
    # 1. Explicit Venue
    if venue and venue.strip():
        dist = _match_district_in_text(venue)
        if dist:
            # Clean city if venue explicitly matches
            cleaned_city = city.strip() if city and city.strip() else dist
            return dist, cleaned_city

    # 2. Explicit City
    if city and city.strip():
        cleaned_city = city.strip()
        if cleaned_city.lower() not in ("tamil nadu", "tamilnadu", "all india", "india", "online", "virtual"):
            dist = _match_district_in_text(cleaned_city)
            if dist:
                return dist, cleaned_city
            return None, cleaned_city

    # 3. Source Region
    if source_region and source_region.strip():
        reg = source_region.strip()
        if reg.lower() not in ("tamil nadu", "tamilnadu", "all india", "india"):
            dist = _match_district_in_text(reg)
            if dist:
                return dist, dist

    # 4. Context fallback ONLY if venue, city, and region are all completely absent
    if not venue and not city and not (source_region and source_region.lower() not in ("tamil nadu", "tamilnadu")):
        if text_context and text_context.strip():
            # Only match if there's an unambiguous single district mentioned
            matches = set()
            for district in TAMIL_NADU_DISTRICTS:
                if re.search(r"\b" + re.escape(district.lower()) + r"\b", text_context.lower()):
                    matches.add(district)
            for alias, canonical in DISTRICT_ALIASES.items():
                if re.search(r"\b" + re.escape(alias) + r"\b", text_context.lower()):
                    matches.add(canonical)
            if len(matches) == 1:
                single_dist = matches.pop()
                return single_dist, single_dist

    # 5. Unknown
    return None, None
