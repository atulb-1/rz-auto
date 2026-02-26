"""
Definedge RZone — Login Only (up to I Agree)
=============================================
Automates login, OTP, navigates to RZone, clicks I Agree, then hands control to you.
Browser stays open until you close this script.

Setup:
    pip install playwright pyotp requests
    playwright install chromium

Usage:
    python rzone_login_only.py
"""

import asyncio
import configparser
import pyotp
import re
import sys
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


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
async def run():
    separator("Definedge RZone — Login Only")
    log("This script logs in and opens RZone, then you take over.")

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
        separator("STEP 1: Opening Definedge Home Page")
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
            log("ERROR: Could not open login page after 3 attempts.")
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


        # ── STEP 5: Wait for MyAccount ───────────────────────────────────────
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


        # ── STEP 6: Analyse & Trade → Opens RZone popup ──────────────────────
        separator("STEP 6: RZone → Analyse & Trade")
        log("Clicking Analyse & Trade button...")
        async with page1.expect_popup() as page2_info:
            await analyse_btn.click()
        page2 = await page2_info.value
        log(f"RZone popup captured →  {page2.url}")

        # RZone SPA does client-side redirects — wait for page to stabilize
        log("Waiting for RZone page to settle...")
        for attempt in range(30):  # up to 15 seconds
            try:
                await page2.wait_for_load_state("domcontentloaded", timeout=5000)
                await asyncio.sleep(1)
                body_len = await page2.evaluate("document.body ? document.body.innerText.length : 0")
                if body_len > 100:
                    break
            except Exception as e:
                log(f"Page still loading/navigating... ({type(e).__name__})")
                await asyncio.sleep(1)

        await page2.bring_to_front()
        await asyncio.sleep(1)
        log(f"RZone page ready ✅  →  {page2.url}")


        # ── STEP 7: I Agree ──────────────────────────────────────────────────
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

            # Also check inside iframes at ~10s mark
            if tick == 20:
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


        # ── DONE — Hand over to user ─────────────────────────────────────────
        separator("ALL DONE — Browser is yours!")
        log("✅ Logged in, RZone open, I Agree handled.")
        log("The browser will stay open. Do your work manually.")
        log("")
        log("Press ENTER in this window when you're done to close the browser.")
        input("  >>> Press ENTER to close... ")
        await browser.close()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run())
