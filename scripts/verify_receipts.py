"""Verify the lidlplus package can authenticate and retrieve receipts.

Uses the refresh token stored in .env (LIDLPLUS_TOKEN) to exercise the real
package code path: refresh-token -> access-token -> tickets() -> ticket(id).

    python scripts/verify_receipts.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from lidlplus import LidlPlusApi

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

language = os.environ.get("LIDL_LANGUAGE", "de")
country = os.environ.get("LIDL_COUNTRY", "DE")
refresh_token = os.environ["LIDLPLUS_TOKEN"]

print(f"[1] Creating LidlPlusApi(language={language!r}, country={country!r})")
lidl = LidlPlusApi(language, country, refresh_token=refresh_token)

print("[2] Exchanging refresh token for access token...")
tickets = lidl.tickets()
print(f"    OK - token renewed. New refresh token suffix: ...{lidl.refresh_token[-6:]}")

print(f"[3] Retrieved {len(tickets)} ticket(s) in the list.")
if not tickets:
    print("    No tickets on this account; nothing more to fetch.")
    raise SystemExit(0)

newest = tickets[0]
print(f"    Newest ticket id={newest.get('id')} date={newest.get('date')} " f"total={newest.get('totalAmount')}")

print(f"[4] Fetching full detail of newest ticket {newest['id']} (HTML -> parsed)...")
detail = lidl.ticket(newest["id"])
items = detail.get("itemsLine", []) if isinstance(detail, dict) else []
print(f"    OK - parsed receipt with {len(items)} line item(s).")
for item in items[:5]:
    print(f"      - {item.get('name')!r}  qty={item.get('quantity')}  " f"price={item.get('originalAmount')}")

print("\n[RESULT] Package works: authenticated and retrieved receipts successfully.")
