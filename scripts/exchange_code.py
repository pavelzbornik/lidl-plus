"""Step 2 of manual-browser token capture: exchange the auth code for a token.

    python scripts/exchange_code.py <CODE>

Reads the PKCE verifier stashed by get_login_url.py, exchanges the code for a
refresh token, persists it to .env (LIDLPLUS_TOKEN), and confirms receipt access.
Authorization codes expire in ~60 seconds, so run this promptly.
"""
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from lidlplus import LidlPlusApi

ROOT = Path(__file__).resolve().parent.parent
code = sys.argv[1]
env_path = ROOT / ".env"
load_dotenv(env_path)

verifier = json.loads((ROOT / ".lidl_pkce.json").read_text(encoding="utf-8"))["verifier"]

api = LidlPlusApi(os.environ["LIDL_LANGUAGE"], os.environ["LIDL_COUNTRY"])
api._code_verifier = verifier
api._authorization_code(code)  # POST /connect/token grant_type=authorization_code

token = api.refresh_token
print(f"[OK] Got refresh token (...{token[-6:]}).")

text = env_path.read_text(encoding="utf-8")
if re.search(r"^LIDLPLUS_TOKEN=", text, flags=re.MULTILINE):
    text = re.sub(r"^LIDLPLUS_TOKEN=.*$", f"LIDLPLUS_TOKEN={token}", text, count=1, flags=re.MULTILINE)
else:
    text = text.rstrip("\n") + f"\nLIDLPLUS_TOKEN={token}\n"
env_path.write_text(text, encoding="utf-8")
print("[OK] Saved to .env as LIDLPLUS_TOKEN.")

print(f"[OK] Headless access confirmed: {len(api.tickets())} receipt(s).")
(ROOT / ".lidl_pkce.json").unlink(missing_ok=True)
