"""
DefineE RZ Momentum Scanner Automation
=======================================
Fully automated: login, OTP, scan, export, Telegram notifications.

Setup:
    pip install playwright pyotp requests
    playwright install chromium

Usage:
    python rz_scanner.py
"""

import asyncio
import configparser
import pyotp
import re
import sys
import time
import requests
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


# ─────────────────────────────────────────────────────────────────────────────
# Load config.ini
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.ini"

def load_config():
    config = configparser.ConfigParser()
    if not CONFIG_PATH.exists():
        print(f"ERROR: config.ini not found at {CONFIG_PATH}")
        sys.exit(1)
    config.read(CONFIG_PATH)
    return config

config       = load_config()
UCC          = config["CREDENTIALS"]["UCC"].strip()
PASSWORD     = config["CREDENTIALS"]["PASSWORD"].strip()
TOTP_SECRET  = config["CREDENTIALS"]["TOTP_SECRET"].strip()
DOWNLOAD_DIR = Path(config["SETTINGS"]["DOWNLOAD_DIR"].strip())
STRATEGIES   = [s.strip() for s in config["STRATEGIES"]["LIST"].strip().splitlines() if s.strip()]

# Telegram (optional — leave blank in config to disable)
TG_TOKEN   = config.get("TELEGRAM", "BOT_TOKEN", fallback="").strip()
TG_CHAT_ID = config.get("TELEGRAM", "CHAT_ID", fallback="").strip()
TG_ENABLED = bool(TG_TOKEN and TG_CHAT_ID)

DATE_STR = datetime.now().strftime("%d_%m_%Y")   # DD_MM_YYYY
DOWNLOAD_DIR = DOWNLOAD_DIR / DATE_STR           # e.g. .../Monthly Stock Portfolios Rankings_AUTOMATED/23_02_2026/
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def separator(title=""):
    print(f"\n{'─' * 55}")
    if title:
        print(f"  {title}")
        print(f"{'─' * 55}")

def tg(msg):
    """Send a message to Telegram. Silently fails if not configured or error."""
    if not TG_ENABLED:
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception:
        pass

def tg_file(file_path, caption=""):
    """Send a file to Telegram. Silently fails if not configured or error."""
    if not TG_ENABLED:
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
        with open(file_path, "rb") as f:
            requests.post(
                url,
                data={"chat_id": TG_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files={"document": (Path(file_path).name, f)},
                timeout=30
            )
        log(f"📤 Sent to Telegram: {Path(file_path).name}")
    except Exception as e:
        log(f"⚠️  Telegram file send failed: {e}")

def notify(msg):
    """Log to console AND send to Telegram."""
    log(msg)
    tg(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
async def dismiss_overlay(page):
    """Dismiss any GWT popup glass overlay that blocks pointer events."""
    try:
        glass = page.locator("div.gwt-PopupPanelGlass")
        if await glass.first.is_visible():
            log("GWT overlay detected — dismissing...")
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            if await glass.first.is_visible():
                await page.evaluate(
                    "document.querySelectorAll('.gwt-PopupPanelGlass').forEach(e => e.remove())"
                )
                await asyncio.sleep(0.3)
                log("Overlay removed via JS")
            else:
                log("Overlay dismissed via Escape")
    except Exception:
        pass


async def run():
    separator("DefineE RZ Scanner Automation Starting")
    log(f"Strategies : {STRATEGIES}")
    log(f"Save folder: {DOWNLOAD_DIR}")
    log(f"Date suffix: {DATE_STR}")
    log(f"Telegram   : {'Enabled ✅' if TG_ENABLED else 'Disabled (no token/chat_id in config.ini)'}")

    if not STRATEGIES:
        log("ERROR: No strategies found in config.ini [STRATEGIES] LIST.")
        sys.exit(1)

    tg(f"🚀 <b>RZ Scanner Started</b>\n"
       f"Strategies: {len(STRATEGIES)}\n"
       f"Date: {DATE_STR}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=300,
            args=["--start-maximized"]
        )
        context = await browser.new_context(
            viewport=None,
            no_viewport=True,
            accept_downloads=True
        )
        page = await context.new_page()


        # ── STEP 1: Home Page ────────────────────────────────────────────────
        separator("STEP 1: Opening DefineE Home Page")
        await page.goto("https://www.definedgesecurities.com/", wait_until="domcontentloaded", timeout=60000)
        log("Home page loaded.")

        await page.get_by_role("link", name="Login").wait_for(state="visible", timeout=15000)
        await page.keyboard.press("Escape")


        # ── STEP 2: Click Login → Opens popup ────────────────────────────────
        separator("STEP 2: Login Popup")
        log("Clicking Login link...")
        page1 = None
        for attempt in range(3):
            try:
                async with page.expect_popup(timeout=5000) as page1_info:
                    await page.get_by_role("link", name="Login").click()
                page1 = await page1_info.value
                break
            except PlaywrightTimeout:
                log(f"Login attempt {attempt+1} blocked — dismissing & retrying...")
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.2)
        if page1 is None:
            notify("❌ Could not open login page after 3 attempts.")
            sys.exit(1)
        await page1.wait_for_load_state("domcontentloaded", timeout=30000)
        log("Login popup opened.")


        # ── STEP 3: Enter UCC + Password ─────────────────────────────────────
        separator("STEP 3: Credentials")
        log("Filling UCC...")
        await page1.get_by_role("textbox", name="UCC").click()
        await page1.get_by_role("textbox", name="UCC").fill(UCC)
        log(f"UCC entered: {UCC}")

        log("Filling Password...")
        await page1.get_by_role("textbox", name=re.compile(r"Password", re.IGNORECASE)).click()
        await page1.get_by_role("textbox", name=re.compile(r"Password", re.IGNORECASE)).fill(PASSWORD)
        log("Password entered.")

        log("Clicking Sign In...")
        await page1.get_by_role("button", name="Sign In").click()


        # ── STEP 4: OTP (auto-generated) ─────────────────────────────────────
        separator("STEP 4: OTP (Auto)")
        log("Waiting for OTP page...")
        await page1.get_by_role("textbox", name=re.compile(r"Code", re.IGNORECASE)).wait_for(
            state="visible", timeout=30000
        )
        log("OTP field ready.")

        totp   = pyotp.TOTP(TOTP_SECRET)
        code   = totp.now()
        expiry = 30 - (datetime.now().second % 30)
        log(f"Generated OTP: {code}  (valid for ~{expiry}s)")
        await page1.get_by_role("textbox", name=re.compile(r"Code", re.IGNORECASE)).click()
        await page1.get_by_role("textbox", name=re.compile(r"Code", re.IGNORECASE)).fill(code)
        log("OTP entered.")

        await page1.get_by_role("button", name="Submit").click()
        log("Submit clicked.")


        # ── STEP 5: Wait for MyAccount (race for Analyse & Trade button) ────
        separator("STEP 5: MyAccount")
        log("Waiting for MyAccount / Analyse & Trade to appear...")
        analyse_btn = page1.get_by_role("button", name="Analyse & Trade")
        for _ in range(120):
            try:
                if await analyse_btn.is_visible():
                    log(f"MyAccount loaded ✅  →  {page1.url}")
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        else:
            log("⚠️  Analyse & Trade not found in 60s — attempting anyway...")

        notify("✅ Logged in to MyAccount")


        # ── STEP 6: Analyse & Trade → Opens RZone popup ──────────────────────
        separator("STEP 6: RZ → Analyse & Trade")
        log("Clicking Analyse & Trade button...")
        async with page1.expect_popup() as page2_info:
            await analyse_btn.click()
        page2 = await page2_info.value
        log(f"RZ popup captured →  {page2.url}")

        # RZ SPA does client-side redirects — wait for page to stabilize
        log("Waiting for RZone page to settle...")
        for attempt in range(30):  # up to 15 seconds
            try:
                await page2.wait_for_load_state("domcontentloaded", timeout=5000)
                await asyncio.sleep(1)
                body_len = await page2.evaluate("document.body ? document.body.innerText.length : 0")
                if body_len > 100:
                    break
            except Exception as e:
                # Execution context destroyed = page is navigating, just wait and retry
                log(f"Page still loading/navigating... ({type(e).__name__})")
                await asyncio.sleep(1)

        await page2.bring_to_front()
        await asyncio.sleep(1)
        log(f"RZ page ready ✅  →  {page2.url}")


        # ── STEP 7: I Agree (may or may not appear) ─────────────────────────
        separator("STEP 7: I Agree")
        log("Waiting for I Agree or page to be ready...")

        # Multiple ways to find the I Agree element (button, link, or any clickable)
        i_agree_by_role  = page2.get_by_role("button", name="I Agree")
        i_agree_by_text  = page2.get_by_text(re.compile(r"^I\s*Agree$", re.IGNORECASE))
        i_agree_by_xpath = page2.locator("xpath=//button[contains(text(),'Agree')] | //a[contains(text(),'Agree')] | //div[contains(text(),'Agree')] | //span[contains(text(),'Agree')]")
        page_ready       = page2.get_by_text("Momentum Scanner")

        found = False
        for tick in range(90):   # up to 45 seconds
            # Try button role first
            try:
                if await i_agree_by_role.is_visible():
                    await i_agree_by_role.click()
                    log("Clicked I Agree (button role) ✅")
                    await asyncio.sleep(2)
                    found = True
                    break
            except Exception:
                pass

            # Try text-based match
            try:
                if await i_agree_by_text.first.is_visible():
                    await i_agree_by_text.first.click()
                    log("Clicked I Agree (text match) ✅")
                    await asyncio.sleep(2)
                    found = True
                    break
            except Exception:
                pass

            # Try XPath (covers button/a/div/span)
            try:
                if await i_agree_by_xpath.first.is_visible():
                    await i_agree_by_xpath.first.click()
                    log("Clicked I Agree (xpath match) ✅")
                    await asyncio.sleep(2)
                    found = True
                    break
            except Exception:
                pass

            # Check if page already loaded past I Agree
            try:
                if await page_ready.is_visible():
                    log("I Agree not shown — already accepted. Continuing...")
                    found = True
                    break
            except Exception:
                pass

            # Also check inside iframes (some SPAs put dialogs in frames)
            if tick == 20:  # check once at ~10s mark
                for frame in page2.frames:
                    try:
                        frame_agree = frame.get_by_text(re.compile(r"I\s*Agree", re.IGNORECASE))
                        if await frame_agree.first.is_visible():
                            await frame_agree.first.click()
                            log("Clicked I Agree (inside iframe) ✅")
                            await asyncio.sleep(2)
                            found = True
                            break
                    except Exception:
                        pass
                if found:
                    break

            await asyncio.sleep(0.5)

        if not found:
            log("Neither I Agree nor page content found in 45s — continuing anyway...")


        # ── STEP 8: Momentum Scanner ─────────────────────────────────────────
        separator("STEP 8: Opening Momentum Scanner")
        log("Clicking Momentum Scanner...")
        await page2.get_by_text("Momentum Scanner").click()
        await asyncio.sleep(1)

        log("Clicking Momentum Investing Scanner...")
        await page2.get_by_role("link", name=re.compile(r"Momentum Investing Scanner", re.IGNORECASE)).click()
        await asyncio.sleep(3)

        log("Waiting for scanner panel to load...")
        await page2.get_by_role("button", name="Scan").wait_for(state="visible", timeout=30000)
        log("Momentum Investing Scanner opened ✅")

        notify("✅ RZ Momentum Scanner ready")


        # ── STEP 9: Loop through strategies ─────────────────────────────────
        results = []   # track results for final summary

        for idx, strategy in enumerate(STRATEGIES, 1):
            separator(f"Strategy {idx}/{len(STRATEGIES)}: {strategy}")
            notify(f"📊 Scanning {idx}/{len(STRATEGIES)}: <b>{strategy}</b>")

            # ── Retry wrapper: try each strategy up to 2 times ────────────
            MAX_ATTEMPTS = 2
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    if attempt > 1:
                        log(f"🔄 RETRY attempt {attempt}/{MAX_ATTEMPTS} for {strategy}")
                        notify(f"🔄 Retrying <b>{strategy}</b> (attempt {attempt})")
                        await asyncio.sleep(3)

                    # Dismiss any leftover GWT overlay from previous strategy
                    await dismiss_overlay(page2)

                    # 9a. Check Mmfy checkbox
                    log("Checking Mmfy checkbox...")
                    mmfy_label = page2.get_by_role("cell", name=re.compile(r"Group\s*:")).locator("label")
                    await mmfy_label.wait_for(state="visible", timeout=15000)
                    await mmfy_label.click()
                    await asyncio.sleep(0.3)
                    log("Mmfy: checked ✅")

                    # 9b. Select strategy from dropdown
                    log(f"Selecting strategy: '{strategy}'")
                    dropdown = None
                    try:
                        dropdown = page2.locator("select").filter(
                            has=page2.locator("option", has_text=re.compile(r"Momentify", re.IGNORECASE))
                        ).first
                        await dropdown.wait_for(state="visible", timeout=2000)
                    except PlaywrightTimeout:
                        dropdown = None

                    if dropdown is None:
                        try:
                            dropdown = page2.get_by_role("cell", name=re.compile(r"Select Momentify|Momentify", re.IGNORECASE)).get_by_role("combobox")
                            await dropdown.wait_for(state="visible", timeout=2000)
                        except PlaywrightTimeout:
                            dropdown = None

                    if dropdown is None:
                        dropdown = page2.locator("select:visible").first
                        await dropdown.wait_for(state="visible", timeout=5000)

                    await dropdown.select_option(strategy)
                    await asyncio.sleep(0.8)
                    log(f"Strategy '{strategy}' selected ✅")

                    # 9c. Uncheck Mmfy checkbox
                    await dismiss_overlay(page2)
                    log("Unchecking Mmfy checkbox...")
                    mmfy_label_after = page2.get_by_role("cell", name=re.compile(r"Group\s*:")).locator("label")
                    await mmfy_label_after.wait_for(state="visible", timeout=10000)
                    await mmfy_label_after.click()
                    await asyncio.sleep(0.8)
                    log("Mmfy: unchecked ✅")

                    # 9c2. Market trend Filter — only if enabled
                    market_filter_btn = page2.get_by_text(re.compile(r"Market.*trend.*Filter|Market.*Filter", re.IGNORECASE)).first
                    market_filter_enabled = False
                    try:
                        await market_filter_btn.wait_for(state="visible", timeout=3000)
                        # Check if the button/link is actually enabled (not greyed out / disabled)
                        is_disabled = await market_filter_btn.is_disabled()
                        # Also check for CSS opacity or disabled-looking class
                        opacity = await market_filter_btn.evaluate("el => getComputedStyle(el).opacity")
                        pointer = await market_filter_btn.evaluate("el => getComputedStyle(el).pointerEvents")
                        if is_disabled or float(opacity) < 0.5 or pointer == "none":
                            log("Market trend Filter is DISABLED — skipping, going to Scan directly.")
                        else:
                            market_filter_enabled = True
                    except PlaywrightTimeout:
                        log("Market trend Filter button not found — skipping, going to Scan directly.")

                    if market_filter_enabled:
                        log("Market trend Filter is ENABLED — clicking...")
                        try:
                            await market_filter_btn.click()
                            await asyncio.sleep(1)
                            log("Market trend Filter popup opened.")

                            # Click SAVE in the popup (XPath for the button inside popup)
                            save_btn = page2.locator("xpath=/html/body/div[7]/div/table/tbody/tr[3]/td/div/table/tbody/tr/td[1]/button")
                            try:
                                await save_btn.wait_for(state="visible", timeout=5000)
                                await save_btn.click()
                            except PlaywrightTimeout:
                                # Fallback: try any button with Save text
                                await page2.get_by_role("button", name=re.compile(r"Save", re.IGNORECASE)).first.click()
                            await asyncio.sleep(0.5)
                            log("Market trend Filter: SAVE clicked ✅")
                        except PlaywrightTimeout:
                            log("⚠️  Market trend Filter popup/SAVE not found — continuing...")

                    # 9d. Click Scan and handle result
                    filter_not_qualified = False
                    no_qualified_scrips  = False
                    log("Clicking Scan button...")
                    await page2.get_by_role("button", name="Scan").click()
                    log("Scan started...")

                    # 9e. Wait for scan result — 15 min total, cancel & retry after 8 min or if stuck
                    CANCEL_RETRY_SECS = 8 * 60   # 8 minutes
                    HARD_TIMEOUT_SECS = 15 * 60  # 15 minutes
                    STUCK_THRESHOLD   = 90        # seconds with no progress change → stuck

                    log(f"Waiting for scan result (max {HARD_TIMEOUT_SECS//60} min, "
                        f"cancel+retry at {CANCEL_RETRY_SECS//60} min, stuck detect at {STUCK_THRESHOLD}s)...")
                    export_btn = page2.get_by_role("button", name="Export")
                    scan_completed_text = page2.get_by_text(re.compile(r"Scan\s*Completed", re.IGNORECASE))
                    validation_popup = page2.get_by_text(re.compile(r"Validation Filter.*not qualified|Filter.*not qualified", re.IGNORECASE))
                    processing_text  = page2.get_by_text(re.compile(r"Processing", re.IGNORECASE))
                    cancel_btn       = page2.get_by_role("button", name=re.compile(r"Cancel", re.IGNORECASE))

                    scan_done = False
                    scan_start = time.time()
                    already_cancelled = False
                    last_progress_str  = ""       # last seen "Processing ..(X/Y)" text
                    last_progress_time = time.time()  # when progress last changed

                    while True:
                        elapsed = time.time() - scan_start

                        # Hard timeout
                        if elapsed > HARD_TIMEOUT_SECS:
                            log(f"⚠️  Timed out waiting for scan ({HARD_TIMEOUT_SECS//60} mins).")
                            notify(f"⚠️ <b>{strategy}</b>: Scan timed out after {HARD_TIMEOUT_SECS//60} mins")
                            break

                        # ── Stuck detection: read current Processing text ──
                        current_progress_str = ""
                        try:
                            if await processing_text.first.is_visible():
                                current_progress_str = (await processing_text.first.text_content() or "").strip()
                        except Exception:
                            pass

                        if current_progress_str:
                            if current_progress_str != last_progress_str:
                                # Progress changed — reset stuck timer
                                last_progress_str  = current_progress_str
                                last_progress_time = time.time()
                            else:
                                # Same text — check if stuck
                                stuck_secs = time.time() - last_progress_time
                                if stuck_secs >= STUCK_THRESHOLD and not already_cancelled:
                                    log(f"🔒 Processing appears STUCK for {int(stuck_secs)}s "
                                        f"at: {current_progress_str} — cancelling & retrying...")
                                    notify(f"🔒 <b>{strategy}</b>: Scan stuck at '{current_progress_str}' "
                                           f"for {int(stuck_secs)}s — cancelling & retrying")
                                    try:
                                        await cancel_btn.first.click()
                                        await asyncio.sleep(2)
                                        await page2.get_by_role("button", name="Scan").click()
                                        log("Re-scan started after stuck cancel.")
                                        scan_start = time.time()
                                        last_progress_str  = ""
                                        last_progress_time = time.time()
                                        already_cancelled = True
                                    except Exception as e:
                                        log(f"Stuck cancel/rescan failed: {e}")
                                    continue

                        # ── Time-based cancel: 8 minutes ──
                        if elapsed > CANCEL_RETRY_SECS and not already_cancelled:
                            is_processing = False
                            try:
                                is_processing = await processing_text.first.is_visible()
                            except Exception:
                                pass
                            if is_processing:
                                log(f"⏳ Scan still processing after {CANCEL_RETRY_SECS//60} mins — cancelling & retrying...")
                                notify(f"⏳ <b>{strategy}</b>: Cancelling slow scan after {CANCEL_RETRY_SECS//60} min, retrying...")
                                try:
                                    await cancel_btn.first.click()
                                    await asyncio.sleep(2)
                                    await page2.get_by_role("button", name="Scan").click()
                                    log("Re-scan started after time-based cancel.")
                                    scan_start = time.time()
                                    last_progress_str  = ""
                                    last_progress_time = time.time()
                                    already_cancelled = True
                                except Exception as e:
                                    log(f"Cancel/rescan failed: {e}")
                                continue

                        # ── Check for validation filter popup ──
                        try:
                            if await validation_popup.first.is_visible():
                                log("⚠️  Validation Filter not qualified!")
                                filter_not_qualified = True

                                log("Closing popup...")
                                close_btn = page2.locator("xpath=/html/body/div[7]/div/table/tbody/tr[3]/td/div/table/tbody/tr/td/button")
                                try:
                                    await close_btn.wait_for(state="visible", timeout=3000)
                                    await close_btn.click()
                                except PlaywrightTimeout:
                                    await page2.get_by_role("button", name=re.compile(r"Close|OK", re.IGNORECASE)).first.click()
                                await asyncio.sleep(1)
                                log("Popup closed.")

                                log("Unchecking Market trend filter...")
                                market_filter_cb = page2.locator(
                                    "xpath=/html/body/div[4]/div[2]/div/div[2]/div[3]/div/div[3]"
                                    "/div/div/div[2]/div/table[1]/tbody/tr[1]/td[5]/table/tbody/tr/td[1]"
                                )
                                try:
                                    await market_filter_cb.wait_for(state="visible", timeout=3000)
                                    await market_filter_cb.click()
                                except PlaywrightTimeout:
                                    mf = page2.get_by_role("cell", name=re.compile(r"Market.*Filter|Market.*Trend", re.IGNORECASE)).locator("label, input, span").first
                                    await mf.click()
                                await asyncio.sleep(0.5)
                                log("Market trend filter unchecked ✅")
                                notify(f"⚠️ <b>{strategy}</b>: Filter not qualified — re-scanning without market filter")

                                log("Re-scanning without market filter...")
                                await page2.get_by_role("button", name="Scan").click()
                                log("Re-scan started...")
                                scan_start = time.time()
                                last_progress_str  = ""
                                last_progress_time = time.time()
                                continue
                        except Exception:
                            pass

                        # ── Check for "Qualified Scrips : 0" ──
                        try:
                            zero_scrips = page2.get_by_text(re.compile(r"Qualified Scrips\s*:\s*0", re.IGNORECASE))
                            if await zero_scrips.first.is_visible():
                                elapsed_s = int(time.time() - scan_start)
                                log(f"⚠️  Scan completed but 0 qualified scrips ({elapsed_s}s)")
                                no_qualified_scrips = True
                                scan_done = True
                                break
                        except Exception:
                            pass

                        # ── Check for scan complete (Export enabled OR "Scan Completed" text) ──
                        try:
                            if await export_btn.is_visible() and await export_btn.is_enabled():
                                elapsed_s = int(time.time() - scan_start)
                                log(f"✅ Scan completed! ({elapsed_s}s)")
                                scan_done = True
                                break
                        except Exception:
                            pass
                        try:
                            if await scan_completed_text.first.is_visible():
                                elapsed_s = int(time.time() - scan_start)
                                log(f"✅ 'Scan Completed' text detected ({elapsed_s}s)")
                                # Small wait for Export button to become enabled
                                await asyncio.sleep(1)
                                scan_done = True
                                break
                        except Exception:
                            pass

                        # ── Log processing status every 15s ──
                        if int(elapsed) % 15 == 0 and int(elapsed) > 0:
                            if current_progress_str:
                                log(f"⏳ {current_progress_str}  ({int(elapsed)}s elapsed)")
                            else:
                                try:
                                    is_proc = await processing_text.first.is_visible()
                                    if is_proc:
                                        log(f"⏳ Still processing... ({int(elapsed)}s elapsed)")
                                except Exception:
                                    pass

                        await asyncio.sleep(0.5)

                    await asyncio.sleep(1)

                    # 9e2. Post-scan check: Validation Filter popup may appear
                    #      at the same instant as "Scan Completed" / Export enabled.
                    #      Check again AFTER the loop exits, before trying to export.
                    try:
                        if await validation_popup.first.is_visible():
                            log("⚠️  Validation Filter popup detected (post-scan)!")
                            filter_not_qualified = True

                            # Close the popup
                            log("Closing popup...")
                            close_btn = page2.locator("xpath=/html/body/div[7]/div/table/tbody/tr[3]/td/div/table/tbody/tr/td/button")
                            closed = False
                            try:
                                await close_btn.wait_for(state="visible", timeout=3000)
                                await close_btn.click()
                                closed = True
                            except PlaywrightTimeout:
                                pass
                            if not closed:
                                try:
                                    await page2.get_by_role("button", name=re.compile(r"Close|OK", re.IGNORECASE)).first.click()
                                    closed = True
                                except Exception:
                                    pass
                            if not closed:
                                # Last resort: press Escape or click any visible button in the popup
                                try:
                                    await page2.keyboard.press("Escape")
                                except Exception:
                                    pass
                            await asyncio.sleep(1)
                            log("Popup closed.")

                            # Uncheck Market trend filter
                            log("Unchecking Market trend filter...")
                            market_filter_cb = page2.locator(
                                "xpath=/html/body/div[4]/div[2]/div/div[2]/div[3]/div/div[3]"
                                "/div/div/div[2]/div/table[1]/tbody/tr[1]/td[5]/table/tbody/tr/td[1]"
                            )
                            try:
                                await market_filter_cb.wait_for(state="visible", timeout=3000)
                                await market_filter_cb.click()
                            except PlaywrightTimeout:
                                try:
                                    mf = page2.get_by_role("cell", name=re.compile(r"Market.*Filter|Market.*Trend", re.IGNORECASE)).locator("label, input, span").first
                                    await mf.click()
                                except Exception:
                                    log("⚠️  Could not uncheck Market trend filter")
                            await asyncio.sleep(0.5)
                            log("Market trend filter unchecked ✅")
                            notify(f"⚠️ <b>{strategy}</b>: Filter not qualified — re-scanning without market filter")

                            # Re-scan
                            log("Re-scanning without market filter...")
                            await page2.get_by_role("button", name="Scan").click()
                            log("Re-scan started...")

                            # Wait for re-scan to complete (simpler wait — just Export enabled)
                            rescan_start = time.time()
                            while time.time() - rescan_start < HARD_TIMEOUT_SECS:
                                try:
                                    if await export_btn.is_visible() and await export_btn.is_enabled():
                                        log(f"✅ Re-scan completed! ({int(time.time()-rescan_start)}s)")
                                        scan_done = True
                                        break
                                except Exception:
                                    pass
                                try:
                                    zero_scrips = page2.get_by_text(re.compile(r"Qualified Scrips\s*:\s*0", re.IGNORECASE))
                                    if await zero_scrips.first.is_visible():
                                        log(f"⚠️  Re-scan: 0 qualified scrips ({int(time.time()-rescan_start)}s)")
                                        no_qualified_scrips = True
                                        scan_done = True
                                        break
                                except Exception:
                                    pass
                                await asyncio.sleep(0.5)
                            await asyncio.sleep(1)
                    except Exception as vf_err:
                        log(f"Post-scan validation check error (non-fatal): {vf_err}")

                    # 9f. Export / save file based on scan result
                    if scan_done and no_qualified_scrips:
                        filename  = f"{strategy}_{DATE_STR}_No_Qualified_Scrips.csv"
                        save_path = DOWNLOAD_DIR / filename
                        save_path.write_text("")
                        log(f"📄 Created empty file: {filename}")
                        notify(f"📄 <b>{strategy}</b>: 0 qualified scrips → {filename}")
                        tg_file(save_path, f"📄 <b>{strategy}</b> — 0 qualified scrips")
                        results.append(f"📄 {strategy} → {filename} (0 scrips)")

                    elif scan_done:
                        suffix = "_filter_not_qualified" if filter_not_qualified else ""
                        filename  = f"{strategy}_{DATE_STR}{suffix}.csv"
                        save_path = DOWNLOAD_DIR / filename
                        log(f"Clicking Export → saving as: {filename}")
                        try:
                            async with page2.expect_download(timeout=60000) as dl_info:
                                await page2.get_by_role("button", name="Export").click()
                            download = await dl_info.value
                            await download.save_as(save_path)
                            log(f"✅ File saved: {save_path}")
                            notify(f"✅ <b>{strategy}</b>: Saved as {filename}")
                            tg_file(save_path, f"✅ <b>{strategy}</b>")
                            results.append(f"✅ {strategy} → {filename}")
                        except PlaywrightTimeout:
                            log(f"⚠️  Download not captured for {strategy}.")
                            notify(f"⚠️ <b>{strategy}</b>: Download failed")
                            results.append(f"⚠️ {strategy} → download failed")

                    else:
                        log(f"⏭️  Skipping export for {strategy} — scan did not complete.")
                        notify(f"❌ <b>{strategy}</b>: Scan did not complete, skipped export")
                        results.append(f"❌ {strategy} → scan timed out")

                    # Strategy succeeded — break out of retry loop
                    break

                except Exception as e:
                    log(f"❌ Error on attempt {attempt}/{MAX_ATTEMPTS} for {strategy}: {e}")
                    if attempt < MAX_ATTEMPTS:
                        log(f"⏳ Waiting 5s before retry...")
                        notify(f"⚠️ <b>{strategy}</b>: Error on attempt {attempt}, retrying...")
                        await asyncio.sleep(5)
                    else:
                        log(f"❌ All {MAX_ATTEMPTS} attempts failed for {strategy}.")
                        notify(f"❌ <b>{strategy}</b>: Failed after {MAX_ATTEMPTS} attempts — {e}")
                        results.append(f"❌ {strategy} → error: {e}")

            log(f"Strategy '{strategy}' done.\n")
            await asyncio.sleep(2)


        # ── ALL DONE ─────────────────────────────────────────────────────────
        separator("ALL STRATEGIES COMPLETE ✅")
        log(f"Processed : {len(STRATEGIES)} strategies")
        log(f"Saved to  : {DOWNLOAD_DIR}")

        # Final summary
        summary = "\n".join(results)
        log(f"\nResults:\n{summary}")
        tg(f"🏁 <b>RZ Scanner Complete</b>\n\n"
           + "\n".join(results)
           + f"\n\n📁 Saved to: {DOWNLOAD_DIR}")

        log("Closing browser in 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run())
