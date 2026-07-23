"""
Database module for Real Estate AI Sales Agent.

Handles SQLite schema creation, upserts, and the search_properties tool
that the AI agent calls during conversations.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realestate.db")


def _get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the database tables if they don't exist."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            developer TEXT,
            location TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            unit_type TEXT NOT NULL,
            bedrooms TEXT NOT NULL,
            area_sqm REAL DEFAULT 0,
            starting_price REAL DEFAULT 0,
            down_payment_pct REAL DEFAULT 0,
            installment_years INTEGER DEFAULT 0,
            delivery_year INTEGER DEFAULT 0,
            payment_plan TEXT,
            raw_summary TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            UNIQUE(project_id, unit_type, bedrooms, installment_years)
        )
    """)

    conn.commit()
    conn.close()
    print(f"✅ Database initialized at: {DB_PATH}")


def _build_raw_summary(project_name: str, developer: str, location: str,
                       unit_type: str, bedrooms: str, area_sqm: float,
                       starting_price: float, payment_plan: str,
                       delivery_year: int) -> str:
    """Build a pre-formatted 5-line summary block for the agent to read."""
    price_str = f"{starting_price:,.0f} EGP" if starting_price > 0 else "Price on request"
    area_str = f"{area_sqm:,.0f} sqm" if area_sqm > 0 else "Area on request"

    return (
        f"🏠 {project_name} — {unit_type} {bedrooms}\n"
        f"📍 {location} | {developer}\n"
        f"💰 Starting: {price_str} | Area: {area_str}\n"
        f"📝 Payment: {payment_plan}\n"
        f"📅 Delivery: {delivery_year}"
    )


def upsert_unit(offer) -> None:
    """
    Insert or replace a unit offer into the database.
    
    Args:
        offer: A UnitOffer Pydantic model instance from parser.py
    """
    conn = _get_connection()
    cursor = conn.cursor()

    # Upsert the project
    cursor.execute(
        "INSERT OR IGNORE INTO projects (name, developer, location) VALUES (?, ?, ?)",
        (offer.project_name, offer.developer_name, offer.location)
    )

    # Get project_id
    cursor.execute("SELECT id FROM projects WHERE name = ?", (offer.project_name,))
    project_id = cursor.fetchone()[0]

    # Build the raw summary
    raw_summary = _build_raw_summary(
        project_name=offer.project_name,
        developer=offer.developer_name,
        location=offer.location,
        unit_type=offer.unit_type,
        bedrooms=offer.bedrooms,
        area_sqm=offer.unit_area_sqm,
        starting_price=offer.starting_price,
        payment_plan=offer.payment_plan_summary,
        delivery_year=offer.delivery_year
    )

    # Upsert the unit
    cursor.execute("""
        INSERT OR REPLACE INTO units 
        (project_id, unit_type, bedrooms, area_sqm, starting_price, 
         down_payment_pct, installment_years, delivery_year, payment_plan, raw_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        offer.unit_type,
        offer.bedrooms,
        offer.unit_area_sqm,
        offer.starting_price,
        offer.down_payment_pct,
        offer.installment_years,
        offer.delivery_year,
        offer.payment_plan_summary,
        raw_summary
    ))

    conn.commit()
    conn.close()
    print(f"  💾 Saved: {offer.project_name} — {offer.unit_type} {offer.bedrooms} ({offer.installment_years}Y)")


def search_properties(
    location_keyword: str = "",
    unit_type: str = "",
    max_budget: float = 0,
    max_delivery_year: int = 0,
    bedrooms: str = ""
) -> str:
    """
    Search real estate properties based on user criteria.
    This function is used as a tool by the AI sales agent.

    Args:
        location_keyword: Filter by location (e.g., "North Coast", "October").
        unit_type: Filter by unit type: "Villa", "Chalet", or "Apartment".
        max_budget: Maximum total price in EGP. Use 0 to skip this filter.
        max_delivery_year: Latest acceptable delivery year. Use 0 to skip.
        bedrooms: Filter by bedroom configuration (e.g., "1B", "2B", "3B + Nanny").

    Returns:
        Formatted property listings separated by dividers, or a guidance message if no matches found.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    query = """
        SELECT u.raw_summary 
        FROM units u
        JOIN projects p ON u.project_id = p.id
        WHERE 1=1
    """
    params = []

    if location_keyword:
        query += " AND p.location LIKE ?"
        params.append(f"%{location_keyword}%")

    if unit_type:
        query += " AND u.unit_type LIKE ?"
        params.append(f"%{unit_type}%")

    if max_budget > 0:
        query += " AND u.starting_price > 0 AND u.starting_price <= ?"
        params.append(max_budget)

    if max_delivery_year > 0:
        query += " AND u.delivery_year <= ?"
        params.append(max_delivery_year)

    if bedrooms:
        query += " AND u.bedrooms LIKE ?"
        params.append(f"%{bedrooms}%")

    query += " ORDER BY u.starting_price ASC"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    if not results:
        return (
            "No exact matches found for the given criteria. "
            "Call search_properties again with relaxed filters (e.g., remove unit_type, "
            "bedrooms, or widen the budget/location) to discover what alternatives are "
            "actually available in the database, then present those concrete options to the user."
        )

    summaries = [row[0] for row in results]
    return "\n---\n".join(summaries)


def search_properties_json(
    location_keyword: str = "",
    unit_type: str = "",
    max_budget: float = 0,
    max_delivery_year: int = 0,
    bedrooms: str = ""
) -> list[dict]:
    """
    Search properties and return structured dictionaries for the web UI.
    Uses the same filtering logic as search_properties but returns rich data
    for rendering PropertyShowcaseCards.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    query = """
        SELECT p.name, p.developer, p.location,
               u.unit_type, u.bedrooms, u.area_sqm,
               u.starting_price, u.down_payment_pct,
               u.installment_years, u.delivery_year, u.payment_plan
        FROM units u
        JOIN projects p ON u.project_id = p.id
        WHERE 1=1
    """
    params = []

    if location_keyword:
        query += " AND p.location LIKE ?"
        params.append(f"%{location_keyword}%")
    if unit_type:
        query += " AND u.unit_type LIKE ?"
        params.append(f"%{unit_type}%")
    if max_budget > 0:
        query += " AND u.starting_price > 0 AND u.starting_price <= ?"
        params.append(max_budget)
    if max_delivery_year > 0:
        query += " AND u.delivery_year <= ?"
        params.append(max_delivery_year)
    if bedrooms:
        query += " AND u.bedrooms LIKE ?"
        params.append(f"%{bedrooms}%")

    query += " ORDER BY u.starting_price ASC"
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    properties = []
    for row in results:
        properties.append({
            "project_name": row[0],
            "developer": row[1],
            "location": row[2],
            "unit_type": row[3],
            "bedrooms": row[4],
            "area_sqm": row[5],
            "starting_price": row[6],
            "down_payment_pct": row[7],
            "installment_years": row[8],
            "delivery_year": row[9],
            "payment_plan": row[10],
        })
    return properties


# Auto-initialize the database on module import
init_db()
