"""
Builds config.ini from environment variables (for GitHub Actions / CI).
Reads secrets from env vars and writes a config.ini in the project root.

Required env vars:
    RZONE_UCC          - Definedge UCC
    RZONE_PASSWORD     - Definedge password
    RZONE_TOTP_SECRET  - TOTP secret key (Base32)
    RZONE_STRATEGIES   - Comma-separated strategy names

Optional env vars:
    RZONE_LOGIN_URL    - Login URL (has default)
    RZONE_DOWNLOAD_DIR - Download folder (defaults to ./downloads)
    RZONE_TG_BOT_TOKEN - Telegram bot token
    RZONE_TG_CHAT_ID   - Telegram chat ID
"""

import os
import sys
from pathlib import Path


def main():
    ucc         = os.environ.get("RZONE_UCC", "").strip()
    password    = os.environ.get("RZONE_PASSWORD", "").strip()
    totp_secret = os.environ.get("RZONE_TOTP_SECRET", "").strip()
    strategies  = os.environ.get("RZONE_STRATEGIES", "").strip()

    if not all([ucc, password, totp_secret, strategies]):
        print("ERROR: Missing required environment variables.")
        print("  Required: RZONE_UCC, RZONE_PASSWORD, RZONE_TOTP_SECRET, RZONE_STRATEGIES")
        missing = []
        if not ucc:         missing.append("RZONE_UCC")
        if not password:    missing.append("RZONE_PASSWORD")
        if not totp_secret: missing.append("RZONE_TOTP_SECRET")
        if not strategies:  missing.append("RZONE_STRATEGIES")
        print(f"  Missing: {', '.join(missing)}")
        sys.exit(1)

    login_url    = os.environ.get("RZONE_LOGIN_URL", (
        "https://signin.definedgesecurities.com/auth/realms/debroking/"
        "protocol/openid-connect/auth?response_type=code&client_id=dashboard"
        "&redirect_uri=https://myaccount.definedgesecurities.com/ssologin"
        "&state=e2cf559f-356c-425a-87e3-032097f643d0&login=true&scope=openid"
    )).strip()
    download_dir = os.environ.get("RZONE_DOWNLOAD_DIR", "./downloads").strip()
    tg_token     = os.environ.get("RZONE_TG_BOT_TOKEN", "").strip()
    tg_chat_id   = os.environ.get("RZONE_TG_CHAT_ID", "").strip()

    # Format strategies: comma-separated → one per line with indentation
    strat_list = [s.strip() for s in strategies.split(",") if s.strip()]
    strat_lines = "\n".join(f"\t{s}" for s in strat_list)

    config_content = f"""[CREDENTIALS]
URL = {login_url}
UCC      = {ucc}
PASSWORD = {password}
TOTP_SECRET = {totp_secret}

[SETTINGS]
DOWNLOAD_DIR = {download_dir}

[STRATEGIES]
LIST =
{strat_lines}

[TELEGRAM]
BOT_TOKEN = {tg_token}
CHAT_ID = {tg_chat_id}
"""

    config_path = Path(__file__).parent.parent / "config.ini"
    config_path.write_text(config_content)
    print(f"config.ini written to {config_path}")
    print(f"  UCC: {ucc}")
    print(f"  Strategies: {len(strat_list)} — {strat_list}")
    print(f"  Download dir: {download_dir}")
    print(f"  Telegram: {'Enabled' if tg_token and tg_chat_id else 'Disabled'}")


if __name__ == "__main__":
    main()
