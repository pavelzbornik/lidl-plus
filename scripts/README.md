# scripts/

Helper utilities for authenticating and pulling data with this package. All read
credentials from a `.env` file in the repo root (see
[`docs/authentication.md`](../docs/authentication.md)). Run them from the repo root:

| Script | Purpose |
| --- | --- |
| `refresh_keepalive.py` | Renew the refresh token and persist the rotated value to `.env`. Fully headless — your day-to-day keep-alive. |
| `verify_receipts.py` | Sanity check: authenticate with the current token and fetch receipts. |
| `get_login_url.py` | Mint a new token, step 1: print the OAuth login URL and stash the PKCE verifier. |
| `exchange_code.py` | Mint a new token, step 2: exchange the auth code (`python scripts/exchange_code.py <CODE>`) for a refresh token and save it to `.env`. |

`get_login_url.py` + `exchange_code.py` implement the manual real-browser login flow
(needed because Lidl's reCAPTCHA Enterprise blocks automated logins). The full
procedure is documented in [`docs/authentication.md`](../docs/authentication.md).
