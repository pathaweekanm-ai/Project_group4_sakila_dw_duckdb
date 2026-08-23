#!/usr/bin/env python3
"""Generate models/staging/stg_*.sql for every Sakila seed table.
Run once from the dbt project root: python3 scripts/generate_staging_models.py
Re-run any time the seed column list changes."""

import os

# column -> dbt/duckdb cast type
TYPES = {
    "actor_id": "integer", "address_id": "integer", "category_id": "integer",
    "city_id": "integer", "country_id": "integer", "customer_id": "integer",
    "film_id": "integer", "language_id": "integer", "original_language_id": "integer",
    "inventory_id": "integer", "payment_id": "integer", "rental_id": "integer",
    "staff_id": "integer", "store_id": "integer", "manager_staff_id": "integer",
    "rental_duration": "integer", "length": "integer", "release_year": "integer",
    "active": "boolean",
    "amount": "decimal(5,2)", "rental_rate": "decimal(4,2)", "replacement_cost": "decimal(5,2)",
    "last_update": "timestamp", "create_date": "timestamp", "rental_date": "timestamp",
    "return_date": "timestamp", "payment_date": "timestamp",
}

# table -> ordered [(column, is_nullable_note)]
TABLES = {
    "actor": ["actor_id", "first_name", "last_name", "last_update"],
    "address": ["address_id", "address", "address2", "district", "city_id",
                "postal_code", "phone", "last_update"],
    "category": ["category_id", "name", "last_update"],
    "city": ["city_id", "city", "country_id", "last_update"],
    "country": ["country_id", "country", "last_update"],
    "customer": ["customer_id", "store_id", "first_name", "last_name", "email",
                 "address_id", "active", "create_date", "last_update"],
    "film": ["film_id", "title", "description", "release_year", "language_id",
             "original_language_id", "rental_duration", "rental_rate", "length",
             "replacement_cost", "rating", "special_features", "last_update"],
    "film_actor": ["actor_id", "film_id", "last_update"],
    "film_category": ["film_id", "category_id", "last_update"],
    "inventory": ["inventory_id", "film_id", "store_id", "last_update"],
    "language": ["language_id", "name", "last_update"],
    "payment": ["payment_id", "customer_id", "staff_id", "rental_id", "amount",
                "payment_date", "last_update"],
    "rental": ["rental_id", "rental_date", "inventory_id", "customer_id",
               "return_date", "staff_id", "last_update"],
    "staff": ["staff_id", "first_name", "last_name", "address_id", "email",
              "store_id", "active", "username", "last_update"],
    "store": ["store_id", "manager_staff_id", "address_id", "last_update"],
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "staging")


def render(table, cols):
    lines = ["select"]
    for i, c in enumerate(cols):
        cast = TYPES.get(c)
        expr = f"{c}::{cast}" if cast else c
        alias = f" as {c}" if cast else ""
        comma = "," if i < len(cols) - 1 else ","
        lines.append(f"    {expr}{alias}{comma}")
    lines.append("    current_timestamp as _loaded_at")
    lines.append(f"from {{{{ ref('{table}') }}}}")
    body = "\n".join(lines)
    return f"-- Staging model for the raw `{table}` seed (source: raw_data_DVD / Sakila)\n{body}\n"


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for table, cols in TABLES.items():
        path = os.path.join(OUT_DIR, f"stg_{table}.sql")
        with open(path, "w") as f:
            f.write(render(table, cols))
        print("wrote", path)