import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine
from app.models import AdminUser, Category, Event, Location

CATEGORIES = [
    {
        "name": "Technology & Hackathons",
        "slug": "technology-hackathons",
        "description": "Hackathons, tech conferences, coding contests, and open source meetups.",
    },
    {
        "name": "Cultural & Arts",
        "slug": "cultural-arts",
        "description": "Tamil literature, music, dance, theatre, and heritage events.",
    },
    {
        "name": "Business & Startups",
        "slug": "business-startups",
        "description": "Entrepreneurship, pitch fests, networking, and investor summits.",
    },
    {
        "name": "Academic & Research",
        "slug": "academic-research",
        "description": "College symposiums, paper presentations, and academic seminars.",
    },
    {
        "name": "Workshops & Training",
        "slug": "workshops-training",
        "description": "Skill development, hands-on masterclasses, and bootcamps.",
    },
    {
        "name": "Sports & Fitness",
        "slug": "sports-fitness",
        "description": "Marathons, tournaments, traditional Tamil sports, and athletics.",
    },
    {
        "name": "Community & Social",
        "slug": "community-social",
        "description": "Volunteering, NGO initiatives, youth forums, and civic meetups.",
    },
]

# Verified venues with physical addresses
VERIFIED_VENUES = [
    {
        "name": "Chennai Trade Centre",
        "city": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "address": "CTC Complex, Mount Poonamallee Road, Nandambakkam, Chennai, Tamil Nadu 600089",
        "is_verified_venue": True,
    },
    {
        "name": "IIT Madras Research Park",
        "city": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "address": "Kanagam Road, Taramani, Chennai, Tamil Nadu 600113",
        "is_verified_venue": True,
    },
    {
        "name": "CODISSIA Trade Fair Complex",
        "city": "Coimbatore",
        "district": "Coimbatore",
        "state": "Tamil Nadu",
        "address": "G.V. Fair Grounds, Avinashi Road, Civil Aerodrome Post, Coimbatore, Tamil Nadu 641014",
        "is_verified_venue": True,
    },
    {
        "name": "Kalaivanar Arangam",
        "city": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "address": "Wallajah Road, Chepauk, Triplicane, Chennai, Tamil Nadu 600002",
        "is_verified_venue": True,
    },
    {
        "name": "Madurai Corporation Convention Hall",
        "city": "Madurai",
        "district": "Madurai",
        "state": "Tamil Nadu",
        "address": "Aringar Anna Maligai, Tallakulam, Madurai, Tamil Nadu 625002",
        "is_verified_venue": True,
    },
]

# District / City entries representing geographic areas (not specific physical venues)
DISTRICT_LOCATIONS = [
    {"name": "Chennai Central Hub", "city": "Chennai", "district": "Chennai"},
    {"name": "Coimbatore City Hub", "city": "Coimbatore", "district": "Coimbatore"},
    {"name": "Pollachi Hub", "city": "Pollachi", "district": "Coimbatore"},
    {"name": "Madurai City Hub", "city": "Madurai", "district": "Madurai"},
    {"name": "Tiruchirappalli Hub", "city": "Tiruchirappalli", "district": "Tiruchirappalli"},
    {"name": "Salem Hub", "city": "Salem", "district": "Salem"},
    {"name": "Tirunelveli Hub", "city": "Tirunelveli", "district": "Tirunelveli"},
    {"name": "Erode Hub", "city": "Erode", "district": "Erode"},
    {"name": "Vellore Hub", "city": "Vellore", "district": "Vellore"},
    {"name": "Thanjavur Hub", "city": "Thanjavur", "district": "Thanjavur"},
    {"name": "Kanchipuram Hub", "city": "Kanchipuram", "district": "Kanchipuram"},
    {"name": "Tambaram Hub", "city": "Tambaram", "district": "Chengalpattu"},
    {"name": "Chengalpattu Hub", "city": "Chengalpattu", "district": "Chengalpattu"},
    {"name": "Tiruppur Hub", "city": "Tiruppur", "district": "Tiruppur"},
    {"name": "Dindigul Hub", "city": "Dindigul", "district": "Dindigul"},
    {"name": "Cuddalore Hub", "city": "Cuddalore", "district": "Cuddalore"},
    {"name": "Thoothukudi Hub", "city": "Thoothukudi", "district": "Thoothukudi"},
    {"name": "Nagercoil Hub", "city": "Nagercoil", "district": "Kanyakumari"},
    {"name": "Hosur Hub", "city": "Hosur", "district": "Krishnagiri"},
    {"name": "Krishnagiri Hub", "city": "Krishnagiri", "district": "Krishnagiri"},
    {"name": "Dharmapuri Hub", "city": "Dharmapuri", "district": "Dharmapuri"},
    {"name": "Namakkal Hub", "city": "Namakkal", "district": "Namakkal"},
    {"name": "Karur Hub", "city": "Karur", "district": "Karur"},
    {"name": "Theni Hub", "city": "Theni", "district": "Theni"},
    {"name": "Sivakasi Hub", "city": "Sivakasi", "district": "Virudhunagar"},
    {"name": "Virudhunagar Hub", "city": "Virudhunagar", "district": "Virudhunagar"},
    {"name": "Ramanathapuram Hub", "city": "Ramanathapuram", "district": "Ramanathapuram"},
    {"name": "Karaikudi Hub", "city": "Karaikudi", "district": "Sivaganga"},
    {"name": "Sivaganga Hub", "city": "Sivaganga", "district": "Sivaganga"},
    {"name": "Pudukkottai Hub", "city": "Pudukkottai", "district": "Pudukkottai"},
    {"name": "Tiruvarur Hub", "city": "Tiruvarur", "district": "Tiruvarur"},
    {"name": "Nagapattinam Hub", "city": "Nagapattinam", "district": "Nagapattinam"},
    {"name": "Mayiladuthurai Hub", "city": "Mayiladuthurai", "district": "Mayiladuthurai"},
    {"name": "Ariyalur Hub", "city": "Ariyalur", "district": "Ariyalur"},
    {"name": "Perambalur Hub", "city": "Perambalur", "district": "Perambalur"},
    {"name": "Tiruvannamalai Hub", "city": "Tiruvannamalai", "district": "Tiruvannamalai"},
    {"name": "Viluppuram Hub", "city": "Viluppuram", "district": "Viluppuram"},
    {"name": "Kallakurichi Hub", "city": "Kallakurichi", "district": "Kallakurichi"},
    {"name": "Ranipet Hub", "city": "Ranipet", "district": "Ranipet"},
    {"name": "Tirupathur Hub", "city": "Tirupathur", "district": "Tirupathur"},
    {"name": "Tenkasi Hub", "city": "Tenkasi", "district": "Tenkasi"},
    {"name": "Udhagamandalam Hub", "city": "Udhagamandalam", "district": "Nilgiris"},
    {"name": "Tiruvallur Hub", "city": "Tiruvallur", "district": "Tiruvallur"},
]


def seed_database(populate_sample_event: bool = True) -> None:
    with Session(engine) as db:
        # 1. Admin user - only in non-production or if safe credentials provided
        is_prod = settings.app_env.lower() == "production"
        if not is_prod or settings.admin_password not in {"change-me", "admin"}:
            admin = db.scalar(select(AdminUser).where(AdminUser.email == settings.admin_email))
            if not admin:
                admin = AdminUser(
                    email=settings.admin_email,
                    password_hash=hash_password(settings.admin_password),
                    is_active=True,
                )
                db.add(admin)
                print(f"Created admin user: {settings.admin_email}")

        # 2. Categories (idempotent)
        cat_map = {}
        for cat_info in CATEGORIES:
            cat = db.scalar(select(Category).where(Category.slug == cat_info["slug"]))
            if not cat:
                cat = Category(
                    name=cat_info["name"],
                    slug=cat_info["slug"],
                    description=cat_info["description"],
                    is_active=True,
                )
                db.add(cat)
                db.flush()
                print(f"Created category: {cat.name}")
            cat_map[cat.slug] = cat

        # 3. Verified venues (idempotent)
        loc_map = {}
        for venue_info in VERIFIED_VENUES:
            loc = db.scalar(
                select(Location).where(
                    Location.name == venue_info["name"],
                    Location.city == venue_info["city"],
                )
            )
            if not loc:
                loc = Location(
                    name=venue_info["name"],
                    city=venue_info["city"],
                    district=venue_info.get("district"),
                    state="Tamil Nadu",
                    address=venue_info.get("address"),
                    is_active=True,
                    is_verified_venue=True,
                )
                db.add(loc)
                db.flush()
                print(f"Created verified venue: {loc.name} ({loc.city})")
            else:
                loc.is_verified_venue = True
                loc.address = venue_info.get("address")
            loc_map[loc.name] = loc

        # 4. Regional district locations without speculative addresses (idempotent)
        for dist_info in DISTRICT_LOCATIONS:
            loc = db.scalar(
                select(Location).where(
                    Location.name == dist_info["name"],
                    Location.city == dist_info["city"],
                )
            )
            if not loc:
                loc = Location(
                    name=dist_info["name"],
                    city=dist_info["city"],
                    district=dist_info.get("district"),
                    state="Tamil Nadu",
                    address=None,
                    is_active=True,
                    is_verified_venue=False,
                )
                db.add(loc)
                db.flush()

        # 5. Development sample event (strictly non-production)
        is_dev = settings.app_env.lower() in {"development", "dev", "local", "test"}
        if populate_sample_event and is_dev:
            sample_slug = "tamil-nadu-ai-open-source-hackathon-2026"
            sample_event = db.scalar(select(Event).where(Event.slug == sample_slug))
            if not sample_event:
                now = datetime.now(timezone.utc)
                tech_cat = cat_map.get("technology-hackathons") or db.scalars(select(Category)).first()
                ctc_loc = loc_map.get("Chennai Trade Centre") or db.scalars(select(Location)).first()

                sample_event = Event(
                    title="Tamil Nadu AI & Open Source Hackathon 2026",
                    slug=sample_slug,
                    short_description="Build groundbreaking AI and open source solutions addressing real-world challenges in Tamil Nadu.",
                    description="Join developers, students, researchers, and technologists from across Tamil Nadu for an intensive 36-hour hackathon. Mentors from premier tech firms will guide teams in creating open source AI solutions for regional language processing, agriculture, public healthcare, and sustainable transit.",
                    organizer_name="Tamil Nadu Tech Developers Collective",
                    organizer_website="https://example.com/tamil-tech",
                    registration_url="https://example.com/hackathon/register",
                    official_website="https://example.com/hackathon",
                    banner_url="https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=1200&q=80",
                    contact_email="contact@tamiltechcollective.org",
                    event_type="hackathon",
                    mode="hybrid",
                    start_date=now + timedelta(days=14),
                    end_date=now + timedelta(days=16),
                    registration_deadline=now + timedelta(days=10),
                    starts_at=now + timedelta(days=14),
                    ends_at=now + timedelta(days=16),
                    organizer="Tamil Nadu Tech Developers Collective",
                    ticket_url="https://example.com/hackathon/register",
                    image_url="https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=1200&q=80",
                    state="Tamil Nadu",
                    district="Chennai",
                    city="Chennai",
                    venue="Chennai Trade Centre, Nandambakkam",
                    eligibility="Open to students, researchers, startup founders, and working professionals across India.",
                    participation_fee=0.0,
                    currency="INR",
                    tags=["AI", "Open Source", "Hackathon", "Innovation", "Tamil Nadu"],
                    status="published",
                    is_published=True,
                    is_featured=True,
                    category_id=tech_cat.id if tech_cat else None,
                    location_id=ctc_loc.id if ctc_loc else None,
                )
                db.add(sample_event)
                print(f"Created development sample event: {sample_event.title}")

        db.commit()
        print("Seeding completed successfully.")


if __name__ == "__main__":
    populate_dev_sample = "--no-sample" not in sys.argv
    seed_database(populate_sample_event=populate_dev_sample)
