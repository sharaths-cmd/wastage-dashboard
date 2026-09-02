import os
import threading
import time
import shutil
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List

from database import init_db, get_conn
from importer import scan_upload_folder, UPLOAD_DIR
from alerts import generate_alerts

app = FastAPI(title="Wastage Management System")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(__file__)
_static_dir = os.path.join(BASE_DIR, "static")
if not os.path.isdir(_static_dir):
    _static_dir = BASE_DIR  # fallback: files sitting at repo root instead of in static/
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ---------- helpers ----------

def build_where(date_from, date_to, cluster, store, category, item, loss_type, day, week, month, cluster_name=None):
    where = []
    params = []
    if date_from:
        where.append("record_date >= ?"); params.append(date_from)
    if date_to:
        where.append("record_date <= ?"); params.append(date_to)
    if cluster:
        where.append("cluster = ?"); params.append(cluster)
    if cluster_name:
        where.append("cluster_name = ?"); params.append(cluster_name)
    if store:
        where.append("store_name = ?"); params.append(store)
    if category:
        where.append("category = ?"); params.append(category)
    if item:
        where.append("item_name = ?"); params.append(item)
    if loss_type:
        where.append("loss_type = ?"); params.append(loss_type)
    if day:
        where.append("day = ?"); params.append(day)
    if week:
        where.append("week_no = ?"); params.append(week)
    if month:
        where.append("month = ?"); params.append(month)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return clause, params


COMMON_PARAMS = dict(
    date_from=Query(None), date_to=Query(None), cluster=Query(None), store=Query(None),
    category=Query(None), item=Query(None), loss_type=Query(None),
    day=Query(None), week=Query(None), month=Query(None),
)


# ---------- startup ----------

@app.on_event("startup")
def startup():
    init_db()
    scan_upload_folder()
    generate_alerts()
    t = threading.Thread(target=background_watcher, daemon=True)
    t.start()


def background_watcher():
    while True:
        try:
            results = scan_upload_folder()
            if any(r["status"] == "processed" for r in results):
                generate_alerts()
        except Exception as e:
            print("watcher error:", e)
        time.sleep(15)


# ---------- pages ----------

@app.get("/")
def index():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))


@app.get("/manifest.json")
def manifest():
    return FileResponse(os.path.join(BASE_DIR, "static", "manifest.json"))


@app.get("/sw.js")
def sw():
    return FileResponse(os.path.join(BASE_DIR, "static", "sw.js"), media_type="application/javascript")


# ---------- upload ----------

@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(UPLOAD_DIR, file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    from importer import process_file
    result = process_file(dest)
    generate_alerts()
    return result


@app.post("/api/rescan")
def rescan():
    results = scan_upload_folder()
    generate_alerts()
    return {"results": results}


# ---------- filter options ----------

@app.get("/api/filters")
def filters():
    conn = get_conn()
    def col(name, table="wastage_records"):
        rows = conn.execute(f"SELECT DISTINCT {name} FROM {table} WHERE {name} IS NOT NULL ORDER BY {name}").fetchall()
        return [r[0] for r in rows if r[0]]
    data = {
        "clusters": col("cluster"),
        "cluster_names": col("cluster_name"),
        "stores": col("store_name"),
        "categories": col("category"),
        "items": col("item_name"),
        "days": col("day"),
        "weeks": col("week_no"),
        "months": col("month"),
        "date_min": conn.execute("SELECT MIN(record_date) m FROM wastage_records").fetchone()["m"],
        "date_max": conn.execute("SELECT MAX(record_date) m FROM wastage_records").fetchone()["m"],
    }
    conn.close()
    return data


# ---------- KPIs ----------

@app.get("/api/kpis")
def kpis(date_from=None, date_to=None, cluster=None, cluster_name=None, store=None, category=None,
          item=None, loss_type=None, day=None, week=None, month=None):
    conn = get_conn()
    clause, params = build_where(date_from, date_to, cluster, store, category, item, None, day, week, month, cluster_name)
    rows = conn.execute(f"""SELECT loss_type, SUM(amount) amt, SUM(qty) qty FROM wastage_records {clause}
                             GROUP BY loss_type""", params).fetchall()
    vals = {r["loss_type"]: (r["amt"] or 0) for r in rows}
    qtys = {r["loss_type"]: (r["qty"] or 0) for r in rows}
    known = vals.get("known", 0)
    unknown_raw = vals.get("unknown", 0)
    # Preserve source signs exactly for the standalone cards. Never ABS()/flip negative values there.
    unknown = unknown_raw
    consumable = 0
    # Headline Total Loss/Total Wastage always reflect the true magnitude of loss
    # (adds shrinkage regardless of its sign) so the top-line numbers read sensibly.
    total_loss = known + abs(unknown)

    known_qty = qtys.get("known", 0)
    unknown_qty = qtys.get("unknown", 0)
    # Consumables also retain the exact source sign.
    cclause, cparams = build_where(date_from, date_to, cluster, store, category, item, None, day, week, month, cluster_name)
    if cclause:
        cclause += " AND loss_type='consumable'"
    else:
        cclause = "WHERE loss_type='consumable'"
    crows = conn.execute(f"""SELECT source_file, SUM(amount) a, SUM(qty) q FROM wastage_records {cclause}
                              GROUP BY source_file""", cparams).fetchall()
    consumable = 0
    consumable_qty = 0
    for cr in crows:
        consumable += cr["a"] or 0
        consumable_qty += cr["q"] or 0
    total_with_consumables = total_loss + abs(consumable)
    total_qty = known_qty + abs(unknown_qty) + abs(consumable_qty)

    sclause, sparams = build_where(date_from, date_to, cluster, store, category, item, None, day, week, month, cluster_name)
    sales_total = conn.execute(f"SELECT SUM(amount) s FROM sales_records {sclause}", sparams).fetchone()["s"] or 0
    conn.close()
    loss_pct = round((total_loss / sales_total) * 100, 2) if sales_total else 0
    def pct(v): return round((v / sales_total) * 100, 2) if sales_total else 0
    return {
        "known_loss": round(known, 2),
        "unknown_loss": round(unknown, 2),
        "consumables": round(consumable, 2),
        "total_loss": round(total_loss, 2),
        "total_with_consumables": round(total_with_consumables, 2),
        "sales_total": round(sales_total, 2),
        "total_loss_pct": loss_pct,
        "known_loss_qty": round(known_qty, 2),
        "unknown_loss_qty": round(unknown_qty, 2),
        "consumables_qty": round(consumable_qty, 2),
        "total_qty": round(total_qty, 2),
        "known_loss_pct": pct(known),
        "unknown_loss_pct": pct(unknown),
        "consumables_pct": pct(consumable),
        "total_with_consumables_pct": pct(total_with_consumables),
    }


# ---------- trend (day/week/month) ----------

@app.get("/api/trend")
def trend(granularity: str = "day", metric: str = "value", date_from=None, date_to=None, cluster=None, cluster_name=None, store=None,
           category=None, item=None, loss_type=None, day=None, week=None, month=None):
    conn = get_conn()
    clause, params = build_where(date_from, date_to, cluster, store, category, item, loss_type, day, week, month, cluster_name)
    group_col = {"day": "record_date", "week": "week_no", "month": "month"}.get(granularity, "record_date")
    col = "qty" if metric == "qty" else "amount"
    rows = conn.execute(f"""
        SELECT {group_col} as label,
               SUM(CASE WHEN loss_type='known' THEN {col} ELSE 0 END) known,
               SUM(CASE WHEN loss_type='unknown' THEN {col} ELSE 0 END) unknown,
               SUM(CASE WHEN loss_type='consumable' THEN {col} ELSE 0 END) consumable
        FROM wastage_records {clause}
        GROUP BY {group_col}
        ORDER BY MIN(record_date)
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- breakdowns ----------

@app.get("/api/breakdown")
def breakdown(by: str = "cluster", limit: int = 15, metric: str = "value", date_from=None, date_to=None, cluster=None,
               cluster_name=None, store=None, category=None, item=None, loss_type=None, day=None, week=None, month=None):
    col_map = {"cluster": "cluster", "store": "store_name", "category": "category", "item": "item_name"}
    col = col_map.get(by, "cluster")
    valcol = "qty" if metric == "qty" else "amount"
    conn = get_conn()
    clause, params = build_where(date_from, date_to, cluster, store, category, item, loss_type, day, week, month, cluster_name)
    rows = conn.execute(f"""
        SELECT {col} as label, SUM({valcol}) as amount
        FROM wastage_records {clause}
        GROUP BY {col} ORDER BY ABS(amount) DESC LIMIT ?
    """, params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/known_vs_unknown")
def known_vs_unknown(date_from=None, date_to=None, cluster=None, cluster_name=None, store=None, category=None,
                       item=None, day=None, week=None, month=None):
    conn = get_conn()
    clause, params = build_where(date_from, date_to, cluster, store, category, item, None, day, week, month, cluster_name)
    rows = conn.execute(f"""
        SELECT loss_type, SUM(amount) amt FROM wastage_records {clause} GROUP BY loss_type
    """, params).fetchall()
    conn.close()
    return {r["loss_type"]: round(r["amt"] or 0, 2) for r in rows}


@app.get("/api/heatmap")
def heatmap(date_from=None, date_to=None, cluster=None, cluster_name=None, store=None, category=None,
             item=None, loss_type=None):
    """store x day-of-week matrix of total wastage"""
    conn = get_conn()
    clause, params = build_where(date_from, date_to, cluster, store, category, item, loss_type, None, None, None)
    rows = conn.execute(f"""
        SELECT store_name, day, SUM(ABS(amount)) amt FROM wastage_records {clause}
        GROUP BY store_name, day
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- alerts ----------

@app.get("/api/alerts")
def get_alerts(severity: Optional[str] = None, limit: int = 100):
    conn = get_conn()
    where = ""
    params = []
    if severity:
        where = "WHERE severity=?"
        params.append(severity)
    rows = conn.execute(f"""SELECT * FROM alerts {where} ORDER BY created_at DESC LIMIT ?""",
                         params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/alerts/{alert_id}/seen")
def mark_seen(alert_id: int):
    conn = get_conn()
    conn.execute("UPDATE alerts SET seen=1 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/alerts/regenerate")
def regenerate_alerts():
    a = generate_alerts()
    return {"count": len(a)}


@app.get("/api/wow")
def wow(dim: str = "store", limit: int = 100, period: str = "week", cluster=None, cluster_name=None, store=None, category=None,
         item=None, loss_type=None, loss_view: str = "include", include_consumables: Optional[bool] = None,
         metric: str = "value"):
    """Signed loss trend, week-wise or day-wise. INC = known+unknown+consumable; EXC = known+unknown.
    Source signs are preserved exactly; no ABS/sign flipping is used."""
    col_map = {"cluster": "cluster", "store": "store_name", "category": "category", "item": "item_name"}
    col = col_map.get(dim, "store_name")
    valcol = "qty" if metric == "qty" else "amount"
    group_col = "record_date" if period == "day" else "week_no"
    conn = get_conn()

    # The INC/EXC control is authoritative for this WoW section.
    # It must not accidentally inherit the global loss-type selector.
    clause, params = build_where(None, None, cluster, store, category, item, None, None, None, None, cluster_name)
    if clause:
        clause += f" AND {group_col} IS NOT NULL"
    else:
        clause = f"WHERE {group_col} IS NOT NULL"
    if loss_view.lower() in ("exclude", "exc", "excluding"):
        clause += " AND loss_type != 'consumable'"

    rows = conn.execute(f"""
        SELECT {col} as label, {group_col} as period_key, SUM({valcol}) amt
        FROM wastage_records {clause}
        GROUP BY {col}, {group_col}
    """, params).fetchall()

    sales_valcol = "qty" if metric == "qty" else "amount"
    sales_rows = conn.execute(f"""
        SELECT {col} as label, {group_col} as period_key, SUM({sales_valcol}) amt
        FROM sales_records WHERE {group_col} IS NOT NULL
        GROUP BY {col}, {group_col}
    """).fetchall()
    conn.close()
    sales_map = {}
    for r in sales_rows:
        sales_map[(r["label"] or "N/A", r["period_key"])] = r["amt"] or 0

    pivot = {}
    periods_seen = set()
    for r in rows:
        label = r["label"] or "N/A"
        pivot.setdefault(label, {})[r["period_key"]] = r["amt"] or 0
        periods_seen.add(r["period_key"])

    if period == "day":
        periods_sorted = sorted(periods_seen)[-14:]
    else:
        def wk_num(w):
            try:
                return int(str(w).replace("Week", "").strip())
            except Exception:
                return 0
        periods_sorted = sorted(periods_seen, key=wk_num)[-8:]
    weeks_sorted = periods_sorted

    totals = {lbl: sum(abs(float(x or 0)) for x in v.values()) for lbl, v in pivot.items()}
    top_labels = sorted(totals, key=totals.get, reverse=True)[:limit]

    result = []
    for lbl in top_labels:
        wk_vals = pivot.get(lbl, {})
        cells = []
        for w in weeks_sorted:
            val = float(wk_vals.get(w, 0) or 0)
            wk_sales = sales_map.get((lbl, w), 0)
            pct = round((val / wk_sales) * 100, 2) if wk_sales else None
            cells.append({"week": w, "amount": round(val, 2), "pct_of_sales": pct})
        result.append({"label": lbl, "cells": cells})
    return {"weeks": weeks_sorted, "rows": result}
# ---------- run server ----------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False
    )

