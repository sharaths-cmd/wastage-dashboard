# Wastage Dashboard — User Manual

## 1. Adding new daily/weekly data (automatic update)

Just drop your exported file straight into the **`Uploads/`** folder inside your
`WastageSystem` project folder — nothing else to do.

- The server checks that folder every 15 seconds.
- New files are read, cleaned, and added to the database automatically.
- If you drop the same file twice (same content), it's skipped — no duplicates.
- The dashboard updates on its own next time it refreshes (every 30 seconds), or
  you can just refresh the browser page.

**File naming rule** — the system detects what a file is from its name, so keep the
same pattern your exports already use:

| File contains in its name | Treated as |
|---|---|
| `known_loss` | Known Loss data |
| `unknown_loss` | Unknown Loss data |
| `sales` | Sales data |

Example: `328_Unknown_Loss_Base_29Aug.csv` → detected as Unknown Loss automatically.

You do **not** need to restart the server to add new data — only restart it if you
change the Python code itself (like `main.py`, `importer.py`, `alerts.py`).

## 2. How the pieces are connected

```
Uploads/ (you drop files here)
     │
     ▼
importer.py  →  reads the file, cleans it, checks for duplicates
     │
     ▼
Database/wastage.db  (SQLite — all your historical data lives here)
     │
     ▼
main.py  →  the web server; answers the dashboard's data requests
     │
     ▼
dashboard.html  →  what you see in the browser (charts, filters, alerts)
```

- **`Uploads/`** — daily drop folder.
- **`importer.py`** — the "reader." Knows how to parse Known Loss, Unknown Loss,
  and Sales files, and which columns mean what.
- **`Database/wastage.db`** — single file holding all imported data. If this ever
  gets corrupted or you want to start fresh, just delete it and restart the
  server — it rebuilds from everything in `Uploads/`.
- **`alerts.py`** — checks each new day's data for spikes (unusually high wastage
  vs. the last 14 days) and creates alerts.
- **`main.py`** — the backend. Runs the folder-watcher, serves the dashboard page,
  and answers all the numbers/charts you see.
- **`dashboard.html`** — everything you see and click. One single file (HTML,
  styling, and behavior all together) so it's easy to move or share.

## 3. Running it day to day

1. Open a terminal in your `WastageSystem` folder.
2. Run: `python main.py`
3. Leave that window open (closing it stops the server).
4. Open `http://localhost:8000` in your browser.
5. Whenever you have a new day's export, drop it in `Uploads/` — no restart needed.

## 4. What the numbers mean

- **Known Loss** — confirmed wastage recorded directly (excludes Consumables).
- **Unknown Loss** — stock discrepancy/shrinkage (excludes Consumables). Shown as
  a positive number in the top summary cards; store/item breakdown tables further
  down show it with its original sign (negative = shrinkage, matches your sheet).
- **Consumables** — packaging/consumable items wastage, combined from both Known
  and Unknown sources.
- **Total Loss** = Known Loss + Unknown Loss.
- **Overall / Total Wastage** = Total Loss + Consumables.
- **Total Loss % of Sales** = Total Loss ÷ Sales × 100.

## 5. Filters & the Value/Qty/% toggle

- Sidebar filters (date, cluster, store, category, article, wastage type, day,
  week, month) apply to every chart and KPI card at once — pick what you want,
  click **Apply Filters**.
- Top-right toggle switches every KPI card between **₹ Value**, **Qty**, and **%**
  without needing to touch the filters.

## 6. Alerts

The **Alerts Center** at the bottom flags stores/items whose wastage today is
50%+ above their normal 14-day average. Severity: 🔴 Critical (200%+),
🟠 High (100%+), 🟡 Medium (50%+). New Critical alerts also pop up as a toast.
