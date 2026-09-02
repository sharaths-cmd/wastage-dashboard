"""
Run this ON YOUR PC. It watches your local Uploads folder and automatically
sends any new file to your cloud-hosted dashboard, so your workflow stays
exactly the same: just drop files in Uploads/ like before.

Usage:
    python sync_to_cloud.py

Edit CLOUD_URL below to your deployed dashboard's address first.
"""
import os
import time
import requests

CLOUD_URL = "https://your-app-name.onrender.com"   # <-- change this after deploying
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "Uploads")
CHECK_EVERY_SECONDS = 15

already_sent = set()


def sync_once():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    for fn in os.listdir(UPLOAD_DIR):
        if fn in already_sent:
            continue
        if not fn.lower().endswith((".csv", ".xlsx", ".xls")):
            continue
        path = os.path.join(UPLOAD_DIR, fn)
        try:
            with open(path, "rb") as f:
                resp = requests.post(f"{CLOUD_URL}/api/upload", files={"file": (fn, f)}, timeout=60)
            print(f"[sent] {fn} -> {resp.json()}")
            already_sent.add(fn)
        except Exception as e:
            print(f"[error] {fn}: {e}")


if __name__ == "__main__":
    print(f"Watching {UPLOAD_DIR} — will push new files to {CLOUD_URL}")
    while True:
        sync_once()
        time.sleep(CHECK_EVERY_SECONDS)
