"""
Builds config.ini from environment variables (for GitHub Actions / CI).
Reads secrets from env vars and writes a config.ini in the project root.

Required env vars:
    RZ_UCC          - DefineE UCC
    RZ_PASSWORD     - DefineE password
    RZ_TOTP_SECRET  - TOTP secret key (Base32)
    RZ_STRATEGIES   - Comma-separated strategy names

Optional env vars:
    RZ_LOGIN_URL    - Login URL (required if not hardcoded in config_sample.ini)
    RZ_DOWNLOAD_DIR - Download folder (defaults to ./downloads)
    RZ_TG_BOT_TOKEN - Telegram bot token
    RZ_TG_CHAT_ID   - Telegram chat ID
"""

import os
import sys
from pathlib import Path


def main():
    ucc         = os.environ.get("RZ_UCC", "").strip()
    password    = os.environ.get("RZ_PASSWORD", "").strip()
    totp_secret = os.environ.get("RZ_TOTP_SECRET", "").strip()
    strategies  = os.environ.get("RZ_STRATEGIES", "").strip()

    if not all([ucc, password, totp_secret, strategies]):
        print("ERROR: Missing required environment variables.")
        print("  Required: RZ_UCC, RZ_PASSWORD, RZ_TOTP_SECRET, RZ_STRATEGIES")
        missing = []
        if not ucc:         missing.append("RZ_UCC")
        if not password:    missing.append("RZ_PASSWORD")
        if not totp_secret: missing.append("RZ_TOTP_SECRET")
        if not strategies:  missing.append("RZ_STRATEGIES")
        print(f"  Missing: {', '.join(missing)}")
        sys.exit(1)

    login_url    = os.environ.get("RZ_LOGIN_URL", "").strip()
    if not login_url:
        print("ERROR: RZ_LOGIN_URL env var is not set. Add it as a GitHub secret.")
        sys.exit(1)

    download_dir = os.environ.get("RZ_DOWNLOAD_DIR", "./downloads").strip()
    tg_token     = os.environ.get("RZ_TG_BOT_TOKEN", "").strip()
    tg_chat_id   = os.environ.get("RZ_TG_CHAT_ID", "").strip()

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
