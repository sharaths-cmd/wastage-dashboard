# Wastage Management System

Full stack: FastAPI backend + SQLite + auto-import + premium HTML/JS dashboard (PWA-installable).

## 1. Setup (one time)

Requires Python 3.10+.

```bash
cd WastageSystem
pip install -r requirements.txt
```

## 2. Run

```bash
python3 main.py
```

Then open **http://localhost:8000** in a browser (or `http://<your-pc-ip>:8000` from your phone on
the same WiFi). On mobile, open the site and use "Add to Home Screen" to install it as an app.

## 3. Daily workflow

Drop your daily Excel/CSV export into the `Uploads/` folder. The app automatically scans that
folder every 15 seconds, detects new/changed files, imports them, skips duplicates, and refreshes
alerts. No restart needed. You can also upload a file manually from the dashboard sidebar.

**File naming matters** — the importer detects file type from the filename:
- Filename contains "known_loss" → Known Loss data
- Filename contains "unknown_loss" → Unknown Loss / stock-discrepancy data
- Filename contains "sales" → Sales data

Keep your export filenames consistent with your current pattern (e.g.
`..._Known_Loss_Base.csv`, `..._Unknown_Loss_Base.csv`, `..._Sales_Base.csv`) and it will just work.

## 4. How the numbers are calculated

- **Known Loss** = all rows in the Known Loss file except category `CONSUMABLES`.
- **Consumables** = rows in the Known Loss file where category = `CONSUMABLES`.
- **Unknown Loss** = only the *negative* stock-discrepancy rows in the Unknown Loss file
  (actual stock found less than expected = real shrinkage). Positive discrepancies (excess stock
  found during a count) are excluded from loss totals — they're not wastage.
- **Total Loss** = Known Loss + Unknown Loss.
- **Total Wastage (incl. consumables)** = Total Loss + Consumables.
- **Total Loss %** = Total Loss ÷ Sales × 100.

If your business wants excess stock counted differently, or wants Unknown Loss calculated some
other way, edit `import_unknown_loss()` in `importer.py`.

## 5. Alerts

Alerts regenerate automatically every time new data is imported. Rules (edit thresholds in
`alerts.py`):
- **Article spike**: an item's wastage at a store is 50%+ above its 14-day trailing average
  (only flagged if today's value is meaningfully large, to avoid noise on tiny numbers).
- **Store spike**: a store's total wastage is 50%+ above its 14-day average.
- **Category spike**: a category's wastage is 50%+ above its 14-day average.
- **Unknown Loss threshold**: a store's unknown loss exceeds ₹5,000/day.

Severity: 🔴 Critical (200%+ over average), 🟠 High (100%+), 🟡 Medium (50%+).

The dashboard polls `/api/alerts` and pops a toast for new Critical alerts.

## 6. Hosting so your team can access it from anywhere

Running `python3 main.py` on your own PC only works while that PC is on and the phone/other
users are on the same network (or you port-forward). For always-on access from anywhere:
- Rent a small cloud VPS (DigitalOcean, AWS Lightsail, Hetzner — ~$5/month) and run the same
  command there, or
- Use a process manager (`pm2`, `systemd`, or `screen`/`tmux`) so it survives reboots/disconnects.

No code changes needed either way — same `python3 main.py`.

## 7. Project structure

```
WastageSystem/
├── main.py          FastAPI app + all API endpoints + background folder watcher
├── database.py       SQLite schema
├── importer.py        File detection, parsing, dedup logic
├── alerts.py          Spike detection engine
├── requirements.txt
├── Uploads/            <-- put your daily files here
├── Database/           wastage.db lives here (auto-created)
├── static/             CSS/JS/PWA files
└── templates/
    └── index.html      dashboard page
```
