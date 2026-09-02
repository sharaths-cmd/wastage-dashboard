import os
import hashlib
import datetime
import pandas as pd
from database import get_conn

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "Uploads")
MAIL_MAP_PATH = os.path.join(os.path.dirname(__file__), "mail_ids.xlsx")

_cluster_name_map = None


def get_cluster_name_map():
    global _cluster_name_map
    if _cluster_name_map is None:
        try:
            df = pd.read_excel(MAIL_MAP_PATH, sheet_name="Store Mail Id")
            _cluster_name_map = dict(zip(df["Store Name"], df["Cluster Name"]))
        except Exception:
            _cluster_name_map = {}
    return _cluster_name_map


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_amount(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("₹", "").strip()
    if s == "" or s.lower() == "nan":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(val):
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(str(val).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        return None


def detect_file_type(filename):
    fn = filename.lower()
    if "unknown_loss" in fn or "unknown loss" in fn:
        return "unknown"
    if "known_loss" in fn or "known loss" in fn:
        return "known"
    if "sales" in fn:
        return "sales"
    return None


def row_hash(*parts):
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def import_known_loss(df, source_file, conn):
    inserted = 0
    for _, r in df.iterrows():
        d = parse_date(r.get("Date"))
        if not d:
            continue
        cat = str(r.get("Cat", "")).strip()
        # second 'Cat' column (Cat.1) holds sub-category in this file; first Cat is the loss category
        raw_cat = str(r.get("Cat", "")).strip()
        loss_type = "consumable" if raw_cat.upper() == "CONSUMABLES" else "known"
        qty = clean_amount(r.get("Qty"))
        amt = clean_amount(r.get("Cost Amt"))
        item = str(r.get("Item Name", "")).strip()
        store = str(r.get("Store Name", "")).strip()
        cname = get_cluster_name_map().get(store, "")
        h = row_hash("known", d, store, item, qty, amt, r.get("Outlet Name"))
        try:
            conn.execute("""INSERT OR IGNORE INTO wastage_records
                (record_date, day, week_no, month, store_name, outlet_name, cluster, cluster_name,
                 store_type, platform, category, item_name, qty, amount, loss_type, source_file, row_hash)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (d, r.get("Day"), r.get("Week no"), r.get("Month"), store,
                 r.get("Outlet Name"), r.get("Cluster"), cname, r.get("Store Type"),
                 r.get("Platform"), raw_cat, item, qty, amt, loss_type, source_file, h))
            inserted += 1
        except Exception:
            pass
    return inserted


def import_unknown_loss(df, source_file, conn):
    inserted = 0
    for _, r in df.iterrows():
        d = parse_date(r.get("Stk Upd Date"))
        if not d:
            continue
        raw_qty = clean_amount(r.get("Sum of Discre Stk"))
        raw_amt = clean_amount(r.get("Sum of Discre Amt(NetCost)"))
        # Kept exactly as in the source file: negative = shrinkage (real loss),
        # positive = excess stock found. No sign conversion applied.
        qty = raw_qty
        amt = raw_amt
        item = str(r.get("Item Name", "")).strip()
        store = str(r.get("Store Name", "")).strip()
        cat = str(r.get("CATEGORY", "")).strip()
        # Store/item breakdown tabs ("Unknown Loss <> Consumables") exclude CONSUMABLES
        # and keep the raw signed value (negative = shrinkage) - verified against sheet.
        loss_type = "consumable" if cat.upper() == "CONSUMABLES" else "unknown"
        cname = get_cluster_name_map().get(store, "")
        h = row_hash("unknown", d, store, item, raw_qty, raw_amt, r.get("OUTLET NAME"))
        conn.execute("""INSERT OR IGNORE INTO wastage_records
            (record_date, day, week_no, month, store_name, outlet_name, cluster, cluster_name,
             store_type, platform, category, item_name, qty, amount, loss_type, source_file, row_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d, r.get("Day"), r.get("Week no"), r.get("Month"), store,
             r.get("OUTLET NAME"), r.get("Cluster"), cname, r.get("Store Type"),
             r.get("Platform"), cat, item, qty, amt, loss_type, source_file, h))
        inserted += 1
    return inserted


def import_sales(df, source_file, conn):
    inserted = 0
    for _, r in df.iterrows():
        d = parse_date(r.get("Bill Date"))
        if not d:
            continue
        qty = clean_amount(r.get("Sum of Qty"))
        amt = clean_amount(r.get("Sum of Actuals"))
        item = str(r.get("Item Name", "")).strip()
        store = str(r.get("Store Name", "")).strip()
        cat = str(r.get("CATEGORY", "")).strip()
        h = row_hash("sales", d, store, item, qty, amt, r.get("Outlet Name"))
        conn.execute("""INSERT OR IGNORE INTO sales_records
            (record_date, day, week_no, month, store_name, outlet_name, cluster, cluster_name,
             store_type, platform, category, item_name, qty, amount, source_file, row_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d, r.get("Day"), r.get("Week no"), r.get("Month"), store,
             r.get("Outlet Name"), r.get("Cluster"), get_cluster_name_map().get(store, ""), r.get("Store Type"),
             r.get("Platform"), cat, item, qty, amt, source_file, h))
        inserted += 1
    return inserted


def process_file(path):
    filename = os.path.basename(path)
    conn = get_conn()
    already = conn.execute("SELECT * FROM processed_files WHERE filename=?", (filename,)).fetchone()
    fhash = file_md5(path)
    if already and already["file_hash"] == fhash:
        conn.close()
        return {"file": filename, "status": "skipped_duplicate"}

    ftype = detect_file_type(filename)
    if not ftype:
        conn.execute("""INSERT OR REPLACE INTO processed_files (filename, file_hash, processed_at, row_count, status)
                         VALUES (?,?,?,?,?)""", (filename, fhash, datetime.datetime.now().isoformat(), 0, "unrecognized_type"))
        conn.commit()
        conn.close()
        return {"file": filename, "status": "unrecognized_type"}

    try:
        if path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path)
    except Exception as e:
        conn.close()
        return {"file": filename, "status": f"error: {e}"}

    if ftype == "known":
        n = import_known_loss(df, filename, conn)
    elif ftype == "unknown":
        n = import_unknown_loss(df, filename, conn)
    else:
        n = import_sales(df, filename, conn)

    conn.execute("""INSERT OR REPLACE INTO processed_files (filename, file_hash, processed_at, row_count, status)
                     VALUES (?,?,?,?,?)""", (filename, fhash, datetime.datetime.now().isoformat(), len(df), "processed"))
    conn.commit()
    conn.close()
    return {"file": filename, "status": "processed", "type": ftype, "rows": len(df)}


def scan_upload_folder():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    results = []
    for fn in os.listdir(UPLOAD_DIR):
        if fn.startswith("~$") or fn.startswith("."):
            continue
        if not fn.lower().endswith((".csv", ".xlsx", ".xls")):
            continue
        path = os.path.join(UPLOAD_DIR, fn)
        results.append(process_file(path))
    return results
