import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "Database", "wastage.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS wastage_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_date TEXT NOT NULL,
        day TEXT,
        week_no TEXT,
        month TEXT,
        store_name TEXT,
        outlet_name TEXT,
        cluster TEXT,
        cluster_name TEXT,
        store_type TEXT,
        platform TEXT,
        category TEXT,
        item_name TEXT,
        qty REAL,
        amount REAL,
        loss_type TEXT NOT NULL,   -- known / unknown / consumable
        source_file TEXT,
        row_hash TEXT UNIQUE
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_date TEXT NOT NULL,
        day TEXT,
        week_no TEXT,
        month TEXT,
        store_name TEXT,
        outlet_name TEXT,
        cluster TEXT,
        cluster_name TEXT,
        store_type TEXT,
        platform TEXT,
        category TEXT,
        item_name TEXT,
        qty REAL,
        amount REAL,
        source_file TEXT,
        row_hash TEXT UNIQUE
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS processed_files (
        filename TEXT PRIMARY KEY,
        file_hash TEXT,
        processed_at TEXT,
        row_count INTEGER,
        status TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        record_date TEXT,
        severity TEXT,
        scope TEXT,        -- article / store / category / unknown_loss
        store_name TEXT,
        item_name TEXT,
        category TEXT,
        today_value REAL,
        avg_value REAL,
        pct_increase REAL,
        message TEXT,
        seen INTEGER DEFAULT 0
    )""")

    c.execute("CREATE INDEX IF NOT EXISTS idx_w_date ON wastage_records(record_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_w_store ON wastage_records(store_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_s_date ON sales_records(record_date)")

    conn.commit()
    conn.close()
