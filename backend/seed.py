import os
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

LOCATIONS = [
    {"name": "Chennai Trade Centre", "city": "Chennai", "district": "Chennai", "address": "CTC Complex, Nandambakkam, Chennai"},
    {"name": "IIT Madras Research Park", "city": "Chennai", "district": "Chennai", "address": "Kanagam Road, Taramani, Chennai"},
    {"name": "CODISSIA Trade Fair Complex", "city": "Coimbatore", "district": "Coimbatore", "address": "G.V. Fair Grounds, Avinashi Road, Coimbatore"},
    {"name": "Pollachi Central Ground", "city": "Pollachi", "district": "Coimbatore", "address": "Pollachi Main Road, Coimbatore District"},
    {"name": "Madurai Meenakshi Convention Centre", "city": "Madurai", "district": "Madurai", "address": "Bypass Road, Madurai"},
    {"name": "Trichy District Central Hall", "city": "Tiruchirappalli", "district": "Tiruchirappalli", "address": "Cantonment, Tiruchirappalli"},
    {"name": "Salem Town Hall", "city": "Salem", "district": "Salem", "address": "Four Roads, Salem"},
    {"name": "Tirunelveli Exhibition Ground", "city": "Tirunelveli", "district": "Tirunelveli", "address": "Palayamkottai, Tirunelveli"},
    {"name": "Erode Municipal Stadium", "city": "Erode", "district": "Erode", "address": "Brough Road, Erode"},
    {"name": "Vellore Fort Auditorium", "city": "Vellore", "district": "Vellore", "address": "Near Vellore Fort, Vellore"},
    {"name": "Thanjavur Arts Centre", "city": "Thanjavur", "district": "Thanjavur", "address": "South Rampart, Thanjavur"},
    {"name": "Kanchipuram Silk Centre Hall", "city": "Kanchipuram", "district": "Kanchipuram", "address": "Gandhi Road, Kanchipuram"},
    {"name": "Tambaram Community Centre", "city": "Tambaram", "district": "Chengalpattu", "address": "GST Road, Tambaram, Chengalpattu District"},
    {"name": "Chengalpattu Collectorate Auditorium", "city": "Chengalpattu", "district": "Chengalpattu", "address": "GST Road, Chengalpattu"},
    {"name": "Tiruppur Knitwear Centre", "city": "Tiruppur", "district": "Tiruppur", "address": "Avinashi Road, Tiruppur"},
    {"name": "Dindigul Rock Fort Stadium", "city": "Dindigul", "district": "Dindigul", "address": "Near Rock Fort, Dindigul"},
    {"name": "Cuddalore Port Beach Grounds", "city": "Cuddalore", "district": "Cuddalore", "address": "Silver Beach Road, Cuddalore"},
    {"name": "Thoothukudi Harbour Grounds", "city": "Thoothukudi", "district": "Thoothukudi", "address": "Beach Road, Thoothukudi"},
    {"name": "Nagercoil Town Hall", "city": "Nagercoil", "district": "Kanyakumari", "address": "Cape Road, Nagercoil"},
    {"name": "Hosur Tech Park Hall", "city": "Hosur", "district": "Krishnagiri", "address": "SIPCOT Phase I, Hosur"},
    {"name": "Krishnagiri District Complex", "city": "Krishnagiri", "district": "Krishnagiri", "address": "Collectorate Road, Krishnagiri"},
    {"name": "Dharmapuri District Grounds", "city": "Dharmapuri", "district": "Dharmapuri", "address": "Pennagaram Road, Dharmapuri"},
    {"name": "Namakkal Transport Hub Hall", "city": "Namakkal", "district": "Namakkal", "address": "Salem Road, Namakkal"},
    {"name": "Karur Textile Fair Hall", "city": "Karur", "district": "Karur", "address": "Kovai Road, Karur"},
    {"name": "Theni Agricultural Centre", "city": "Theni", "district": "Theni", "address": "Madurai Road, Theni"},
    {"name": "Sivakasi Jubilee Hall", "city": "Sivakasi", "district": "Virudhunagar", "address": "Sivakasi Main Road, Virudhunagar District"},
    {"name": "Virudhunagar Municipal Complex", "city": "Virudhunagar", "district": "Virudhunagar", "address": "Madurai Road, Virudhunagar"},
    {"name": "Ramanathapuram Palace Hall", "city": "Ramanathapuram", "district": "Ramanathapuram", "address": "Palace Grounds, Ramanathapuram"},
    {"name": "Karaikudi Heritage Complex", "city": "Karaikudi", "district": "Sivaganga", "address": "College Road, Karaikudi"},
    {"name": "Sivaganga District Hall", "city": "Sivaganga", "district": "Sivaganga", "address": "Madurai Road, Sivaganga"},
    {"name": "Pudukkottai Palace Grounds", "city": "Pudukkottai", "district": "Pudukkottai", "address": "Palace Road, Pudukkottai"},
    {"name": "Tiruvarur Chariot Square", "city": "Tiruvarur", "district": "Tiruvarur", "address": "Car Street, Tiruvarur"},
    {"name": "Nagapattinam Coastal Auditorium", "city": "Nagapattinam", "district": "Nagapattinam", "address": "Public Office Road, Nagapattinam"},
    {"name": "Mayiladuthurai Cauvery Hall", "city": "Mayiladuthurai", "district": "Mayiladuthurai", "address": "Pattamangala Street, Mayiladuthurai"},
    {"name": "Ariyalur Cement City Hall", "city": "Ariyalur", "district": "Ariyalur", "address": "Trichy Main Road, Ariyalur"},
    {"name": "Perambalur Collectorate Grounds", "city": "Perambalur", "district": "Perambalur", "address": "Elambalur Road, Perambalur"},
    {"name": "Tiruvannamalai Girivalam Plaza", "city": "Tiruvannamalai", "district": "Tiruvannamalai", "address": "Girivalam Path, Tiruvannamalai"},
    {"name": "Viluppuram Junction Hall", "city": "Viluppuram", "district": "Viluppuram", "address": "Trichy Trunk Road, Viluppuram"},
    {"name": "Kallakurichi Town Ground", "city": "Kallakurichi", "district": "Kallakurichi", "address": "Salem Main Road, Kallakurichi"},
    {"name": "Ranipet Industrial Centre", "city": "Ranipet", "district": "Ranipet", "address": "SIPCOT, Ranipet"},
    {"name": "Tirupathur District Auditorium", "city": "Tirupathur", "district": "Tirupathur", "address": "Railway Station Road, Tirupathur"},
    {"name": "Tenkasi Waterfalls Pavilion", "city": "Tenkasi", "district": "Tenkasi", "address": "Courtallam Road, Tenkasi"},
    {"name": "Ooty Heritage Botanical Hall", "city": "Udhagamandalam", "district": "Nilgiris", "address": "Vannarapettai, Ooty, Nilgiris"},
    {"name": "Tiruvallur Municipal Stadium", "city": "Tiruvallur", "district": "Tiruvallur", "address": "JN Road, Tiruvallur"},
]


def seed_database(populate_sample_event: bool = True) -> None:
    with Session(engine) as db:
        # 1. Admin user
        admin = db.scalar(select(AdminUser).where(AdminUser.email == settings.admin_email))
        if not admin:
            admin = AdminUser(email=settings.admin_email, password_hash=hash_password(settings.admin_password), is_active=True)
            db.add(admin)
            print(f"Created default admin user: {settings.admin_email}")

        # 2. Categories
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

        # 3. Locations
        loc_map = {}
        for loc_info in LOCATIONS:
            loc = db.scalar(select(Location).where(Location.name == loc_info["name"], Location.city == loc_info["city"]))
            if not loc:
                loc = Location(
                    name=loc_info["name"],
                    city=loc_info["city"],
                    district=loc_info.get("district"),
                    state="Tamil Nadu",
                    address=loc_info.get("address"),
                    is_active=True,
                )
                db.add(loc)
                db.flush()
                print(f"Created location: {loc.name} ({loc.city})")
            loc_map[loc.name] = loc

        # 4. Development sample event
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
