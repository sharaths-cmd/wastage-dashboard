import datetime
from database import get_conn

LOOKBACK_DAYS = 14
MIN_AVG_BASE = 200          # ignore tiny-value noise
ARTICLE_ABS_MIN = 1000      # today's value must exceed this to matter
UNKNOWN_LOSS_THRESHOLD = 5000  # per store per day


def severity_for_pct(pct):
    if pct >= 200:
        return "Critical"
    if pct >= 100:
        return "High"
    return "Medium"


def generate_alerts():
    conn = get_conn()
    latest_row = conn.execute("SELECT MAX(record_date) as d FROM wastage_records").fetchone()
    if not latest_row or not latest_row["d"]:
        conn.close()
        return []
    today = latest_row["d"]
    start_window = (datetime.datetime.strptime(today, "%Y-%m-%d") -
                     datetime.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    conn.execute("DELETE FROM alerts WHERE record_date=?", (today,))
    alerts = []
    now_iso = datetime.datetime.now().isoformat()

    # 1) Article-level spikes per store (known+unknown+consumable combined)
    today_rows = conn.execute("""
        SELECT store_name, item_name, category, SUM(CASE WHEN loss_type='unknown' THEN -amount ELSE amount END) amt,
               SUM(CASE WHEN loss_type='unknown' THEN -qty ELSE qty END) qty
        FROM wastage_records WHERE record_date=?
        GROUP BY store_name, item_name""", (today,)).fetchall()

    hist_rows = conn.execute("""
        SELECT store_name, item_name, record_date, SUM(CASE WHEN loss_type='unknown' THEN -amount ELSE amount END) amt
        FROM wastage_records WHERE record_date>=? AND record_date<?
        GROUP BY store_name, item_name, record_date""", (start_window, today)).fetchall()

    hist_map = {}
    hist_peak = {}
    for r in hist_rows:
        key = (r["store_name"], r["item_name"])
        hist_map.setdefault(key, []).append(r["amt"])
        if key not in hist_peak or r["amt"] > hist_peak[key][0]:
            hist_peak[key] = (r["amt"], r["record_date"])

    for r in today_rows:
        key = (r["store_name"], r["item_name"])
        hist_vals = hist_map.get(key, [])
        if not hist_vals:
            continue
        avg = sum(hist_vals) / len(hist_vals)
        if avg < MIN_AVG_BASE or r["amt"] < ARTICLE_ABS_MIN:
            continue
        if r["amt"] > avg * 1.5:
            pct = round(((r["amt"] - avg) / avg) * 100, 1)
            sev = severity_for_pct(pct)
            peak_amt, peak_date = hist_peak.get(key, (None, None))
            peak_note = f", prior peak ₹{peak_amt:.0f} on {peak_date}" if peak_date else ""
            msg = f"{r['item_name']} at {r['store_name']}: on {today} ₹{r['amt']:.0f} ({r['qty']:.1f} qty) vs avg ₹{avg:.0f} (+{pct}%){peak_note}"
            alerts.append((now_iso, today, sev, "article", r["store_name"], r["item_name"],
                            r["category"], r["amt"], avg, pct, msg))

    # 2) Store-level total wastage spikes
    today_store = conn.execute("""
        SELECT store_name, SUM(CASE WHEN loss_type='unknown' THEN -amount ELSE amount END) amt FROM wastage_records
        WHERE record_date=? GROUP BY store_name""", (today,)).fetchall()
    hist_store_rows = conn.execute("""
        SELECT store_name, record_date, SUM(CASE WHEN loss_type='unknown' THEN -amount ELSE amount END) amt FROM wastage_records
        WHERE record_date>=? AND record_date<? GROUP BY store_name, record_date""",
        (start_window, today)).fetchall()
    hist_store_map = {}
    hist_store_peak = {}
    for r in hist_store_rows:
        hist_store_map.setdefault(r["store_name"], []).append(r["amt"])
        if r["store_name"] not in hist_store_peak or r["amt"] > hist_store_peak[r["store_name"]][0]:
            hist_store_peak[r["store_name"]] = (r["amt"], r["record_date"])

    for r in today_store:
        vals = hist_store_map.get(r["store_name"], [])
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        if avg < MIN_AVG_BASE or r["amt"] < ARTICLE_ABS_MIN:
            continue
        if r["amt"] > avg * 1.5:
            pct = round(((r["amt"] - avg) / avg) * 100, 1)
            sev = severity_for_pct(pct)
            peak_amt, peak_date = hist_store_peak.get(r["store_name"], (None, None))
            peak_note = f", prior peak ₹{peak_amt:.0f} on {peak_date}" if peak_date else ""
            msg = f"Store {r['store_name']} total wastage on {today} ₹{r['amt']:.0f} vs avg ₹{avg:.0f} (+{pct}%){peak_note}"
            alerts.append((now_iso, today, sev, "store", r["store_name"], None, None,
                            r["amt"], avg, pct, msg))

    # 3) Unknown loss threshold breach per store
    today_unknown = conn.execute("""
        SELECT store_name, SUM(CASE WHEN loss_type='unknown' THEN -amount ELSE amount END) amt FROM wastage_records
        WHERE record_date=? AND loss_type='unknown' GROUP BY store_name""", (today,)).fetchall()
    for r in today_unknown:
        if r["amt"] and r["amt"] > UNKNOWN_LOSS_THRESHOLD:
            pct = round((r["amt"] / UNKNOWN_LOSS_THRESHOLD) * 100 - 100, 1)
            sev = severity_for_pct(pct if pct > 0 else 0)
            msg = f"Unknown Loss at {r['store_name']} = ₹{r['amt']:.0f}, above threshold ₹{UNKNOWN_LOSS_THRESHOLD}"
            alerts.append((now_iso, today, sev, "unknown_loss", r["store_name"], None, None,
                            r["amt"], UNKNOWN_LOSS_THRESHOLD, pct, msg))

    # 4) Category spike vs previous week average
    week_ago_start = (datetime.datetime.strptime(today, "%Y-%m-%d") -
                       datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    today_cat = conn.execute("""
        SELECT category, SUM(CASE WHEN loss_type='unknown' THEN -amount ELSE amount END) amt FROM wastage_records
        WHERE record_date=? GROUP BY category""", (today,)).fetchall()
    hist_cat_rows = conn.execute("""
        SELECT category, record_date, SUM(CASE WHEN loss_type='unknown' THEN -amount ELSE amount END) amt FROM wastage_records
        WHERE record_date>=? AND record_date<? GROUP BY category, record_date""",
        (start_window, today)).fetchall()
    hist_cat_map = {}
    hist_cat_peak = {}
    for r in hist_cat_rows:
        hist_cat_map.setdefault(r["category"], []).append(r["amt"])
        if r["category"] not in hist_cat_peak or r["amt"] > hist_cat_peak[r["category"]][0]:
            hist_cat_peak[r["category"]] = (r["amt"], r["record_date"])

    for r in today_cat:
        vals = hist_cat_map.get(r["category"], [])
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        if avg < MIN_AVG_BASE or r["amt"] < ARTICLE_ABS_MIN:
            continue
        if r["amt"] > avg * 1.5:
            pct = round(((r["amt"] - avg) / avg) * 100, 1)
            sev = severity_for_pct(pct)
            peak_amt, peak_date = hist_cat_peak.get(r["category"], (None, None))
            peak_note = f", prior peak ₹{peak_amt:.0f} on {peak_date}" if peak_date else ""
            msg = f"Category {r['category']} wastage on {today} ₹{r['amt']:.0f} vs avg ₹{avg:.0f} (+{pct}%){peak_note}"
            alerts.append((now_iso, today, sev, "category", None, None, r["category"],
                            r["amt"], avg, pct, msg))

    for a in alerts:
        conn.execute("""INSERT INTO alerts
            (created_at, record_date, severity, scope, store_name, item_name, category,
             today_value, avg_value, pct_increase, message)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""", a)
    conn.commit()
    conn.close()
    return alerts
