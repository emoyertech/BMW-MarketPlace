from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List


RANDOM_SEED = 20240517
RNG = random.Random(RANDOM_SEED)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    slug = []
    previous_dash = False
    for character in value.lower():
        if character.isalnum():
            slug.append(character)
            previous_dash = False
        else:
            if not previous_dash:
                slug.append("-")
                previous_dash = True
    result = "".join(slug).strip("-")
    return result or "item"


def iso_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def random_datetime(start: datetime, end: datetime) -> datetime:
    span = int((end - start).total_seconds())
    if span <= 0:
        return start
    offset = RNG.randint(0, span)
    return start + timedelta(seconds=offset)


def pick(items: list[str]) -> str:
    return RNG.choice(items)


def pick_many(items: list[str], minimum: int = 1, maximum: int = 3) -> list[str]:
    count = RNG.randint(minimum, maximum)
    count = min(count, len(items))
    return RNG.sample(items, count)


def write_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class User:
    user_id: str
    name: str
    display_name: str
    email: str
    role: str
    location: str
    avatar_url: str
    bio: str


@dataclass(slots=True)
class Listing:
    listing_id: str
    seller_user_id: str
    seller_name: str
    seller_role: str
    title: str
    slug: str
    price: int
    currency: str
    year: int
    mileage: int
    transmission: str
    fuel_type: str
    body_style: str
    color: str
    drivetrain: str
    exterior_condition: str
    interior_condition: str
    description: str
    excerpt: str
    status: str
    featured: bool
    images: list[str]
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Part:
    part_id: str
    seller_user_id: str
    seller_name: str
    seller_role: str
    title: str
    slug: str
    price: int
    condition: str
    category: str
    description: str
    featured: bool
    images: list[str]
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Inquiry:
    inquiry_id: str
    listing_id: str
    user_id: str
    user_name: str
    subject: str
    message: str
    status: str
    created_at: str


@dataclass(slots=True)
class Message:
    message_id: str
    conversation_id: str
    sender_user_id: str
    sender_name: str
    recipient_user_id: str
    recipient_name: str
    subject: str
    body: str
    created_at: str
    read_at: str | None


@dataclass(slots=True)
class ForumCategory:
    category_id: str
    slug: str
    name: str
    description: str
    sort_order: int


@dataclass(slots=True)
class ForumThread:
    thread_id: str
    category_id: str
    title: str
    excerpt: str
    body: str
    author_user_id: str
    author_name: str
    author_role: str
    tags: list[str]
    created_at: str
    updated_at: str
    reply_count: int
    view_count: int
    pinned: bool
    locked: bool


@dataclass(slots=True)
class ForumReply:
    reply_id: str
    thread_id: str
    author_user_id: str
    author_name: str
    author_role: str
    body: str
    created_at: str


# ---------------------------------------------------------------------------
# Seed content
# ---------------------------------------------------------------------------


USER_NAMES = [
    ("Alex", "M3Touring"),
    ("Brandon", "///M_TrackRat"),
    ("Chris", "F30Daily"),
    ("Dylan", "E92Collector"),
    ("Evan", "N54Tuner"),
    ("Felix", "LCI_Club"),
    ("Gabe", "PartsBench"),
    ("Henry", "DriveTrainGuy"),
    ("Ian", "RoadTrip330"),
    ("Jared", "GarageJournal"),
    ("Kevin", "M54Swap"),
    ("Liam", "BlackSapphire"),
    ("Marcus", "ServiceBay"),
    ("Noah", "DetailDays"),
    ("Owen", "TrackSpec"),
    ("Peter", "WeekendWrench"),
    ("Quinn", "BayAreaBMW"),
    ("Ryan", "BlueBookBuyer"),
    ("Sean", "EuroSpec"),
    ("Tyler", "TurbosAndTires"),
    ("Victor", "VINHunter"),
    ("Wyatt", "WinterReady"),
]


USER_ROLES = [
    "buyer",
    "seller",
    "dealer",
    "mechanic",
    "collector",
    "enthusiast",
]


LOCATIONS = [
    "Portland, OR",
    "Seattle, WA",
    "San Diego, CA",
    "Denver, CO",
    "Austin, TX",
    "Atlanta, GA",
    "Chicago, IL",
    "Boston, MA",
    "Charlotte, NC",
    "Phoenix, AZ",
    "Nashville, TN",
    "Tampa, FL",
]


AVATARS = [
    "https://images.example.com/avatars/bmw-01.png",
    "https://images.example.com/avatars/bmw-02.png",
    "https://images.example.com/avatars/bmw-03.png",
    "https://images.example.com/avatars/bmw-04.png",
    "https://images.example.com/avatars/bmw-05.png",
    "https://images.example.com/avatars/bmw-06.png",
]


BIO_SNIPPETS = [
    "Keeps a close eye on maintenance, updates, and clean OEM+ builds.",
    "Likes track prep, road trips, and comparing service notes.",
    "Buys, sells, and restores BMW parts one garage project at a time.",
    "Prefers well-documented cars and honest seller communication.",
    "Enjoys swap ideas, forum threads, and weekend wrenching.",
    "Always looking for the right spec, the right color, and the right history.",
]


LISTING_TITLES = [
    "2018 BMW M240i xDrive",
    "2016 BMW M3 Competition",
    "2015 BMW 340i Sport Package",
    "2019 BMW X3 M40i",
    "2014 BMW 435i Coupe",
    "2020 BMW M340i xDrive",
    "2017 BMW 330i M Sport",
    "2013 BMW 128i Sport",
    "2008 BMW E90 335i",
    "2021 BMW X5 xDrive40i",
    "2011 BMW 535i Manual Swap",
    "2012 BMW M5 Executive",
]


LISTING_DESCRIPTIONS = [
    "Clean history, well-kept service records, and tasteful upgrades only. The car presents exactly as a BMW should: sorted, sharp, and ready to enjoy.",
    "Adult-owned, garage-kept, and maintained on schedule. The chassis feels tight, the interior is crisp, and the platform has been responsibly refreshed.",
    "A strong driver with OEM+ parts, recent service, and no major surprises. Ideal for someone who wants a reliable entry into the platform.",
    "Track-day friendly setup with the right maintenance records. Suspension, brakes, and tires are all current, and the car is ready for the next enthusiast.",
]


PART_TITLES = [
    "OEM Adaptive LED Headlights",
    "M Performance Front Lip",
    "F80 Style Wheel Set",
    "Michelin Pilot Sport 4S Set",
    "Carbon Fiber Mirror Caps",
    "Genuine BMW Floor Mats",
    "Turbo Inlet Pipe Upgrade",
    "Airlift Suspension Kit",
    "Aluminum Charge Pipe",
    "OEM Roof Rack System",
    "Exhaust Valve Controller",
    "Performance Brake Pad Set",
]


PART_CATEGORIES = [
    "Exterior",
    "Interior",
    "Suspension",
    "Wheels",
    "Engine",
    "Lighting",
    "Audio",
    "Brakes",
]


THREAD_TITLE_TEMPLATES = [
    "Thinking about a {model} as a daily - what should I watch for?",
    "Best maintenance items after buying a {model}",
    "Worth paying extra for a clean history on a {model}?",
    "Project update: my {model} is finally back on the road",
    "Which wheels fit the {model} without rubbing?",
    "Dealer experience: did I overpay for this {model}?",
    "Parts question: genuine OEM vs aftermarket for the {model}",
    "Track setup feedback for my {model}",
    "Winter storage tips for a weekend {model}",
    "Anyone running this tire setup on a {model}?",
]


THREAD_BODY_TEMPLATES = [
    "I just picked up a car in this chassis and I’m trying to get ahead of the common issues. The service history looks decent, but I’d like to know what people usually inspect first once the car is home.",
    "The car is mostly stock with a few tasteful updates. I want to keep it reliable, but I’m open to the usual maintenance refresh list if it makes ownership easier long term.",
    "This one has a strong history and a pretty honest seller description. I’m interested in what everyone considers a fair price adjustment for mileage, condition, and records.",
    "I have been collecting parts for months and finally got the last piece installed. The car feels much better now, but I’m still debating a few details before I call the build finished.",
    "I’m trying to decide between keeping the OEM look and adding a couple of subtle upgrades. Nothing wild - just enough to make the car feel sorted without losing the factory character.",
]


REPLY_TEMPLATES = [
    "That looks like a solid starting point. I’d prioritize fluids, belts, and a full inspection so you know exactly what you’re working with.",
    "For a clean example, the price can make sense if the records are real and the wear items have already been handled.",
    "I ran the same setup on mine and the fit was fine. If you stay conservative on tire size, you should be in good shape.",
    "Nice progress. The car already looks balanced, and I think the tasteful direction is the right one for this chassis.",
    "If the history checks out, I would not hesitate too long. Good cars are still the easiest ones to justify later.",
    "I’d stay OEM on anything safety-related and save the aftermarket budget for parts that are easy to swap later.",
    "Mine had a similar issue and it turned out to be a small maintenance item rather than a major repair. Worth checking the basics first.",
    "This is exactly the kind of project update people like to see. It is clean, straightforward, and clearly headed in the right direction.",
]


FORUM_CATEGORY_SEEDS = [
    ("general-discussion", "General Discussion", "Daily BMW talk, ownership stories, and anything else that does not fit a more specific board.", 10),
    ("maintenance-repair", "Maintenance & Repair", "Service schedules, troubleshooting, and repair advice for all BMW generations.", 20),
    ("build-projects", "Build Projects", "Progress updates, photos, parts lists, and project planning for enthusiast builds.", 30),
    ("parts-market", "Parts & Accessories", "OEM, aftermarket, fitment questions, and parts buying or selling discussions.", 40),
    ("dealer-buyer", "Dealer & Buyer Talk", "Pricing, buying advice, and dealer experiences shared by shoppers and sellers.", 50),
    ("track-autocross", "Track & Autocross", "Lap-day prep, tire choices, suspension setup, and motorsport discussion.", 60),
]


def generate_users(num_users: int = 24) -> list[User]:
    users: list[User] = []
    for index in range(num_users):
        first_name, handle = USER_NAMES[index % len(USER_NAMES)]
        role = USER_ROLES[index % len(USER_ROLES)]
        location = LOCATIONS[index % len(LOCATIONS)]
        avatar_url = AVATARS[index % len(AVATARS)]
        bio = BIO_SNIPPETS[index % len(BIO_SNIPPETS)]
        user_id = f"user-{index + 1:03d}"
        full_name = f"{first_name} {handle.replace('_', ' ')}"
        display_name = handle.replace("_", " ")
        users.append(
            User(
                user_id=user_id,
                name=full_name,
                display_name=display_name,
                email=f"{slugify(display_name)}@example.com",
                role=role,
                location=location,
                avatar_url=avatar_url,
                bio=bio,
            )
        )
    return users


def generate_listings(users: list[User], num_listings: int = 18) -> list[Listing]:
    now = datetime(2024, 5, 1, tzinfo=timezone.utc)
    listings: list[Listing] = []
    body_styles = ["Sedan", "Coupe", "SUV", "Wagon", "Convertible"]
    transmissions = ["Automatic", "Manual"]
    fuel_types = ["Gasoline", "Turbo Gasoline"]
    drivetrains = ["RWD", "xDrive", "AWD"]
    conditions = ["Excellent", "Very Good", "Good"]

    for index in range(num_listings):
        seller = users[index % len(users)]
        title = LISTING_TITLES[index % len(LISTING_TITLES)]
        created = now - timedelta(days=60 - index * 2)
        updated = created + timedelta(days=RNG.randint(0, 18))
        year = int(title.split()[0])
        price = 14500 + index * 2350 + RNG.randint(-600, 1200)
        mileage = 32000 + index * 8400 + RNG.randint(0, 4500)
        excerpt = LISTING_DESCRIPTIONS[index % len(LISTING_DESCRIPTIONS)][:180]
        listings.append(
            Listing(
                listing_id=f"listing-{index + 1:03d}",
                seller_user_id=seller.user_id,
                seller_name=seller.display_name,
                seller_role=seller.role,
                title=title,
                slug=slugify(title),
                price=price,
                currency="USD",
                year=year,
                mileage=mileage,
                transmission=transmissions[index % len(transmissions)],
                fuel_type=fuel_types[index % len(fuel_types)],
                body_style=body_styles[index % len(body_styles)],
                color=["Black Sapphire", "Alpine White", "Portimao Blue", "Mineral Grey", "Brooklyn Grey"][index % 5],
                drivetrain=drivetrains[index % len(drivetrains)],
                exterior_condition=conditions[index % len(conditions)],
                interior_condition=conditions[(index + 1) % len(conditions)],
                description=LISTING_DESCRIPTIONS[index % len(LISTING_DESCRIPTIONS)],
                excerpt=excerpt,
                status="active" if index % 5 != 4 else "pending",
                featured=index % 4 == 0,
                images=[
                    f"https://images.example.com/listings/{index + 1:03d}-1.jpg",
                    f"https://images.example.com/listings/{index + 1:03d}-2.jpg",
                ],
                created_at=iso_datetime(created),
                updated_at=iso_datetime(updated),
            )
        )
    return listings


def generate_parts(users: list[User], num_parts: int = 20) -> list[Part]:
    now = datetime(2024, 5, 1, tzinfo=timezone.utc)
    parts: list[Part] = []
    conditions = ["New", "Like New", "Used", "Refurbished"]

    for index in range(num_parts):
        seller = users[(index + 3) % len(users)]
        title = PART_TITLES[index % len(PART_TITLES)]
        created = now - timedelta(days=40 - index)
        updated = created + timedelta(days=RNG.randint(0, 10))
        parts.append(
            Part(
                part_id=f"part-{index + 1:03d}",
                seller_user_id=seller.user_id,
                seller_name=seller.display_name,
                seller_role=seller.role,
                title=title,
                slug=slugify(title),
                price=RNG.randint(120, 2400),
                condition=conditions[index % len(conditions)],
                category=PART_CATEGORIES[index % len(PART_CATEGORIES)],
                description=(
                    "Carefully stored and ready for the next build. "
                    "Pictures and fitment notes available on request."
                ),
                featured=index % 6 == 0,
                images=[
                    f"https://images.example.com/parts/{index + 1:03d}-1.jpg",
                    f"https://images.example.com/parts/{index + 1:03d}-2.jpg",
                ],
                created_at=iso_datetime(created),
                updated_at=iso_datetime(updated),
            )
        )
    return parts


def generate_inquiries(users: list[User], listings: list[Listing], num_inquiries: int = 24) -> list[Inquiry]:
    inquiries: list[Inquiry] = []
    subjects = [
        "Is this still available?",
        "A few questions about maintenance history",
        "Interested in a test drive",
        "Can you share more photos?",
        "Would you consider a trade?",
    ]
    body_options = [
        "Hi, I’m interested in the car and wanted to ask about the service history and ownership records.",
        "The listing looks great. Could you let me know whether any recent maintenance has been completed?",
        "I’m local and can come by this week if the car is still available. Thanks for the time.",
        "Could you send a few more photos of the interior and engine bay when you get a chance?",
    ]
    status_cycle = ["new", "responded", "closed"]

    for index in range(num_inquiries):
        listing = listings[index % len(listings)]
        user = users[(index + 5) % len(users)]
        created = datetime(2024, 4, 10, tzinfo=timezone.utc) + timedelta(days=index)
        inquiries.append(
            Inquiry(
                inquiry_id=f"inquiry-{index + 1:03d}",
                listing_id=listing.listing_id,
                user_id=user.user_id,
                user_name=user.display_name,
                subject=subjects[index % len(subjects)],
                message=body_options[index % len(body_options)],
                status=status_cycle[index % len(status_cycle)],
                created_at=iso_datetime(created),
            )
        )
    return inquiries


def generate_messages(users: list[User], num_messages: int = 36) -> list[Message]:
    messages: list[Message] = []
    subjects = [
        "BMW listing follow-up",
        "More info on the service history",
        "Quick question about the part",
        "Ready to schedule a viewing",
        "Thanks for the update",
    ]
    body_options = [
        "Thanks for the quick reply. The details help a lot while I decide whether to move forward.",
        "I appreciate the photos and the extra notes. The car sounds like a strong fit for what I want.",
        "If the part is still available, I’d like to arrange payment and shipping details.",
        "That makes sense. Please keep me posted if anything changes with availability.",
    ]

    for index in range(num_messages):
        sender = users[index % len(users)]
        recipient = users[(index + 7) % len(users)]
        created = datetime(2024, 4, 1, tzinfo=timezone.utc) + timedelta(days=index // 2, hours=index % 12)
        messages.append(
            Message(
                message_id=f"message-{index + 1:03d}",
                conversation_id=f"conversation-{(index // 2) + 1:03d}",
                sender_user_id=sender.user_id,
                sender_name=sender.display_name,
                recipient_user_id=recipient.user_id,
                recipient_name=recipient.display_name,
                subject=subjects[index % len(subjects)],
                body=body_options[index % len(body_options)],
                created_at=iso_datetime(created),
                read_at=iso_datetime(created + timedelta(hours=6)) if index % 3 != 0 else None,
            )
        )
    return messages


def generate_forum_categories() -> list[ForumCategory]:
    categories: list[ForumCategory] = []
    for index, (slug, name, description, sort_order) in enumerate(FORUM_CATEGORY_SEEDS):
        categories.append(
            ForumCategory(
                category_id=f"forum-category-{index + 1:03d}",
                slug=slug,
                name=name,
                description=description,
                sort_order=sort_order,
            )
        )
    return categories


def _thread_title(category_slug: str, model_name: str, index: int) -> str:
    template = THREAD_TITLE_TEMPLATES[index % len(THREAD_TITLE_TEMPLATES)]
    return template.format(model=model_name if model_name else "BMW")


def _thread_body(category_name: str, model_name: str, index: int) -> str:
    intro = THREAD_BODY_TEMPLATES[index % len(THREAD_BODY_TEMPLATES)]
    closing = (
        f"Any advice from people who have owned {model_name} would be appreciated."
        if model_name
        else "Any advice from people who have been through this before would be appreciated."
    )
    if category_name == "Build Projects":
        closing = "I’ll keep posting updates as the build comes together."
    elif category_name == "Parts & Accessories":
        closing = "If anyone has fitment notes or part numbers, please share them."
    elif category_name == "Dealer & Buyer Talk":
        closing = "I’d love to hear how others handled negotiation on similar cars."
    elif category_name == "Track & Autocross":
        closing = "I’m especially interested in alignment, tire, and brake feedback."
    return f"{intro}\n\n{closing}"


def generate_forum_threads(users: list[User], categories: list[ForumCategory], num_threads: int) -> list[ForumThread]:
    threads: list[ForumThread] = []
    models = [
        "E90 335i",
        "F30 340i",
        "F82 M4",
        "E46 M3",
        "G20 M340i",
        "F10 M5",
        "E92 335is",
        "X3 M40i",
    ]
    base_created = datetime(2024, 4, 1, tzinfo=timezone.utc)

    category_threads = {
        category.category_id: 0 for category in categories
    }

    for index in range(num_threads):
        category = categories[index % len(categories)]
        category_threads[category.category_id] += 1
        model_name = models[index % len(models)]
        author = users[(index * 2 + 1) % len(users)]
        created = base_created + timedelta(days=index * 2, hours=(index % 8) * 2)
        updated = created + timedelta(hours=RNG.randint(1, 72))
        title = _thread_title(category.slug, model_name, index)
        body = _thread_body(category.name, model_name, index)
        excerpt = body.replace("\n", " ")[:180]
        tags = pick_many(
            [
                "bmw",
                "maintenance",
                "project",
                "fitment",
                "dealer",
                "pricing",
                "track",
                "oem",
                "aftermarket",
                "daily-driver",
            ],
            minimum=2,
            maximum=4,
        )
        threads.append(
            ForumThread(
                thread_id=f"forum-thread-{index + 1:04d}",
                category_id=category.category_id,
                title=title,
                excerpt=excerpt,
                body=body,
                author_user_id=author.user_id,
                author_name=author.display_name,
                author_role=author.role,
                tags=tags,
                created_at=iso_datetime(created),
                updated_at=iso_datetime(updated),
                reply_count=0,
                view_count=RNG.randint(28, 420),
                pinned=category.slug == "general-discussion" and index == 0,
                locked=index % 11 == 10,
            )
        )
    return threads


def generate_forum_replies(users: list[User], threads: list[ForumThread], num_replies: int) -> list[ForumReply]:
    replies: list[ForumReply] = []
    reply_time = datetime(2024, 4, 2, tzinfo=timezone.utc)
    for index in range(num_replies):
        thread = threads[index % len(threads)]
        author = users[(index * 3 + 4) % len(users)]
        created = reply_time + timedelta(days=index // 3, hours=index % 7)
        body = REPLY_TEMPLATES[index % len(REPLY_TEMPLATES)]
        if index % 5 == 0:
            body += " I would also check the maintenance log before making any decisions."
        replies.append(
            ForumReply(
                reply_id=f"forum-reply-{index + 1:04d}",
                thread_id=thread.thread_id,
                author_user_id=author.user_id,
                author_name=author.display_name,
                author_role=author.role,
                body=body,
                created_at=iso_datetime(created),
            )
        )
    return replies


def summarize_forum_threads(threads: list[ForumThread], replies: list[ForumReply]) -> list[ForumThread]:
    reply_counts: dict[str, int] = {}
    latest_reply_times: dict[str, str] = {}
    for reply in replies:
        reply_counts[reply.thread_id] = reply_counts.get(reply.thread_id, 0) + 1
        latest_reply_times[reply.thread_id] = max(latest_reply_times.get(reply.thread_id, reply.created_at), reply.created_at)

    updated_threads: list[ForumThread] = []
    for thread in threads:
        reply_count = reply_counts.get(thread.thread_id, 0)
        updated_at = thread.updated_at
        if thread.thread_id in latest_reply_times:
            updated_at = latest_reply_times[thread.thread_id]
        updated_threads.append(
            ForumThread(
                thread_id=thread.thread_id,
                category_id=thread.category_id,
                title=thread.title,
                excerpt=thread.excerpt,
                body=thread.body,
                author_user_id=thread.author_user_id,
                author_name=thread.author_name,
                author_role=thread.author_role,
                tags=thread.tags,
                created_at=thread.created_at,
                updated_at=updated_at,
                reply_count=reply_count,
                view_count=thread.view_count,
                pinned=thread.pinned,
                locked=thread.locked,
            )
        )
    return updated_threads


build_users = generate_users
build_listings = generate_listings
build_parts = generate_parts
build_inquiries = generate_inquiries
build_messages = generate_messages
build_forum_categories = generate_forum_categories
build_forum_threads = generate_forum_threads
build_forum_replies = generate_forum_replies


def seed_forum_data(users: list[User], num_threads: int = 18, num_replies: int = 42) -> tuple[list[ForumCategory], list[ForumThread], list[ForumReply]]:
    categories = generate_forum_categories()
    threads = generate_forum_threads(users, categories, num_threads=num_threads)
    replies = generate_forum_replies(users, threads, num_replies=num_replies)
    threads = summarize_forum_threads(threads, replies)
    return categories, threads, replies

# ---------------------------------------------------------------------------
# Seeding entrypoint
# ---------------------------------------------------------------------------


def seed_data() -> None:
    ensure_data_dir()

    users = generate_users()
    listings = generate_listings(users)
    parts = generate_parts(users)
    inquiries = generate_inquiries(users, listings)
    messages = generate_messages(users)

    forum_categories = generate_forum_categories()
    forum_threads = generate_forum_threads(users, forum_categories, num_threads=18)
    forum_replies = generate_forum_replies(users, forum_threads, num_replies=42)
    forum_threads = summarize_forum_threads(forum_threads, forum_replies)

    write_json(DATA_DIR / "users.json", [asdict(user) for user in users])
    write_json(DATA_DIR / "listings.json", [asdict(listing) for listing in listings])
    write_json(DATA_DIR / "parts.json", [asdict(part) for part in parts])
    write_json(DATA_DIR / "inquiries.json", [asdict(inquiry) for inquiry in inquiries])
    write_json(DATA_DIR / "messages.json", [asdict(message) for message in messages])

    write_json(DATA_DIR / "forum_categories.json", [asdict(category) for category in forum_categories])
    write_json(DATA_DIR / "forum_threads.json", [asdict(thread) for thread in forum_threads])
    write_json(DATA_DIR / "forum_replies.json", [asdict(reply) for reply in forum_replies])


def main() -> None:
    seed_data()
    print(f"Seed data written to {DATA_DIR}")


if __name__ == "__main__":
    main()