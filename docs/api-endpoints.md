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

Some endpoints additionally require a `Country: <CC>` header (noted below).

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
| GET | `accounts.lidl.com/connect/userinfo` | `user_info()`; `loyalty_id()` (returns the `sub` claim) | ✅ 200 |

> The legacy v2 coupon endpoints (`coupons.lidlplus.com/api/v2/{CC}` and
> `…/api/v1/{CC}/{id}/activation`) were retired by Lidl (404). `coupons()`,
> `activate_coupon()`, and `deactivate_coupon()` were **repointed to the live V1
> promotions API**, so they share endpoints with their `*_v1` counterparts.

### Takeaways

- **Core receipts work.** `tickets()` + `ticket()` are healthy — the package's main feature is fine.
- **Coupons now work.** The live coupon surface is the **V1 promotions** API
  (`/app/api/v1/promotionslist` + `/promotions/{id}/activation`). The legacy v2 endpoints were
  retired (404); `coupons()` / `activate_coupon()` / `deactivate_coupon()` have been repointed to
  V1 and the CLI `coupon` command was consolidated onto the single working path.
- **Loyalty/profile moved to OIDC.** The whole `profile.lidlplus.com` host was retired (every
  path returns nginx 404). `loyalty_id()` was repointed to the `sub` claim from
  `accounts.lidl.com/connect/userinfo`, and a new `user_info()` exposes the full profile claims.
  Caveat: `sub` is the stable account identifier, *not* the legacy scannable loyalty-card number —
  that number is no longer exposed by any reachable endpoint.

---

## Known endpoints NOT mapped by this package

Gathered from sibling clients ([bluewalk/lidlplus-dotnet-client](https://github.com/bluewalk/lidlplus-dotnet-client),
[KoenZomers/LidlApi](https://github.com/KoenZomers/LidlApi), [Andre0512/lidl-plus](https://github.com/Andre0512/lidl-plus))
and probed for current reachability:

| Feature | Candidate endpoint | Status (FR, Jun 2026) |
| --- | --- | --- |
| Mark receipt favourite | `POST tickets.lidlplus.com/api/v1/{CC}/tickets/{id}/favorite` | not mapped (note: list call already supports `onlyFavorite`) |
| Stores list / detail | `appgateway.lidlplus.com/stores/v2/{CC}`, `/app/v15/{CC}/stores` | ⚠️ 502 — host unhealthy/retired |
| Profile details | `appgateway.lidlplus.com/app/v1/{CC}/profile` | ⚠️ 502 |
| Scratch coupons / redeem | `coupons.lidlplus.com/api/v1/{CC}/scratch`, `/scratchcoupons/{id}/redeem` | 404 on probed paths |
| Alerts / messages | `content.lidlplus.com/v1/{CC}/alerts` | ⚠️ host unresolvable |
| Lidl Pay / payments | `payments.lidlplus.com/...` | 404 / not available |
| Digital loyalty card | `profile.lidlplus.com/profile/api/v1/{CC}/card` | 404 |

### Takeaways

- The hosts other clients used for **stores** (`appgateway.lidlplus.com`) and **alerts**
  (`content.lidlplus.com`) are currently **down or relocated** (502 / DNS failure), which is
  consistent with those .NET clients being archived as "no longer working." Mapping these would
  require rediscovering the current hosts/paths via app traffic capture.
- The **practical live surface today is just two hosts**: `tickets.lidlplus.com` (receipts) and
  `coupons.lidlplus.com` (coupon promotions). Everything the package needs for its headline
  features lives there and works.

---

## Suggested follow-ups

- ✅ Done: repointed `coupons()` / `activate_coupon()` / `deactivate_coupon()` to the live V1
  promotions API and consolidated the CLI `coupon` command.
- ✅ Done: `loyalty_id()` repointed to the OIDC `sub` claim; added `user_info()`.
- Stores/alerts/Lidl-Pay would need fresh reverse engineering before they could be added.
