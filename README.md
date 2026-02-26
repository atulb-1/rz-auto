# Definedge RZone Momentum Scanner Automation

Fully automated browser-based workflow for Definedge Securities RZone platform. Logs in, navigates to the Momentum Investing Scanner, runs scans for each configured strategy, exports results as CSV, and sends notifications + files to Telegram.

---

## Quick Start

```
1. Run  setup.bat        (first time only — installs everything)
2. Edit config.ini       (add your credentials + strategies)
3. Run  run_scanner.bat  (starts the full automation)
```

---

## Files Overview

| File | Purpose |
|---|---|
| `setup.bat` | First-time setup: creates virtual environment, installs Python packages, downloads Chromium |
| `config.ini` | Your credentials, strategies, download path, Telegram settings (**do not share**) |
| `config_sample.ini` | Template for config.ini (safe to share, no real credentials) |
| `rzone_scanner.py` | Main automation script — runs all strategies end-to-end |
| `rzone_login_only.py` | Login-only script — stops after I Agree, hands browser to you |
| `run_scanner.bat` | Launches `rzone_scanner.py` with venv activated |
| `run_login_only.bat` | Launches `rzone_login_only.py` with venv activated |
| `README.md` | This file |

---

## Prerequisites

- **Windows 10/11**
- **Python 3.9+** — download from https://www.python.org/downloads/
  - IMPORTANT: check **"Add Python to PATH"** during installation
- **Internet connection** (for login, scanning, and Telegram)

---

## Setup (First Time)

1. **Double-click `setup.bat`** — it will:
   - Verify Python is installed
   - Create a virtual environment (`venv` folder)
   - Install packages: `playwright`, `pyotp`, `requests`
   - Download the Chromium browser that Playwright uses
   - Verify everything works

2. **Create `config.ini`**:
   - Copy `config_sample.ini` to `config.ini`
   - Fill in your UCC, Password, and TOTP Secret
   - Add strategy names (exactly as they appear in the RZone dropdown)
   - Optionally configure Telegram (see Telegram Setup below)

---

## Configuration (config.ini)

### Credentials
| Field | Description |
|---|---|
| `URL` | Definedge login URL (default works, usually no change needed) |
| `UCC` | Your User Client Code |
| `PASSWORD` | Your login password |
| `TOTP_SECRET` | Base32 secret key for OTP generation (NOT the 6-digit code) |

### Finding Your TOTP Secret
The TOTP secret is the Base32 string used when you first set up your authenticator app. It looks like `MVGEWMTZJAYUY2CIO5WTISSJNNTGK5LS`. If you used a QR code, the secret is embedded in the QR URL. Some authenticator apps (like Aegis, andOTP) let you export/view the secret.

### Strategies
Add one strategy per line under `[STRATEGIES] LIST =`. Names must **exactly match** what appears in the Momentify dropdown on RZone. Example:
```ini
LIST =
    MIP 37 As is
    MIP-34
    ETF_MONTHLY_1
    ETF_WEEKLY
```

### Telegram (Optional)
| Field | Description |
|---|---|
| `BOT_TOKEN` | Token from @BotFather (create a bot, get the token) |
| `CHAT_ID` | Your chat/group ID (use @userinfobot or @getidsbot) |

Leave both blank to disable Telegram. For group chats the CHAT_ID starts with `-100`.

---

## Usage

### Full Automation (run_scanner.bat)
Double-click `run_scanner.bat`. It will:
1. Activate the virtual environment
2. Run `rzone_scanner.py`
3. A Chromium browser window opens — **do not close it or interact with it**
4. Watch the console for real-time progress logs
5. Files are saved to `DOWNLOAD_DIR/DD_MM_YYYY/`
6. Telegram notifications sent for each strategy (if configured)

### Login Only (run_login_only.bat)
Double-click `run_login_only.bat`. Useful for:
- Testing that login works
- Manual debugging of RZone
- Checking if selectors have changed

It automates up to I Agree, then hands the browser to you. Press ENTER in the console to close.

---

## How It Works — Step by Step

### Login Flow
1. Opens the Definedge login URL in Chromium
2. Dismisses any homepage popup (presses Escape)
3. Clicks "Login" link (opens login popup) — retries up to 3 times if popup is blocked
4. Fills UCC and Password from config.ini
5. Clicks Sign In
6. Auto-generates OTP using the TOTP secret and submits
7. Waits for MyAccount page (polls for "Analyse & Trade" button)

### Navigation to Scanner
8. Clicks "Analyse & Trade" (opens RZone in new tab)
9. Handles "I Agree" dialog — uses 4 detection methods (button role, text match, XPath, iframe scan) since the element type varies
10. Clicks Momentum Scanner in the sidebar
11. Clicks Momentum Investing Scanner link
12. Waits for the Scan button to confirm the scanner panel is ready

### Strategy Scanning Loop
For each strategy in the configured list:

13. **Check Momentify** — clicks the Momentify group checkbox
14. **Select strategy** — picks the strategy from dropdown (3 fallback selection methods)
15. **Uncheck Momentify** — deselects the group checkbox
16. **Market Trend Filter** — checks if the filter is enabled:
    - If enabled: clicks it, clicks SAVE in the popup
    - If disabled/greyed out: skips directly to Scan
17. **Click Scan** — starts the scan
18. **Monitor scan progress** — polls every 0.5 seconds, watching for:
    - Export button becoming enabled (scan complete with results)
    - "Scan Completed" text appearing
    - "Qualified Scrips : 0" (scan complete, no results)
    - Validation Filter popup (filter not qualified)
    - Processing text changes (stuck detection)
19. **Export** — downloads the CSV and renames it

### Retry Logic
Each strategy is attempted up to **2 times** before moving to the next. If attempt 1 fails (any error), it logs the error and retries once.

---

## Timing, Timeouts & Stuck Detection

| Situation | Timeout | Action |
|---|---|---|
| Login page load | 30 seconds | Error |
| OTP field appear | 30 seconds | Error |
| MyAccount load | 60 seconds | Continue anyway |
| I Agree dialog | 45 seconds | Continue anyway |
| Scanner panel load | 30 seconds | Error |
| Scan processing | 8 minutes | Cancel + re-scan |
| Scan hard timeout | 15 minutes | Give up, move to next |
| Processing stuck | 90 seconds no change | Cancel + re-scan |
| Export/download | 60 seconds | Error |

### Stuck Detection (Processing Intelligence)
The script reads the "Processing ..(X/Y), Stock_name" text every 0.5 seconds. If the text doesn't change for **90 seconds**, it considers the scan stuck, cancels it, and retries. This catches scenarios where the server hangs mid-scan.

After either a stuck-cancel or a time-based cancel (8 min), the scan is retried once. If the retry also fails after 15 minutes total, the strategy is skipped.

---

## Edge Cases & Known Behaviors

### I Agree Dialog
- Sometimes appears, sometimes doesn't (if previously accepted in the same session)
- Detection uses 4 methods: button role, text match, XPath across element types, iframe scan
- If not found within 45 seconds, continues anyway

### Validation Filter Popup
- Some strategies trigger a "Validation Filter not qualified" popup
- The script automatically: closes the popup, unchecks the Market Trend Filter checkbox, and re-scans
- The exported file gets a `_filter_not_qualified` suffix

### 0 Qualified Scrips
- When a scan completes with "Qualified Scrips : 0 (0.00%)", there's nothing to export
- The script creates an empty CSV named `{strategy}_{date}_No_Qualified_Scrips.csv`

### Market Trend Filter Disabled
- Some strategies don't have the Market Trend Filter available (greyed out)
- The script checks if it's enabled (via disabled state, CSS opacity, pointer-events)
- If disabled, it skips directly to Scan

### Home Page Popup
- The Definedge home page sometimes shows a marketing popup that blocks the Login button
- The script presses Escape before clicking Login, with up to 3 retry attempts

### Strategy Dropdown State
- After the first strategy is selected, the dropdown's label changes from "-- Select Momentify Strategies --" to the previously selected name
- The script uses 3 fallback methods to find the dropdown: option-text search, cell role regex, first visible select

---

## Output Files

Files are saved to: `DOWNLOAD_DIR / DD_MM_YYYY /`

| Filename Pattern | Meaning |
|---|---|
| `Strategy_DD_MM_YYYY.csv` | Normal successful scan export |
| `Strategy_DD_MM_YYYY_filter_not_qualified.csv` | Re-scanned after Validation Filter popup |
| `Strategy_DD_MM_YYYY_No_Qualified_Scrips.csv` | Empty file, 0 scrips qualified |

---

## Telegram Notifications

When configured, the script sends:
- Start notification with strategy list
- Per-strategy status (scanning, completed, errors)
- Exported CSV files as attachments
- Final summary of all strategies

---

## Troubleshooting

### "Python not found"
Install Python 3.9+ and ensure "Add Python to PATH" is checked during install. Restart your terminal after installing.

### "playwright install" fails
Run manually in the venv:
```
venv\Scripts\activate
playwright install chromium
```

### Login fails / OTP rejected
- Verify UCC and PASSWORD in config.ini (no extra spaces)
- Verify TOTP_SECRET is the Base32 secret (not the 6-digit code)
- Check your system clock is accurate (OTP is time-based, even 30 seconds off can cause rejection)

### Strategy not found in dropdown
- Strategy names must exactly match what appears in the RZone Momentify dropdown
- Check for typos, extra spaces, or case differences

### Scan takes too long
- Scans auto-cancel and retry after 8 minutes
- Hard timeout is 15 minutes per scan
- Stuck detection cancels after 90 seconds of no progress change
- If the RZone server itself is slow, there's nothing the script can do

### Browser closes unexpectedly
- Don't click inside the automated browser window
- Don't minimize it (some elements need to be "visible" for Playwright)
- Keep the console window open

### "I Agree" not being clicked
- The script tries 4 detection methods over 45 seconds
- If the RZone page changed its element type, the XPath fallback should catch it
- Use `run_login_only.bat` to test login + I Agree independently

### Market Trend Filter issues
- If the SAVE button in the popup can't be found, the script tries a text-based fallback
- If the entire filter is disabled, it's automatically skipped

---

## Security Notes

- `config.ini` contains your **plain-text password and TOTP secret** — do not share it or commit it to version control
- `config_sample.ini` is safe to share (no real credentials)
- The Telegram bot token gives access to send messages via your bot — keep it private
- The script runs a real Chromium browser (not headless) so you can visually verify what it's doing

---

## Project Structure

```
trading_rzone_automation/
  setup.bat               ← Run first (one-time setup)
  config.ini              ← Your settings (DO NOT SHARE)
  config_sample.ini       ← Template (safe to share)
  rzone_scanner.py        ← Main automation
  rzone_login_only.py     ← Login-only automation
  run_scanner.bat         ← Launch scanner
  run_login_only.bat      ← Launch login-only
  README.md               ← This file
  venv/                   ← Virtual environment (created by setup.bat)
```
