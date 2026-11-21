"""Clean synthetic tables and their schemas. Seeded, so the same seed gives the same table.

A schema is the user's spec for the clean file: column names in order, a type for each,
ranges, allowed values, a unique key and the columns that identify a record. It holds no
rows from any file.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

FIRST = [
    "Ana", "Ben", "Chloe", "Dev", "Elena", "Femi", "Grace", "Hiro", "Ines", "Jamal",
    "Kira", "Liam", "Maya", "Noah", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tara",
    "José", "Zoë", "Renée", "André", "Björn", "Lucía", "Søren", "Chloé",
]  # fmt: skip
LAST = [
    "Lopez", "Smith", "Nguyen", "Patel", "Okafor", "Kim", "Garcia", "Brown", "Rossi",
    "Cohen", "Ali", "Jones", "Silva", "Tanaka", "Moore", "Reyes", "Clark", "Diaz",
    "Müller", "Núñez", "Ångström", "Dupré", "Çelik", "O'Brien",
]  # fmt: skip
CITIES = [("Austin", "TX"), ("Dallas", "TX"), ("Denver", "CO"), ("Chicago", "IL"),
          ("Boston", "MA"), ("Seattle", "WA"), ("Miami", "FL"), ("Phoenix", "AZ")]  # fmt: skip
SEGMENTS = ["Retail", "Wholesale", "Online", "Enterprise"]
CATEGORIES = ["Electronics", "Furniture", "Office Supplies", "Grocery", "Clothing"]
WAREHOUSES = ["Austin", "Dallas", "Houston", "Chicago"]
PRODUCTS = {
    "Electronics": ["USB Cable", "Monitor", "Keyboard", "Headset", "Router", "Webcam"],
    "Furniture": ["Desk", "Chair", "Shelf", "Cabinet", "Lamp", "Stool"],
    "Office Supplies": ["Stapler", "Paper Ream", "Pen Box", "Binder", "Tape", "Folder"],
    "Grocery": ["Coffee Beans", "Green Tea", "Rice Bag", "Olive Oil", "Oat Mix", "Honey"],
    "Clothing": ["T Shirt", "Hoodie", "Cap", "Jacket", "Socks", "Apron"],
}
START = date(2023, 1, 1)


def _day(rng: random.Random) -> str:
    return (START + timedelta(days=rng.randrange(0, 900))).isoformat()


SCHEMAS = {
    "customers": {
        "key": "customer_id",
        "dedupe_on": ["first_name", "last_name", "email", "phone"],
        "columns": {
            "customer_id": {"type": "str", "example": "C00000"},
            "first_name": {"type": "str"},
            "last_name": {"type": "str"},
            "email": {"type": "str"},
            "phone": {"type": "str", "example": "512-555-0134"},
            "signup_date": {"type": "date"},
            "city": {"type": "str"},
            "segment": {"type": "str", "allowed": SEGMENTS},
            "lifetime_value": {"type": "money", "min": 0, "max": 50000},
        },
    },
    "orders": {
        "key": "order_id",
        "dedupe_on": ["customer_id", "order_date", "category", "quantity"],
        "columns": {
            "order_id": {"type": "str", "example": "O00000"},
            "customer_id": {"type": "str", "example": "C00000"},
            "order_date": {"type": "date"},
            "category": {"type": "str", "allowed": CATEGORIES},
            "quantity": {"type": "int", "min": 1, "max": 50},
            "unit_price": {"type": "money", "min": 0, "max": 5000},
            "weight_kg": {"type": "float", "unit": "kg", "min": 0, "max": 500},
            "ship_city": {"type": "str"},
            "ship_state": {"type": "str"},
        },
    },
    "inventory": {
        "key": "sku",
        "dedupe_on": ["product_name", "warehouse", "last_restock"],
        "columns": {
            "sku": {"type": "str", "example": "SKU-0000"},
            "product_name": {"type": "str"},
            "category": {"type": "str", "allowed": CATEGORIES},
            "stock": {"type": "int", "min": 0, "max": 5000},
            "unit_cost": {"type": "money", "min": 0, "max": 5000},
            "weight_kg": {"type": "float", "unit": "kg", "min": 0, "max": 500},
            "last_restock": {"type": "date"},
            "warehouse": {"type": "str", "allowed": WAREHOUSES},
        },
    },
}


def _customers(rng: random.Random, n: int) -> list[dict]:
    rows, seen = [], set()
    for i in range(1, n + 1):
        while True:
            first, last = rng.choice(FIRST), rng.choice(LAST)
            num = rng.randrange(10, 99)
            if (first, last, num) not in seen:
                seen.add((first, last, num))
                break
        city, _ = rng.choice(CITIES)
        ascii_first = first.encode("ascii", "ignore").decode().lower() or "user"
        ascii_last = "".join(c for c in last.lower() if c.isascii() and c.isalpha()) or "x"
        rows.append(
            {
                "customer_id": f"C{i:05d}",
                "first_name": first,
                "last_name": last,
                "email": f"{ascii_first}.{ascii_last}{num}@mail.test",
                "phone": f"{rng.randrange(200, 999)}-555-{rng.randrange(0, 9999):04d}",
                "signup_date": _day(rng),
                "city": city,
                "segment": rng.choice(SEGMENTS),
                "lifetime_value": f"{rng.uniform(20, 9000):.2f}",
            }
        )
    return rows


def _orders(rng: random.Random, n: int) -> list[dict]:
    rows, seen = [], set()
    for i in range(1, n + 1):
        while True:
            cust, day, cat, qty = (
                f"C{rng.randrange(1, 400):05d}",
                _day(rng),
                rng.choice(CATEGORIES),
                str(rng.randrange(1, 20)),
            )
            if (cust, day, cat, qty) not in seen:
                seen.add((cust, day, cat, qty))
                break
        city, state = rng.choice(CITIES)
        rows.append(
            {
                "order_id": f"O{i:05d}",
                "customer_id": cust,
                "order_date": day,
                "category": cat,
                "quantity": qty,
                "unit_price": f"{rng.uniform(2, 1500):.2f}",
                "weight_kg": f"{rng.uniform(0.2, 60):.2f}",
                "ship_city": city,
                "ship_state": state,
            }
        )
    return rows


def _inventory(rng: random.Random, n: int) -> list[dict]:
    rows, seen = [], set()
    for i in range(1, n + 1):
        while True:
            cat = rng.choice(CATEGORIES)
            name = f"{rng.choice(PRODUCTS[cat])} {rng.choice('ABCDEFGH')}{rng.randrange(1, 99)}"
            wh, day = rng.choice(WAREHOUSES), _day(rng)
            if (name, wh, day) not in seen:
                seen.add((name, wh, day))
                break
        rows.append(
            {
                "sku": f"SKU-{i:04d}",
                "product_name": name,
                "category": cat,
                "stock": str(rng.randrange(0, 2000)),
                "unit_cost": f"{rng.uniform(1, 900):.2f}",
                "weight_kg": f"{rng.uniform(0.1, 80):.2f}",
                "last_restock": day,
                "warehouse": wh,
            }
        )
    return rows


MAKERS = {"customers": _customers, "orders": _orders, "inventory": _inventory}


def clean_table(kind: str, seed: int, n: int) -> tuple[list[str], list[dict]]:
    """Return (header, rows) for a clean table. Every value is a string, as in a CSV."""
    rows = MAKERS[kind](random.Random(f"{kind}:{seed}"), n)
    return list(SCHEMAS[kind]["columns"]), rows
