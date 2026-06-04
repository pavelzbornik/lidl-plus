"""Step 1 of manual-browser token capture: generate the login URL + keep PKCE verifier.

Prints the OAuth login URL and stashes the matching code_verifier (in the repo
root as .lidl_pkce.json) so step 2 (exchange_code.py) can trade the returned auth
code for a refresh token.

    python scripts/get_login_url.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from lidlplus import LidlPlusApi

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

api = LidlPlusApi(os.environ["LIDL_LANGUAGE"], os.environ["LIDL_COUNTRY"])
url = api._register_link  # generates code_challenge + sets api._code_verifier

(ROOT / ".lidl_pkce.json").write_text(json.dumps({"verifier": api._code_verifier}), encoding="utf-8")

print(url)
