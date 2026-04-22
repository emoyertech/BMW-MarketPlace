#!/usr/bin/env python3
"""Generate local seed data for BMW Marketplace MVP testing.

This script creates sample users, listings, inquiries, and messages as JSON files
under the repository's data/ directory.
"""

from __future__ import annotations

import argparse
import hashlib
import csv
import json
import mimetypes
import random
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

RANDOM_SEED = 50
CURRENT_YEAR = datetime.now(timezone.utc).year
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_CSV_PATH = REPO_ROOT / "data" / "data_full.csv"
BMW_CATALOG_JSON_PATH = REPO_ROOT / "data" / "bmw_catalog.json"
SEED_IMAGES_DIR = REPO_ROOT / "data" / "seed-images"

BMW_MODELS = [
    "3 Series",
    "5 Series",
    "7 Series",
    "X3",
    "X5",
    "M3",
    "M4",
    "M5",
    "Z4",
    "i3",
    "i8",
    "X1",
    "X2",
    "X4",
    "X6",
    "X7",
    "2 Series",
    "4 Series",
    "6 Series",
    "8 Series",
    "M2",
    "M6",
    "M8",
    "Z3",
    "iX3",
    "i4",
    "iX",
]

LOCATIONS = ["San Diego, CA", "Los Angeles, CA", "San Jose, CA", "Phoenix, AZ", "Las Vegas, NV", "Denver, CO", "Seattle, WA", "Portland, OR", "Austin, TX", "Dallas, TX", "Miami, FL", "Orlando, FL", "Atlanta, GA", "Chicago, IL", "New York, NY", "Boston, MA", "Washington, DC", "Philadelphia, PA", "Minneapolis, MN", "Detroit, MI", "Columbus, OH", "Cleveland, OH", "Pittsburgh, PA", "Baltimore, MD", "Charlotte, NC", "Raleigh, NC", "Nashville, TN", "Memphis, TN", "Louisville, KY", "Indianapolis, IN", "Kansas City, MO", "St. Louis, MO", "Cincinnati, OH", "Milwaukee, WI", "Omaha, NE", "Albuquerque, NM", "Tucson, AZ", "Fresno, CA", "Sacramento, CA", "Long Beach, CA", "Mesa, AZ", "Virginia Beach, VA", "Oakland, CA", "Tulsa, OK", "Arlington, TX", "New Orleans, LA", "Wichita, KS", "Cleveland, OH", "Bakersfield, CA", "Aurora, CO", "Anaheim, CA", "Honolulu, HI", "Santa Ana, CA", "Riverside, CA", "Corpus Christi, TX", "Lexington, KY", "Henderson, NV", "Stockton, CA", "Saint Paul, MN", "Cincinnati, OH", "St. Louis, MO", "Pittsburgh, PA", "Greensboro, NC", "Lincoln, NE", "Plano, TX", "Orlando, FL", "Irvine, CA", "Newark, NJ", "Durham, NC", "Chula Vista, CA", "Toledo, OH", "Fort Wayne, IN", "St. Petersburg, FL"]

MODEL_YEAR_RANGES = {
    "2 Series": (2014, CURRENT_YEAR),
    "3 Series": (1976, CURRENT_YEAR),
    "4 Series": (2014, CURRENT_YEAR),
    "5 Series": (1972, CURRENT_YEAR),
    "6 Series": (1976, 2019),
    "7 Series": (1977, CURRENT_YEAR),
    "8 Series": (1990, CURRENT_YEAR),
    "X1": (2012, CURRENT_YEAR),
    "X2": (2018, CURRENT_YEAR),
    "X3": (2004, CURRENT_YEAR),
    "X4": (2015, CURRENT_YEAR),
    "X5": (2000, CURRENT_YEAR),
    "X6": (2008, CURRENT_YEAR),
    "X7": (2019, CURRENT_YEAR),
    "M2": (2016, CURRENT_YEAR),
    "M3": (1986, CURRENT_YEAR),
    "M4": (2015, CURRENT_YEAR),
    "M5": (1985, CURRENT_YEAR),
    "Z3": (1996, 2002),
    "Z4": (2003, CURRENT_YEAR),
    "i3": (2014, 2022),
    "i8": (2014, 2020),
    "i4": (2022, CURRENT_YEAR),
    "iX": (2022, CURRENT_YEAR),
    "iX3": (2021, CURRENT_YEAR),
    "M6": (1984, 2019),
    "M8": (2019, CURRENT_YEAR),
}

MODEL_BASE_PRICE = {
    "2 Series": 38000,
    "3 Series": 47000,
    "4 Series": 52000,
    "5 Series": 61000,
    "6 Series": 70000,
    "7 Series": 90000,
    "8 Series": 98000,
    "X1": 41000,
    "X2": 43000,
    "X3": 52000,
    "X4": 59000,
    "X5": 69000,
    "X6": 76000,
    "X7": 86000,
    "M2": 65000,
    "M3": 76000,
    "M4": 78000,
    "M5": 110000,
    "M6": 120000,
    "M8": 135000,
    "Z3": 30000,
    "Z4": 57000,
    "i3": 46000,
    "i4": 58000,
    "i8": 150000,
    "iX": 90000,
    "iX3": 70000,
}

EV_MODELS = {"i3", "i4", "i8", "iX", "iX3"}

TITLE_TYPE_WEIGHTS = [
    ("Clean", 82),
    ("Rebuilt", 7),
    ("Salvage", 6),
    ("Flood", 2),
    ("Lemon Buyback", 2),
    ("Hail Damage", 1),
]

TITLE_PRICE_FACTORS = {
    "Clean": (0.98, 1.03),
    "Rebuilt": (0.72, 0.86),
    "Salvage": (0.50, 0.68),
    "Flood": (0.42, 0.60),
    "Lemon Buyback": (0.68, 0.82),
    "Hail Damage": (0.78, 0.90),
}

BODY_STYLE_BY_MODEL = {
    "2 Series": ["Coupe", "Gran Coupe", "Convertible"],
    "3 Series": ["Sedan", "Wagon"],
    "4 Series": ["Coupe", "Gran Coupe", "Convertible"],
    "5 Series": ["Sedan"],
    "6 Series": ["Coupe", "Gran Coupe", "Convertible"],
    "7 Series": ["Sedan"],
    "8 Series": ["Coupe", "Gran Coupe", "Convertible"],
    "X1": ["SUV"],
    "X2": ["SUV"],
    "X3": ["SUV"],
    "X4": ["SUV Coupe"],
    "X5": ["SUV"],
    "X6": ["SUV Coupe"],
    "X7": ["SUV"],
    "M2": ["Coupe"],
    "M3": ["Sedan"],
    "M4": ["Coupe", "Convertible"],
    "M5": ["Sedan"],
    "M6": ["Coupe", "Gran Coupe", "Convertible"],
    "M8": ["Coupe", "Gran Coupe", "Convertible"],
    "Z3": ["Roadster", "Coupe"],
    "Z4": ["Roadster"],
    "i3": ["Hatchback"],
    "i4": ["Gran Coupe"],
    "i8": ["Coupe", "Roadster"],
    "iX": ["SUV"],
    "iX3": ["SUV"],
}

TRIMS_BY_MODEL = {
    "2 Series": ["230i", "230i xDrive", "M240i", "M240i xDrive"],
    "3 Series": ["320i", "328i", "330i", "330e", "335i", "340i", "330i xDrive", "M340i xDrive"],
    "4 Series": ["430i", "430i xDrive", "M440i", "M440i xDrive"],
    "5 Series": ["525i", "528i", "530i", "530e", "535i", "540i", "540i xDrive", "545i", "550i", "550i xDrive", "M550i xDrive"],
    "6 Series": ["640i", "650i", "650i xDrive"],
    "7 Series": ["740i", "740i xDrive", "750i xDrive", "760i"],
    "8 Series": ["840i", "840i xDrive", "M850i xDrive"],
    "X1": ["sDrive28i", "xDrive28i"],
    "X2": ["sDrive28i", "xDrive28i", "M35i"],
    "X3": ["sDrive30i", "xDrive30i", "M40i"],
    "X4": ["xDrive30i", "M40i"],
    "X5": ["xDrive40i", "xDrive45e", "xDrive50e", "M50i", "M60i"],
    "X6": ["xDrive40i", "M50i", "M60i"],
    "X7": ["xDrive40i", "M60i", "ALPINA XB7"],
    "M2": ["Base", "Competition", "CS"],
    "M3": ["Base", "Competition", "Competition xDrive"],
    "M4": ["Base", "Competition", "Competition xDrive"],
    "M5": ["Base", "Competition", "CS"],
    "M6": ["Base", "Competition"],
    "M8": ["Competition Coupe", "Competition Gran Coupe", "Competition Convertible"],
    "Z3": ["2.3", "2.8", "3.0", "M Roadster", "M Coupe"],
    "Z4": ["sDrive30i", "M40i"],
    "i3": ["BEV", "REx", "S"],
    "i4": ["eDrive35", "eDrive40", "xDrive40", "M50"],
    "i8": ["Coupe", "Roadster"],
    "iX": ["xDrive40", "xDrive50", "M60"],
    "iX3": ["M Sport", "Inspiring"],
}


def possible_trims(model: str, year: int) -> list[str]:
    if model == "5 Series":
        if year <= 2010:
            return ["525i", "528i", "530i", "535i", "540i", "545i", "550i"]
        if year <= 2016:
            return ["528i", "535i", "550i", "550i xDrive"]
        return ["530i", "530e", "540i", "540i xDrive", "M550i xDrive"]

    if model == "3 Series":
        if year <= 2011:
            return ["325i", "328i", "330i", "335i"]
        return ["330i", "330e", "340i", "330i xDrive", "M340i xDrive"]
    
    if model == "X5":
        if year <= 2013:
            return ["xDrive35i", "xDrive50i"]
        if year <= 2020:
            return ["xDrive35i", "xDrive40e", "xDrive50i", "M50i"]
        return ["xDrive40i", "xDrive45e", "xDrive50e", "M50i", "M60i"]
    
    if model == "X6":
        if year <= 2014:
            return ["xDrive35i", "xDrive50i"]
        if year <= 2020:
            return ["xDrive35i", "xDrive40e", "xDrive50i", "M50i"]
        return ["xDrive40i", "M50i", "M60i"]
    
    if model == "7 Series":
        if year <= 2012:
            return ["740i", "750i", "760i"]
        if year <= 2019:
            return ["740i", "750i xDrive", "750i", "760i"]
        return ["740i", "740i xDrive", "750i xDrive", "760i"]
    
    if model == "8 Series":
        if year <= 2019:
            return ["840i", "M850i xDrive"]
        return ["840i", "840i xDrive", "M850i xDrive"]
    
    if model == "M3":
        if year <= 2013:
            return ["Base", "Competition"]
        return ["Base", "Competition", "Competition xDrive"]
    
    if model == "M4":
        if year <= 2013:
            return ["Base", "Competition"]
        return ["Base", "Competition", "Competition xDrive"]
    
    if model == "M5":
        if year <= 2012:
            return ["Base", "Competition"]
        return ["Base", "Competition", "CS"]
    
    if model == "M6":
        if year <= 2012:
            return ["Base", "Competition"]
        return ["Base", "Competition"]
    
    if model == "M8":
        if year <= 2019:
            return ["Competition Coupe", "Competition Gran Coupe", "Competition Convertible"]
        return ["Competition Coupe", "Competition Gran Coupe", "Competition Convertible"]
    
    if model == "i3":
        if year <= 2016:
            return ["BEV", "REx"]
        return ["BEV", "REx", "S"]
    
    if model == "i4":
        if year <= 2022:
            return ["eDrive35", "eDrive40"]
        return ["eDrive35", "eDrive40", "xDrive40", "M50"]
    
    if model == "iX":
        if year <= 2022:
            return ["xDrive40", "xDrive50"]
        return ["xDrive40", "xDrive50", "M60"]
    
    if model == "iX3":
        if year <= 2021:
            return ["M Sport"]
        return ["M Sport", "Inspiring"]
    
    if model == "Z3":
        if year <= 1999:
            return ["2.3", "2.8", "M Roadster", "M Coupe"]
        return ["2.8", "3.0", "M Roadster", "M Coupe"]
    
    if model == "Z4":
        if year <= 2006:
            return ["3.0i", "M Roadster", "M Coupe"]
        return ["sDrive30i", "M40i"]
    
    if model == "2 Series":
        if year <= 2015:
            return ["230i", "M235i"]
        return ["230i", "230i xDrive", "M240i", "M240i xDrive"]
    
    if model == "4 Series":
        if year <= 2015:
            return ["428i", "435i"]
        return ["430i", "430i xDrive", "M440i", "M440i xDrive"]
    
    if model == "1 Series":
        if year <= 2011:
            return ["128i", "135i"]
        return ["128i", "135i", "135is"]
    
    return TRIMS_BY_MODEL.get(model, ["Base"])


def pick_trim(model: str, year: int) -> str:
    return random.choice(possible_trims(model, year))


def pick_title_type() -> str:
    labels, weights = zip(*TITLE_TYPE_WEIGHTS)
    return random.choices(labels, weights=weights, k=1)[0]


def pick_body_style(model: str) -> str:
    return random.choice(BODY_STYLE_BY_MODEL.get(model, ["Sedan"]))


def infer_drive_type(model: str, trim: str) -> str:
    t = trim.lower()
    if "xdrive" in t:
        return "AWD"
    if model in EV_MODELS:
        if "xdrive" in t:
            return "AWD"
        return random.choice(["RWD", "AWD"])
    if model.startswith("X"):
        return random.choice(["AWD", "RWD"])
    if model.startswith("M"):
        return random.choice(["RWD", "AWD"])
    return random.choice(["RWD", "AWD"])


def apply_title_price_adjustment(price: int, title_type: str, year: int) -> int:
    low, high = TITLE_PRICE_FACTORS.get(title_type, (1.0, 1.0))
    adjusted = int(price * random.uniform(low, high))
    floor_price = 5_500 if year <= 2005 else 8_000
    return max(floor_price, adjusted)


def normalize_bmw_name(value: str) -> str:
    value = value.strip()
    if value.upper().startswith("BMW "):
        value = value[4:]
    value = re.sub(r"(?<=\d)Series", " Series", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_year_list(value: str) -> list[int]:
    years: list[int] = []
    for item in parse_csv_list(value):
        try:
            years.append(int(item))
        except ValueError:
            continue
    return years


def select_catalog_image(image_urls: list[str], listing_index: int) -> str:
    if not image_urls:
        return ""
    return image_urls[(listing_index - 1) % len(image_urls)]


def cache_seed_image(image_url: str, fallback_name: str) -> str:
    if not image_url:
        return ""

    SEED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(image_url)
    suffix = Path(parsed.path).suffix.lower()
    if not suffix:
        suffix = mimetypes.guess_extension(mimetypes.guess_type(parsed.path)[0] or "") or ".jpg"

    file_name = f"{hashlib.sha256(image_url.encode('utf-8')).hexdigest()[:24]}{suffix}"
    output_path = SEED_IMAGES_DIR / file_name
    if output_path.exists():
        return f"/seed-images/{file_name}"

    try:
        request = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=12) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                raise ValueError(f"Unexpected content type: {content_type}")
            output_path.write_bytes(response.read())
        return f"/seed-images/{file_name}"
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        fallback_svg = build_svg_data_uri(fallback_name, "Seed Image", CURRENT_YEAR, "Catalog", 1)
        return fallback_svg


def infer_bmw_family(name: str) -> str:
    normalized = normalize_bmw_name(name)
    if not normalized:
        return "X5"

    if normalized.startswith("iX3"):
        return "iX3"
    if normalized.startswith("iX"):
        return "iX"
    if normalized.startswith("i4"):
        return "i4"
    if normalized.startswith("i3"):
        return "i3"

    if normalized.startswith("M8"):
        return "M8"
    if normalized.startswith("M6"):
        return "M6"
    if normalized.startswith("M5"):
        return "M5"
    if normalized.startswith("M4"):
        return "M4"
    if normalized.startswith("M3"):
        return "M3"
    if normalized.startswith("M2"):
        return "M2"

    if normalized.startswith("X7"):
        return "X7"
    if normalized.startswith("X6"):
        return "X6"
    if normalized.startswith("X5"):
        return "X5"
    if normalized.startswith("X4"):
        return "X4"
    if normalized.startswith("X3"):
        return "X3"
    if normalized.startswith("X2"):
        return "X2"
    if normalized.startswith("X1"):
        return "X1"

    if "8 Series" in normalized:
        return "8 Series"
    if "7 Series" in normalized:
        return "7 Series"
    if "6 Series" in normalized:
        return "6 Series"
    if "5 Series" in normalized:
        return "5 Series"
    if "4 Series" in normalized:
        return "4 Series"
    if "3 Series" in normalized:
        return "3 Series"
    if "2 Series" in normalized:
        return "2 Series"

    return normalized.split()[0]


def catalog_display_name(entry: dict) -> str:
    raw_value = entry.get("title") or entry.get("model") or "BMW"
    raw_value = re.sub(r"^\d{4}\s+", "", raw_value).strip()
    if raw_value.upper().startswith("BMW "):
        raw_value = raw_value[4:]
    suffix_patterns = [
        r"\b[FGUKWLR]\d{2,3}[A-Z]?\b$",
        r"\b(?:\d{4}\s*[-–/]?\s*\d{4}|\d{8}|\d{4}\s*(?:Present|Current|present|current))\b$",
        r"\b(?:LCI|Facelift|Life Cycle Impulse)\b$",
    ]
    previous_value = None
    while raw_value and raw_value != previous_value:
        previous_value = raw_value
        for pattern in suffix_patterns:
            raw_value = re.sub(pattern, "", raw_value, flags=re.IGNORECASE).strip()
    raw_value = re.sub(r"\s{2,}", " ", raw_value)
    raw_value = re.sub(r"\s*[-–]\s*", " ", raw_value)
    raw_value = normalize_bmw_name(raw_value)
    return raw_value.strip() or infer_bmw_family(raw_value)


def load_bmw_catalog() -> list[dict]:
    if not SOURCE_CSV_PATH.exists():
        return []

    catalog: list[dict] = []
    with SOURCE_CSV_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if len(row) < 44:
                continue

            brand = row[0].strip().upper()
            if brand != "BMW":
                continue

            image_urls = parse_csv_list(row[40])
            if not image_urls:
                continue

            production_years = parse_year_list(row[2])
            from_year = row[3].strip()
            to_year = row[4].strip()

            catalog.append(
                {
                    "brand": brand,
                    "model": normalize_bmw_name(row[1]),
                    "title": row[7].strip(),
                    "description": row[8].strip(),
                    "segment": row[6].strip(),
                    "body_style": row[5].strip(),
                    "drive_type": row[18].strip(),
                    "from_year": int(from_year) if from_year.isdigit() else None,
                    "to_year": int(to_year) if to_year.isdigit() else None,
                    "production_years": production_years,
                    "image_urls": image_urls,
                    "image_file_names": parse_csv_list(row[41]),
                    "dir_path": row[42].strip(),
                    "total_images": int(row[43] or 0),
                }
            )

    with BMW_CATALOG_JSON_PATH.open("w", encoding="utf-8") as json_file:
        json.dump(catalog, json_file, indent=2)

    return catalog


def generate_catalog_listings(users: List[User], num_listings: int, catalog: list[dict]) -> List[Listing]:
    seller_users = [u for u in users if u.role in {"DEALER", "PRIVATE_SELLER"}]
    listings: List[Listing] = []

    if not seller_users or not catalog:
        return listings

    catalog_cycle = catalog[:]
    random.shuffle(catalog_cycle)

    for i in range(1, num_listings + 1):
        cycle_index = (i - 1) % len(catalog_cycle)
        if cycle_index == 0 and i != 1:
            random.shuffle(catalog_cycle)

        seller = random.choice(seller_users)
        catalog_entry = catalog_cycle[cycle_index]
        family = infer_bmw_family(catalog_entry.get("model", catalog_entry.get("title", "")))
        title_type = pick_title_type()
        model_name = catalog_display_name(catalog_entry)

        years = catalog_entry.get("production_years") or []
        if years:
            year = random.choice(years)
        else:
            start_year = catalog_entry.get("from_year") or 2000
            end_year = catalog_entry.get("to_year") or CURRENT_YEAR
            year = random.randint(start_year, end_year)

        age = max(0, CURRENT_YEAR - year)
        mileage_low, mileage_high = annual_mileage_range(family)
        mileage = min(
            (age * random.randint(mileage_low, mileage_high)) + random.randint(2_000, 14_000),
            260_000 if year <= 2005 else 220_000,
        )

        base_price = MODEL_BASE_PRICE.get(family, 55_000)
        depreciation = 0.89 ** age
        price = max(6_500 if year <= 2005 else 9_500, int(base_price * depreciation * random.uniform(0.9, 1.1)))

        catalog_images = list(dict.fromkeys(catalog_entry.get("image_urls", [])))[:6]
        primary_source = select_catalog_image(catalog_entry.get("image_urls", []), i)
        image_url = cache_seed_image(primary_source, model_name) if primary_source else build_image_url(model_name, catalog_entry.get("segment", "Base"), year, catalog_entry.get("body_style", ""), i)
        gallery_images = [
            cache_seed_image(image_url_source, model_name)
            for image_url_source in catalog_images
            if image_url_source
        ]
        listings.append(
            Listing(
                listing_id=f"listing-{i}",
                seller_user_id=seller.user_id,
                seller_type=seller.role,
                model=model_name,
                trim=catalog_entry.get("segment", "Base"),
                body_style=catalog_entry.get("body_style", ""),
                drive_type=catalog_entry.get("drive_type", ""),
                title_type=title_type,
                image_url=image_url,
                description=catalog_entry.get("description", ""),
                gallery_images=gallery_images,
                year=year,
                mileage=mileage,
                price=apply_title_price_adjustment(price, title_type, year),
                location=random.choice(LOCATIONS),
                status="ACTIVE",
                created_at=_ts(random.randint(1, 30)),
            )
        )

    return listings


def build_svg_data_uri(model: str, trim: str, year: int, body_style: str, listing_index: int) -> str:
        # Stable color palette so each card looks distinct but deterministic.
        palette = [
                ("#0b57d0", "#0f172a"),
                ("#1d4ed8", "#111827"),
                ("#0f766e", "#1f2937"),
                ("#b45309", "#1f2937"),
                ("#7c3aed", "#111827"),
                ("#be123c", "#111827"),
        ]
        primary, secondary = palette[listing_index % len(palette)]

        label = f"{year} BMW {model}"
        sublabel = f"{trim} | {body_style}"

        svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' width='960' height='640' viewBox='0 0 960 640'>
    <defs>
        <linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>
            <stop offset='0%' stop-color='{primary}'/>
            <stop offset='100%' stop-color='{secondary}'/>
        </linearGradient>
    </defs>
    <rect width='960' height='640' fill='url(#bg)'/>
    <g opacity='0.18' fill='none' stroke='white' stroke-width='2'>
        <circle cx='140' cy='120' r='80'/>
        <circle cx='820' cy='140' r='110'/>
        <circle cx='760' cy='520' r='130'/>
    </g>
    <g transform='translate(130,290)'>
        <rect x='0' y='45' rx='28' ry='28' width='700' height='120' fill='rgba(255,255,255,0.9)'/>
        <rect x='120' y='0' rx='22' ry='22' width='360' height='80' fill='rgba(255,255,255,0.85)'/>
        <circle cx='170' cy='190' r='52' fill='#111827'/>
        <circle cx='170' cy='190' r='24' fill='#9ca3af'/>
        <circle cx='560' cy='190' r='52' fill='#111827'/>
        <circle cx='560' cy='190' r='24' fill='#9ca3af'/>
    </g>
    <text x='48' y='78' fill='white' font-size='44' font-family='Segoe UI, Arial, sans-serif' font-weight='700'>{label}</text>
    <text x='48' y='122' fill='white' font-size='28' font-family='Segoe UI, Arial, sans-serif'>{sublabel}</text>
    <text x='48' y='594' fill='rgba(255,255,255,0.9)' font-size='20' font-family='Segoe UI, Arial, sans-serif'>BMW Marketplace Seed Image</text>
</svg>
""".strip()

        return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def build_image_url(model: str, trim: str, year: int, body_style: str, listing_index: int) -> str:
    return build_svg_data_uri(model, trim, year, body_style, listing_index)


@dataclass
class User:
    user_id: str
    role: str
    full_name: str
    email: str
    created_at: str


@dataclass
class Listing:
    listing_id: str
    seller_user_id: str
    seller_type: str
    model: str
    trim: str
    body_style: str
    drive_type: str
    title_type: str
    image_url: str
    description: str
    gallery_images: list[str]
    year: int
    mileage: int
    price: int
    location: str
    status: str
    created_at: str


@dataclass
class Inquiry:
    inquiry_id: str
    listing_id: str
    buyer_user_id: str
    seller_user_id: str
    status: str
    created_at: str


@dataclass
class Message:
    message_id: str
    inquiry_id: str
    sender_user_id: str
    body: str
    sent_at: str


def _ts(days_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


def model_year_range(model: str) -> tuple[int, int]:
    if model in MODEL_YEAR_RANGES:
        return MODEL_YEAR_RANGES[model]
    return (2006, CURRENT_YEAR)


def annual_mileage_range(model: str) -> tuple[int, int]:
    if model.startswith("M"):
        return (3_000, 9_000)
    if model in EV_MODELS:
        return (4_000, 11_000)
    if model in {"7 Series", "8 Series", "X7"}:
        return (4_000, 10_000)
    return (6_000, 14_000)


def generate_vehicle_numbers(model: str) -> tuple[int, int, int]:
    min_year, max_year = model_year_range(model)
    year = random.randint(min_year, max_year)
    age = max(0, CURRENT_YEAR - year)

    per_year_low, per_year_high = annual_mileage_range(model)
    base = age * random.randint(per_year_low, per_year_high)
    starter_miles = random.randint(1_000, 12_000) if age <= 1 else random.randint(3_000, 18_000)
    mileage = base + starter_miles

    # Keep old cars plausible without creating extreme outliers for modern vehicles.
    max_miles = 260_000 if year <= 2005 else 220_000
    mileage = min(mileage, max_miles)

    base_price = MODEL_BASE_PRICE.get(model, 45_000)
    depreciation = 0.87 ** age
    expected_miles = age * 12_000
    excess_miles = max(0, mileage - expected_miles)
    mileage_penalty = (excess_miles // 1_000) * 110

    raw_price = int(base_price * depreciation * random.uniform(0.92, 1.08) - mileage_penalty)
    floor_price = 5_500 if year <= 2005 else 9_000
    price = max(floor_price, raw_price)

    return year, mileage, price


def generate_users(num_buyers: int, num_dealers: int, num_private_sellers: int) -> List[User]:
    users: List[User] = []

    for i in range(1, num_buyers + 1):
        users.append(
            User(
                user_id=f"buyer-{i}",
                role="BUYER",
                full_name=f"Buyer {i}",
                email=f"buyer{i}@example.com",
                created_at=_ts(random.randint(1, 30)),
            )
        )

    for i in range(1, num_dealers + 1):
        users.append(
            User(
                user_id=f"dealer-{i}",
                role="DEALER",
                full_name=f"Dealer {i}",
                email=f"dealer{i}@example.com",
                created_at=_ts(random.randint(1, 30)),
            )
        )

    for i in range(1, num_private_sellers + 1):
        users.append(
            User(
                user_id=f"seller-{i}",
                role="PRIVATE_SELLER",
                full_name=f"Private Seller {i}",
                email=f"seller{i}@example.com",
                created_at=_ts(random.randint(1, 30)),
            )
        )

    return users


def generate_listings(users: List[User], num_listings: int) -> List[Listing]:
    seller_users = [u for u in users if u.role in {"DEALER", "PRIVATE_SELLER"}]
    listings: List[Listing] = []

    for i in range(1, num_listings + 1):
        seller = random.choice(seller_users)
        model = random.choice(BMW_MODELS)
        year, mileage, price = generate_vehicle_numbers(model)
        trim = pick_trim(model, year)
        body_style = pick_body_style(model)
        drive_type = infer_drive_type(model, trim)
        title_type = pick_title_type()
        image_url = build_image_url(model, trim, year, body_style, i)
        price = apply_title_price_adjustment(price, title_type, year)
        listings.append(
            Listing(
                listing_id=f"listing-{i}",
                seller_user_id=seller.user_id,
                seller_type=seller.role,
                model=model,
                trim=trim,
                body_style=body_style,
                drive_type=drive_type,
                title_type=title_type,
                image_url=image_url,
                description=f"{year} BMW {model} with {trim} trim and {body_style.lower() if body_style else 'BMW styling'}.",
                gallery_images=[image_url],
                year=year,
                mileage=mileage,
                price=price,
                location=random.choice(LOCATIONS),
                status="ACTIVE",
                created_at=_ts(random.randint(1, 30)),
            )
        )

    return listings


def generate_inquiries(users: List[User], listings: List[Listing], num_inquiries: int) -> List[Inquiry]:
    buyers = [u for u in users if u.role == "BUYER"]
    active_listings = [l for l in listings if l.status == "ACTIVE"]
    inquiries: List[Inquiry] = []

    for i in range(1, num_inquiries + 1):
        listing = random.choice(active_listings)
        buyer = random.choice(buyers)
        inquiries.append(
            Inquiry(
                inquiry_id=f"inquiry-{i}",
                listing_id=listing.listing_id,
                buyer_user_id=buyer.user_id,
                seller_user_id=listing.seller_user_id,
                status=random.choice(["NEW", "RESPONDED", "CLOSED"]),
                created_at=_ts(random.randint(0, 14)),
            )
        )

    return inquiries


def generate_messages(inquiries: List[Inquiry]) -> List[Message]:
    messages: List[Message] = []

    for i, inquiry in enumerate(inquiries, start=1):
        messages.append(
            Message(
                message_id=f"message-{i*2-1}",
                inquiry_id=inquiry.inquiry_id,
                sender_user_id=inquiry.buyer_user_id,
                body="Hi, is this BMW still available?",
                sent_at=_ts(random.randint(0, 10)),
            )
        )

        if inquiry.status in {"RESPONDED", "CLOSED"}:
            messages.append(
                Message(
                    message_id=f"message-{i*2}",
                    inquiry_id=inquiry.inquiry_id,
                    sender_user_id=inquiry.seller_user_id,
                    body="Yes, it is available. Let me know if you want to schedule a viewing.",
                    sent_at=_ts(random.randint(0, 10)),
                )
            )

    return messages


def write_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample BMW Marketplace data")
    parser.add_argument("--buyers", type=int, default=15, help="Number of buyer users")
    parser.add_argument("--dealers", type=int, default=5, help="Number of dealer users")
    parser.add_argument("--private-sellers", type=int, default=8, help="Number of private sellers")
    parser.add_argument("--listings", type=int, default=100, help="Number of listings")
    parser.add_argument("--inquiries", type=int, default=80, help="Number of inquiries")
    parser.add_argument(
        "--out-dir",
        default="data",
        help="Output directory for generated JSON files (default: data)",
    )
    args = parser.parse_args()

    random.seed(RANDOM_SEED)

    users = generate_users(args.buyers, args.dealers, args.private_sellers)
    bmw_catalog = load_bmw_catalog()
    if bmw_catalog:
        listings = generate_catalog_listings(users, args.listings, bmw_catalog)
    else:
        listings = generate_listings(users, args.listings)
    inquiries = generate_inquiries(users, listings, args.inquiries)
    messages = generate_messages(inquiries)

    out_dir = Path(args.out_dir)
    write_json(out_dir / "users.json", [asdict(x) for x in users])
    write_json(out_dir / "listings.json", [asdict(x) for x in listings])
    write_json(out_dir / "inquiries.json", [asdict(x) for x in inquiries])
    write_json(out_dir / "messages.json", [asdict(x) for x in messages])

    print("Seed data generated:")
    print(f"- {out_dir / 'users.json'} ({len(users)} rows)")
    print(f"- {out_dir / 'listings.json'} ({len(listings)} rows)")
    print(f"- {out_dir / 'inquiries.json'} ({len(inquiries)} rows)")
    print(f"- {out_dir / 'messages.json'} ({len(messages)} rows)")


if __name__ == "__main__":
    main()
