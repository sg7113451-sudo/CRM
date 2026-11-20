"""Database layer for the simple CRM.

Uses SQLite, which is built into Python, so no extra install is needed.
All the app screens (app.py) talk to the database only through this file.
"""
import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import pandas as pd

# The database file is created next to this script.
# You can change the location with the CRM_DB_PATH environment variable.
DB_PATH = os.environ.get(
    "CRM_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "crm.db"),
)

STATUSES = ["New", "Contacted", "Interested", "Follow-up", "Won", "Lost"]
CLOSED_STATUSES = ("Won", "Lost")
SOURCES = ["Walk-in", "Referral", "Call", "WhatsApp", "Instagram", "Website", "Other"]

# Only these columns can be changed through update_lead().
EDITABLE_FIELDS = {
    "name", "phone", "email", "company", "source", "status", "value", "next_followup",
}


@contextmanager
def get_conn():
    """Open a database connection, save on success, undo on error, always close."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create the tables if they do not exist yet."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                phone         TEXT DEFAULT '',
                email         TEXT DEFAULT '',
                company       TEXT DEFAULT '',
                source        TEXT DEFAULT 'Other',
                status        TEXT NOT NULL DEFAULT 'New',
                value         REAL NOT NULL DEFAULT 0,
                next_followup TEXT,
                created_at    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id    INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                note       TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_leads_status   ON leads(status);
            CREATE INDEX IF NOT EXISTS idx_leads_followup ON leads(next_followup);
            """
        )


# ---------------------------------------------------------------- helpers
def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _to_iso(d):
    """Turn a date / datetime / 'YYYY-MM-DD' string / None into 'YYYY-MM-DD' or None."""
    if d is None or d == "":
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if isinstance(d, str):
        return datetime.strptime(d.strip(), "%Y-%m-%d").date().isoformat()
    raise ValueError("Date must be a date or a 'YYYY-MM-DD' text.")


def _check_status(status):
    if status not in STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(STATUSES)}")


def _check_value(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError("Deal value must be a number.")
    if value < 0:
        raise ValueError("Deal value cannot be negative.")
    return value


# ------------------------------------------------------------------ leads
def add_lead(name, phone="", email="", company="", source="Other",
             status="New", value=0.0, next_followup=None):
    """Add a new lead and return its id."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Name is required.")
    _check_status(status)
    value = _check_value(value)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO leads
               (name, phone, email, company, source, status, value, next_followup, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, (phone or "").strip(), (email or "").strip(), (company or "").strip(),
             source or "Other", status, value, _to_iso(next_followup), _now()),
        )
        return cur.lastrowid


def update_lead(lead_id, **fields):
    """Change one or more fields of a lead, e.g. update_lead(3, status='Won')."""
    unknown = set(fields) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Cannot update: {', '.join(sorted(unknown))}")
    if not fields:
        return

    clean = {}
    for key, val in fields.items():
        if key == "name":
            val = (val or "").strip()
            if not val:
                raise ValueError("Name is required.")
        elif key == "status":
            _check_status(val)
        elif key == "value":
            val = _check_value(val)
        elif key == "next_followup":
            val = _to_iso(val)
        else:
            val = (val or "").strip()
        clean[key] = val

    # Column names come from our own whitelist above, so this is safe.
    set_clause = ", ".join(f"{k} = ?" for k in clean)
    with get_conn() as conn:
        conn.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", [*clean.values(), lead_id])


def delete_lead(lead_id):
    """Delete a lead. Its notes are deleted too."""
    with get_conn() as conn:
        conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))


def get_lead(lead_id):
    """Return one lead as a dict, or None if it does not exist."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(row) if row else None


def count_leads():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]


def get_leads(status=None, search=None):
    """Return leads as a pandas DataFrame (newest first), with optional filters."""
    sql = "SELECT * FROM leads"
    where, params = [], []
    if status and status != "All":
        where.append("status = ?")
        params.append(status)
    if search and search.strip():
        like = f"%{search.strip()}%"
        where.append("(name LIKE ? OR phone LIKE ? OR email LIKE ? OR company LIKE ?)")
        params += [like] * 4
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def followups_due(today=None):
    """Open leads whose follow-up date is today or earlier (oldest first)."""
    today_iso = _to_iso(today or date.today())
    sql = """SELECT * FROM leads
             WHERE next_followup IS NOT NULL
               AND next_followup <= ?
               AND status NOT IN ('Won', 'Lost')
             ORDER BY next_followup, id"""
    with get_conn() as conn:
        df = pd.read_sql_query(sql, conn, params=[today_iso])
    if df.empty:
        df["days_overdue"] = []
    else:
        df["days_overdue"] = (pd.to_datetime(today_iso) - pd.to_datetime(df["next_followup"])).dt.days
    return df


# ------------------------------------------------------------------ notes
def add_note(lead_id, note):
    note = (note or "").strip()
    if not note:
        raise ValueError("Note is empty.")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO notes (lead_id, note, created_at) VALUES (?, ?, ?)",
            (lead_id, note, _now()),
        )


def get_notes(lead_id):
    """Notes of one lead as a DataFrame, newest first."""
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT id, note, created_at FROM notes WHERE lead_id = ? ORDER BY id DESC",
            conn, params=[lead_id],
        )


# ------------------------------------------------------------- dashboard
def get_stats():
    """Numbers and tables used by the dashboard page."""
    df = get_leads()
    by_status = df["status"].value_counts().reindex(STATUSES, fill_value=0)
    won = int(by_status["Won"])
    lost = int(by_status["Lost"])
    open_df = df[~df["status"].isin(CLOSED_STATUSES)]
    return {
        "total": int(len(df)),
        "open": int(len(open_df)),
        "won": won,
        "lost": lost,
        "win_rate": (won / (won + lost) * 100) if (won + lost) else 0.0,
        "pipeline_value": float(open_df["value"].sum()),
        "won_value": float(df.loc[df["status"] == "Won", "value"].sum()),
        "by_status": by_status,
        "value_by_status": df.groupby("status")["value"].sum().reindex(STATUSES, fill_value=0),
        "by_source": df["source"].value_counts(),
    }


# -------------------------------------------------------------- demo data
def seed_demo(n=24):
    """Fill an EMPTY database with made-up leads so you can see the dashboard."""
    if count_leads() > 0:
        return 0
    rng = random.Random(42)
    first = ["Amit", "Priya", "Rohan", "Sneha", "Vikram", "Neha", "Rahul", "Pooja",
             "Suresh", "Anjali", "Kiran", "Meera"]
    last = ["Patil", "Sharma", "Deshmukh", "Joshi", "Kulkarni", "Shinde", "More", "Jadhav"]
    firms = ["Demo Traders", "Sample Motors", "Test Enterprises", "Example Foods",
             "Dummy Logistics", "Trial Textiles"]
    today = date.today()
    for i in range(n):
        status = rng.choices(STATUSES, weights=[4, 5, 4, 4, 3, 2])[0]
        followup = None
        if status not in CLOSED_STATUSES:
            followup = today + timedelta(days=rng.randint(-4, 7))
        lead_id = add_lead(
            name=f"{rng.choice(first)} {rng.choice(last)}",
            phone=f"90000{i:05d}",
            company=rng.choice(firms),
            source=rng.choice(SOURCES),
            status=status,
            value=rng.choice([5000, 10000, 25000, 50000, 100000, 250000]),
            next_followup=followup,
        )
        add_note(lead_id, "Demo lead created for testing.")
    return n
