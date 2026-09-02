# Deploying the Dashboard to the Cloud (Free) — for your manager's access

This makes the dashboard reachable from **any phone or PC, anywhere**, on a
permanent link — not tied to your PC being on. Using Render.com's free tier
(no credit card needed).

## One-time setup (15-20 minutes)

### Step 1: Put your project on GitHub
1. Go to https://github.com and create a free account if you don't have one.
2. Create a new repository (e.g. `wastage-dashboard`), keep it **Private**.
3. Upload your whole `WastageSystem` folder to it (GitHub's website lets you
   drag-and-drop files — click "uploading an existing file" on the repo page).
   - **Do not upload** the `Database/wastage.db` file itself if it's large —
     the cloud copy will start empty and you'll feed it data via Step 4 below.

### Step 2: Deploy on Render
1. Go to https://render.com and sign up free (you can sign in with GitHub).
2. Click **New +** → **Web Service**.
3. Connect your GitHub repo (`wastage-dashboard`).
4. Fill in:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Instance Type**: Free
5. Click **Create Web Service**. Wait a few minutes for it to build.
6. You'll get a permanent link like `https://wastage-dashboard-xxxx.onrender.com`
   — this is what you share with your manager.

**Note:** on the free tier, the service "sleeps" after 15 minutes of no
traffic and takes ~30 seconds to wake up on the next visit. That's the
trade-off for free hosting — fine for daily check-ins, just expect a short
delay on the first open of the day.

### Step 3: Install it like an app on your manager's phone
1. Open the Render link in their phone's browser.
2. Tap the browser menu → **"Add to Home Screen"** (Chrome/Safari both support
   this since it's a PWA).
3. It now sits on their home screen with an icon, opens full-screen like a
   real app.

### Step 4: Keep feeding it your daily data automatically
On your PC, open `sync_to_cloud.py` in the project folder and change this
line at the top to your actual Render link from Step 2:
```python
CLOUD_URL = "https://wastage-dashboard-xxxx.onrender.com"
```
Then run it once and leave it running whenever you're at your PC:
```
pip install requests
python sync_to_cloud.py
```
Now your exact same habit — drop a file into the local `Uploads/` folder —
automatically pushes it to the cloud dashboard your manager sees. You don't
need to change anything about how you work day to day.

## If you'd rather I just do the deployment for you
I can't directly push to GitHub or Render from here (no login access to your
accounts), so these steps do need to be done on your end — but if you get
stuck on any specific step, paste me the exact error and I'll help you
through just that part, without repeating the whole guide.
