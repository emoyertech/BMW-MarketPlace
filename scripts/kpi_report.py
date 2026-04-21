#!/usr/bin/env python3
"""Print simple MVP KPIs from local JSON seed data."""

from __future__ import annotations

import json
from pathlib import Path


def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0%"
    return f"{(numerator / denominator) * 100:.1f}%"


def main() -> None:
    data_dir = Path("data")
    users = load_rows(data_dir / "users.json")
    listings = load_rows(data_dir / "listings.json")
    inquiries = load_rows(data_dir / "inquiries.json")

    buyers = [u for u in users if u["role"] == "BUYER"]
    dealers = [u for u in users if u["role"] == "DEALER"]
    private_sellers = [u for u in users if u["role"] == "PRIVATE_SELLER"]

    active_listings = [l for l in listings if l["status"] == "ACTIVE"]
    responded_inquiries = [i for i in inquiries if i["status"] in {"RESPONDED", "CLOSED"}]

    print("BMW Marketplace KPI Snapshot")
    print("=" * 32)
    print(f"Total users: {len(users)}")
    print(f"- Buyers: {len(buyers)}")
    print(f"- Dealers: {len(dealers)}")
    print(f"- Private sellers: {len(private_sellers)}")
    print()
    print(f"Total listings: {len(listings)}")
    print(f"- Active listings: {len(active_listings)} ({pct(len(active_listings), len(listings))})")
    print()
    print(f"Total inquiries: {len(inquiries)}")
    print(
        f"- Responded inquiries: {len(responded_inquiries)} "
        f"({pct(len(responded_inquiries), len(inquiries))})"
    )


if __name__ == "__main__":
    main()
