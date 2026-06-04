# Lidl Plus API — endpoint map

A reverse-engineered map of the Lidl Plus HTTP API and how much of it this package covers.

> **Caveat:** This API is undocumented and reverse-engineered. Hosts, paths, and versions
> change without notice. The "Status" columns below were probed **live with a valid token,
> country `FR`, June 2026** (GET endpoints only — mutating calls were not fired). Treat them as
> a snapshot, not a contract.

All authenticated requests carry these headers (see `LidlPlusApi._default_headers`):

```
Authorization: Bearer <access_token>
App-Version: 15.30.0          # must be a realistic version — the API tarpits "999.99.9"
Operating-System: iOs
App: com.lidl.eci.lidl.plus
Accept-Language: <language>
```

Some endpoints additionally require a `Country: <CC>` header (noted below). The **public**
endpoints (`stores`, `countries`) take no token but reject requests without a Lidl Plus
`User-Agent` (e.g. `LidlPlus/16.0.0 (iPhone; iOS 17.0; Scale/3.00)`).

---

## Authentication — `accounts.lidl.com`

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/connect/authorize` | Start OAuth2 + PKCE login (browser flow). |
| POST | `/connect/token` | Exchange `authorization_code` or `refresh_token` for an access token. |
| GET | `/connect/userinfo` | OpenID Connect profile claims (`name`, `email`, `sub`, …). |

See [authentication.md](authentication.md) for the full flow.

---

## Implemented in this package (`lidlplus/api.py`)

| Method | Endpoint | Package method | Status (FR, Jun 2026) |
| --- | --- | --- | --- |
| GET | `tickets.lidlplus.com/api/v2/{CC}/tickets?pageNumber=N&onlyFavorite=` | `tickets()` | ✅ 200 |
| GET | `tickets.lidlplus.com/api/v3/{CC}/tickets/{id}` | `ticket(id)` | ✅ 200 (HTML receipt) |
| GET | `coupons.lidlplus.com/app/api/v1/promotionslist` *(needs `Country` header)* | `coupons()` and `coupon_promotions_v1()` | ✅ 200 |
| POST | `coupons.lidlplus.com/app/api/v1/promotions/{id}/activation` *(`Country` header)* | `activate_coupon(id)` and `activate_coupon_promotion_v1(id)` | mutating — not probed |
| DELETE | `coupons.lidlplus.com/app/api/v1/promotions/{id}/activation` *(`Country` header)* | `deactivate_coupon(id)` | mutating — not probed |
| GET | `profile.lidlplus.com/api/v1/{CC}/loyalty` | `loyalty_id()` | ✅ 200 (plain-text card id) |
| GET | `accounts.lidl.com/connect/userinfo` | `user_info()` | ✅ 200 |
| GET | `stores.lidlplus.com/api/v4/{CC}` *(no auth; `User-Agent` only)* | `stores()` | ✅ 200 (1642 FR stores) |
| GET | `appgateway.lidlplus.com/configurationapp/v3/countries` *(no auth; `User-Agent`)* | `countries()` | ✅ 200 (32 countries) |

> The legacy v2 coupon endpoints (`coupons.lidlplus.com/api/v2/{CC}` and
> `…/api/v1/{CC}/{id}/activation`) were retired by Lidl (404). `coupons()`,
> `activate_coupon()`, and `deactivate_coupon()` were **repointed to the live V1
> promotions API**, so they share endpoints with their `*_v1` counterparts. (The app's
> current version is **v3** — `…/app/api/v3/promotionslist` + `…/v2/promotions/{id}/activation`
> — which also works; v1 is kept for now.)
>
> `loyalty_id()` lives at `profile.lidlplus.com/**api**/v1/{CC}/loyalty` — the package
> previously used a wrong `…/**profile**/api/v1/…` path that 404'd. The host is alive.

### Takeaways

- **Core receipts work.** `tickets()` + `ticket()` are healthy — the package's main feature is fine.
- **Coupons now work.** The live coupon surface is the **V1 promotions** API
  (`/app/api/v1/promotionslist` + `/promotions/{id}/activation`). The legacy v2 endpoints were
  retired (404); `coupons()` / `activate_coupon()` / `deactivate_coupon()` have been repointed to
  V1 and the CLI `coupon` command was consolidated onto the single working path.
- **Loyalty works again** — the host was never dead; the package just had a wrong path
  (`/profile/api/v1/…` instead of `/api/v1/…`). `loyalty_id()` now returns the real plain-text
  loyalty card id. A new `user_info()` additionally exposes the OIDC profile claims.
- **Stores & countries added.** `stores()` (`stores.lidlplus.com/api/v4/{CC}`) and `countries()`
  (`appgateway.lidlplus.com/configurationapp/v3/countries`) are **public** (no token) — they only
  need a Lidl Plus `User-Agent` header. Discovered from the
  [LittleMinus](https://github.com/Philipp0002/LittleMinus) Android client source.

---

## Known endpoints NOT mapped by this package

Gathered from sibling clients ([LittleMinus](https://github.com/Philipp0002/LittleMinus) — an
*open-source Android* client, the most current source —
[bluewalk/lidlplus-dotnet-client](https://github.com/bluewalk/lidlplus-dotnet-client),
[KoenZomers/LidlApi](https://github.com/KoenZomers/LidlApi),
[Andre0512/lidl-plus](https://github.com/Andre0512/lidl-plus)) and probed for current reachability:

| Feature | Candidate endpoint | Status (FR, Jun 2026) |
| --- | --- | --- |
| Mark receipt favourite | `POST tickets.lidlplus.com/api/v1/{CC}/tickets/{id}/favorite` | not mapped (note: list call already supports `onlyFavorite`) |
| Scratch coupons / redeem | `coupons.lidlplus.com/api/v1/{CC}/scratch`, `/scratchcoupons/{id}/redeem` | 404 on probed paths |
| Alerts / messages | `content.lidlplus.com/v1/{CC}/alerts` | ⚠️ host unresolvable |
| Lidl Pay / payments | `payments.lidlplus.com/...` | 404 / not available |

### Takeaways

- Mining the **LittleMinus** source corrected three "dead" endpoints into wrong-path/header
  mistakes: **loyalty** (wrong path), **stores** (moved to a dedicated `stores.lidlplus.com` host),
  and **countries** (a different `appgateway` path). The 404→401→200 progression while probing was
  the tell.
- The hosts still genuinely missing — **alerts** (`content.lidlplus.com`, DNS failure) and
  **Lidl Pay** (`payments.lidlplus.com`) — are not referenced by LittleMinus either, so they'd
  need fresh app-traffic capture to rediscover.
- **Live surface now covered:** `tickets`, `coupons`, `profile/loyalty`, `stores`, plus public
  `countries` and OIDC `userinfo`.

---

## Suggested follow-ups

- ✅ Done: repointed `coupons()` / `activate_coupon()` / `deactivate_coupon()` to the live V1
  promotions API and consolidated the CLI `coupon` command.
- ✅ Done: fixed `loyalty_id()` (corrected path → real card id), added `user_info()`, and added
  `stores()` + `countries()` (discovered from the LittleMinus source).
- Optional: bump coupons to **v3** (`/app/api/v3/promotionslist` + `/v2/.../activation`) to match
  the current app; v1 still works.
- Alerts and Lidl Pay would need fresh app-traffic capture to rediscover their current hosts.
