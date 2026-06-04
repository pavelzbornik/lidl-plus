# Lidl Plus Authentication

> See also: [api-endpoints.md](api-endpoints.md) — what the API exposes and how much the package maps.

How to obtain and maintain credentials for this package. Two paths exist:

1. **Refresh token (recommended)** — headless, no browser, no CAPTCHA. Use this for all normal/automated runs.
2. **Fresh login** — needed only to *mint* a refresh token the first time (or when one dies). Lidl's anti-bot blocks fully-automated login, so this is done through a **real browser**.

---

## Background: how auth works

The API is OAuth2 with PKCE. A long-lived **refresh token** is exchanged for a short-lived
**access token** (a JWT, ~1 h) on every request:

```
refresh_token  --(POST /connect/token)-->  access_token (JWT)  -->  receipts / coupons / ...
```

`LidlPlusApi._default_headers()` auto-renews the access token whenever it's missing or expired,
and **Lidl rotates the refresh token on each renewal** — so a persisted refresh token can live
indefinitely.

### `.env` keys

Copy [`.env.example`](../.env.example) to `.env` and fill in your values (`.env` is gitignored):

```env
LIDL_LANGUAGE=fr
LIDL_COUNTRY=FR
LIDL_EMAIL=you@example.com
LIDL_PASSWORD=your_password
LIDLPLUS_TOKEN=<refresh token>      # NOTE: this is the REFRESH token (64-char hex), not an access token
```

> ⚠️ `LIDLPLUS_TOKEN` holds the **refresh token** (a 64-char hex string), not a bearer/access
> token. Feed it to `LidlPlusApi(language, country, refresh_token=...)`.

---

## Path 1 — Use & keep the refresh token alive (recommended)

Fully headless. No browser, no reCAPTCHA, no 2FA.

```python
import os
from dotenv import load_dotenv
from lidlplus import LidlPlusApi

load_dotenv()
lidl = LidlPlusApi(os.environ["LIDL_LANGUAGE"], os.environ["LIDL_COUNTRY"],
                   refresh_token=os.environ["LIDLPLUS_TOKEN"])
for t in lidl.tickets():
    print(lidl.ticket(t["id"]))
```

Because Lidl rotates the refresh token, **persist the rotated value** so it never expires. Run
[`scripts/refresh_keepalive.py`](../scripts/refresh_keepalive.py) periodically (or before each job):

```bash
python scripts/refresh_keepalive.py
```

It renews the token, writes any rotation back to `.env`, and confirms receipt access.

---

## Path 2 — Mint a fresh refresh token via a real browser

Use this once to bootstrap a token, or whenever the refresh token dies.

### Why not automated?

The login form is protected by **reCAPTCHA Enterprise** (invisible, score-based). Automated
browsers (Selenium — headless *or* visible, with or without a proxy) get a low trust score and
are silently soft-blocked with a red banner:

> *"Nous sommes en surcapacité — Veuillez patienter quelques instants et réessayer."*

This is **not** a real outage and **not** a bug in the package — it is bot-detection. A genuine
human browser passes it. Do **not** try to defeat the CAPTCHA.

### Prerequisites

- `.env` populated with `LIDL_EMAIL`, `LIDL_PASSWORD`, `LIDL_COUNTRY`, `LIDL_LANGUAGE`.
- Your normal Chrome browser.

### Steps

**1. Generate the login URL (and stash the PKCE verifier).**

```bash
python scripts/get_login_url.py
```

This prints an `https://accounts.lidl.com/connect/authorize?...` URL and writes the matching
`code_verifier` to `.lidl_pkce.json`. The verifier **must** pair with this exact URL for the final
exchange, so don't regenerate between steps.

**2. Log in through your real browser.**

Open the printed URL in Chrome and:

- Click **S'identifier**, enter your **email + password**, submit.
- Complete **2FA** if prompted (a trusted session may skip it).
- Accept the **updated Terms & Conditions** if shown ("Accepter").
- Solve a reCAPTCHA challenge if one appears (you're human — it passes).

The flow ends by redirecting to a custom scheme the browser can't open:

```
com.lidlplus.app://callback?code=<HEX_CODE>&scope=...&session_state=...
```

This "can't open page / no app" result **is success**. Copy the `code=<HEX_CODE>` value from the
address bar (or the error text).

> **Capturing the code reliably.** Because the redirect target is a non-`http` scheme, the browser
> may bounce/clear its logs. A robust capture is to load the authorize URL inside a **hidden iframe
> on an `accounts.lidl.com` page** (keeps SameSite session cookies and keeps the tab on-domain);
> the resulting `com.lidlplus.app://callback?code=...` URL is then readable from the tab/devtools
> without navigating away. The `code` is a hex string.

**3. Exchange the code for a refresh token (do this within ~60 s — codes expire fast).**

```bash
python scripts/exchange_code.py <HEX_CODE>
```

This reads the stashed verifier, calls `/connect/token` with
`grant_type=authorization_code`, prints the new refresh token, writes it to `.env` as
`LIDLPLUS_TOKEN`, confirms receipt access, and deletes `.lidl_pkce.json`.

From here on, use **Path 1** — you won't need the browser again until the token is invalidated.

---

## Security notes

- **Never** let an automated agent type your password into the login form; you enter it yourself
  in your own browser.
- `.env` and `.lidl_pkce.json` contain secrets — keep them out of version control
  (add to `.gitignore`).
- Authorization codes are single-use and expire in ~60 seconds.

---

## CLI equivalent

The package also exposes the Selenium login via the CLI (subject to the same reCAPTCHA limitation):

```bash
lidl-plus auth                 # prints a refresh token (auto-loads .env, prompts for 2FA)
lidl-plus -d auth              # visible browser (debug) — more likely to pass reCAPTCHA than headless
lidl-plus -r <TOKEN> receipt --all > data.json
```

---

## Related package fixes

These were required to make the above work against the current Lidl backend (`lidlplus/api.py`):

| Fix | Why |
| --- | --- |
| `_APP_VERSION` replaces the `999.99.9` sentinel | Lidl now tarpits requests with an implausible `App-Version`; receipts requests would hang until timeout. |
| Password selector `login-input-password` (was `input-password`) | Lidl renamed the field's `data-testid`; Selenium login could never fill the password. |
| Selenium Manager for the driver (was `webdriver_manager`) | Avoids a slow/hanging driver download and wrong-arch binaries; browser starts in ~1 s. |
