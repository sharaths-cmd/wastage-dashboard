"""
Sends wastage alert emails for a chosen date or week.

- One email PER STORE, sent only to that store's own email, listing that
  store's own top wastage items (item, value, qty, date). Stores never see
  each other's emails or data (privacy).
- One email PER CLUSTER, sent only to that cluster's email, combining data
  from every store in the cluster - but never CC'ing/exposing any store's
  individual email address.

Usage:
    python email_alerts.py --date 2026-08-30
    python email_alerts.py --week "Week 22"
    python email_alerts.py --date 2026-08-30 --items-per-store 20

Edit the SMTP settings below before first use.
"""
import argparse
import smtplib
import sqlite3
from email.mime.text import MIMEText

# ---- EDIT THESE ----
SMTP_HOST = "smtp.gmail.com"      # or your company's SMTP server
SMTP_PORT = 587
SMTP_USER = "your-email@mychickenandmore.com"
SMTP_PASSWORD = "your-app-password"   # Gmail: use an "App Password", not your login password
FROM_ADDR = SMTP_USER
# ---------------------

DB_PATH = "Database/wastage.db"
MAIL_MAP_PATH = "mail_ids.xlsx"


def load_mail_maps():
    import pandas as pd
    xl = pd.ExcelFile(MAIL_MAP_PATH)
    store_df = pd.read_excel(xl, "Store Mail Id")
    cluster_df = pd.read_excel(xl, "Cluster Mail Id")
    store_to_mail = dict(zip(store_df["Store Name"], store_df["Store Mail Id"]))
    store_to_cluster = dict(zip(store_df["Store Name"], store_df["Cluster"]))
    cluster_to_mail = dict(zip(cluster_df["Cluster"], cluster_df["Cluster Mail Id"]))
    return store_to_mail, store_to_cluster, cluster_to_mail


def get_top_items(conn, where_clause, params, limit):
    rows = conn.execute(f"""
        SELECT item_name, category,
               SUM(CASE WHEN loss_type='unknown' THEN -amount ELSE amount END) amt,
               SUM(CASE WHEN loss_type='unknown' THEN -qty ELSE qty END) qty,
               MAX(record_date) as last_date
        FROM wastage_records {where_clause}
        GROUP BY item_name
        ORDER BY ABS(amt) DESC
        LIMIT ?
    """, params + [limit]).fetchall()
    return rows


def format_body(store_or_cluster_name, rows, period_label):
    lines = [f"Wastage Alert — {store_or_cluster_name} — {period_label}", ""]
    lines.append(f"{'Item':<35}{'Category':<20}{'Value (₹)':>12}{'Qty':>10}{'Date':>14}")
    lines.append("-" * 91)
    for r in rows:
        lines.append(f"{r['item_name'][:34]:<35}{(r['category'] or '')[:19]:<20}"
                      f"{r['amt']:>12.0f}{r['qty']:>10.1f}{r['last_date']:>14}")
    lines.append("")
    lines.append("This is an automated wastage alert from the Wastage Management Dashboard.")
    return "\n".join(lines)


def send_email(to_addr, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_ADDR
    msg["To"] = to_addr
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_ADDR, [to_addr], msg.as_string())
    print(f"[sent] {to_addr} - {subject}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="e.g. 2026-08-30")
    ap.add_argument("--week", help='e.g. "Week 22"')
    ap.add_argument("--items-per-store", type=int, default=20,
                     help="How many top wastage items to include per store (10-30 recommended)")
    args = ap.parse_args()
    if not args.date and not args.week:
        print("Provide --date or --week")
        return

    if args.date:
        where = "WHERE record_date=?"
        params = [args.date]
        period_label = args.date
    else:
        where = "WHERE week_no=?"
        params = [args.week]
        period_label = args.week

    store_to_mail, store_to_cluster, cluster_to_mail = load_mail_maps()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cluster_rows = {}  # cluster -> list of rows across all its stores

    for store, mail in store_to_mail.items():
        s_where = where + " AND store_name=?"
        s_params = params + [store]
        rows = get_top_items(conn, s_where, s_params, args.items_per_store)
        if not rows:
            continue
        body = format_body(store, rows, period_label)
        send_email(mail, f"Wastage Alert - {store} - {period_label}", body)

        cluster = store_to_cluster.get(store)
        if cluster:
            cluster_rows.setdefault(cluster, []).extend([dict(r) for r in rows])

    # Cluster rollup emails - combine, re-rank, send ONLY to cluster email (no store emails included)
    for cluster, rows in cluster_rows.items():
        mail = cluster_to_mail.get(cluster)
        if not mail:
            continue
        rows_sorted = sorted(rows, key=lambda r: abs(r["amt"]), reverse=True)[:args.items_per_store]
        body = format_body(f"{cluster} (all stores combined)", rows_sorted, period_label)
        send_email(mail, f"Wastage Alert - {cluster} - {period_label}", body)

    conn.close()


if __name__ == "__main__":
    main()
