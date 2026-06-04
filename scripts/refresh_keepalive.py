"""Keep the Lidl refresh token alive — fully headless, no browser, no reCAPTCHA.

Lidl rotates the refresh token on every renewal. This renews it and writes the
NEW token back to .env so the next run keeps working. Run it periodically (or
before each receipts job) and you never need a browser login again.

    python scripts/refresh_keepalive.py
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from lidlplus import LidlPlusApi

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)

old_token = os.environ["LIDLPLUS_TOKEN"]
lidl = LidlPlusApi(os.environ["LIDL_LANGUAGE"], os.environ["LIDL_COUNTRY"], refresh_token=old_token)

print("Renewing access token (rotates the refresh token)...")
lidl._renew_token()
new_token = lidl.refresh_token

if new_token and new_token != old_token:
    text = ENV_PATH.read_text(encoding="utf-8")
    text = re.sub(r"^LIDLPLUS_TOKEN=.*$", f"LIDLPLUS_TOKEN={new_token}",
                  text, count=1, flags=re.MULTILINE)
    ENV_PATH.write_text(text, encoding="utf-8")
    print(f"[OK] Refresh token rotated and saved to .env (...{new_token[-6:]}).")
else:
    print("[OK] Token still valid; no rotation needed.")

# Prove the session works headlessly.
count = len(lidl.tickets())
print(f"[OK] Headless access confirmed: {count} receipt(s) reachable.")
