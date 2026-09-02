# Run Without CMD

## Start it silently (no black window)
Double-click **`Start_Dashboard_Silently.vbs`** in your project folder.
- No CMD window appears.
- Closing anything (or logging in/out) does NOT stop it.
- It keeps running in the background until the PC restarts or you stop it
  manually (Task Manager → find `pythonw.exe` → End Task).

## Make it start automatically every time your PC turns on
So you never have to remember to start it at all:

1. Press `Win + R`, type `shell:startup`, press Enter. A folder opens.
2. Right-click `Start_Dashboard_Silently.vbs` → **Copy**.
3. Paste it into that Startup folder (right-click → Paste, or create a
   shortcut to it and paste the shortcut instead).

Now every time your PC boots up, the dashboard starts automatically in the
background — no CMD, no manual step, ever. Your manager's link just keeps
working as long as the PC is powered on.

## Note
This still requires your PC to be powered on (not just logged in — sleep/
shutdown will stop it, but it restarts itself automatically next boot thanks
to the Startup folder step above). If you need it available even when your
PC is fully off, that needs cloud hosting instead — see `DEPLOY_TO_CLOUD.md`.
