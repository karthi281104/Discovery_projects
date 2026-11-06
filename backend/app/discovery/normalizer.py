import html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from bs4 import BeautifulSoup
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

    # Filter query params
    filtered_query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS
    ]
    query_str = urlencode(filtered_query)

    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    canonical = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        parsed.params,
        query_str,
        ""  # drop fragment
    ))
    return canonical


def parse_and_localize_date(
    date_str: str | None,
    default_tz: ZoneInfo = KOLKATA_TZ,
) -> datetime | None:
    """
    Parses a string into a timezone-aware UTC datetime.
    If the date is naive and associated with India/Tamil Nadu, applies Asia/Kolkata first.
    """
    if not date_str or not str(date_str).strip():
        return None

    cleaned_str = str(date_str).strip()
    try:
        dt = date_parser.parse(cleaned_str)
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)

    return dt.astimezone(timezone.utc)


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


def detect_district_and_city(
    venue: str | None,
    city: str | None,
    text_context: str | None,
) -> tuple[str | None, str | None]:
    """Infers district and city from location strings and text context."""
    combined = f"{venue or ''} {city or ''} {text_context or ''}".lower()

    detected_district = None
    for district in TAMIL_NADU_DISTRICTS:
        pattern = r"\b" + re.escape(district.lower()) + r"\b"
        if re.search(pattern, combined):
            detected_district = district
            break

    # Common alternate names
    if not detected_district:
        if "madras" in combined:
            detected_district = "Chennai"
        elif "trichy" in combined:
            detected_district = "Tiruchirappalli"
        elif "kovai" in combined:
            detected_district = "Coimbatore"
        elif "tuticorin" in combined:
            detected_district = "Thoothukudi"

    # Handle state-level or empty city input
    cleaned_city = city.strip() if city and city.strip() else None
    if cleaned_city and cleaned_city.lower() in ("tamil nadu", "tamilnadu", "all india", "india"):
        cleaned_city = None

    detected_city = cleaned_city or detected_district
    return detected_district, detected_city
