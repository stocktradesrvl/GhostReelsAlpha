# RevenueCat — integrated (2026-06)
This file is a memory to interact with the user's RevenueCat account via the integration proxy later.

## Identifiers (from /setup response — copy verbatim)
- rc_project_id: proja26f3c2c
- apple_app_id: app6b5bbdae75
- play_app_id: app358f82c0fd
- entitlement_lookup_key: pro
- offering_lookup_key: default
- Packages (package -> product_id, current price):
  - $rc_monthly -> proddd66b26b4f   ($9.99 / P1M, trial: P1W — 7-day free trial)
  - $rc_annual  -> prod4a33ab21a8   ($79.99 / P1Y, trial: none)
- Dashboard: https://app.revenuecat.com/projects/proja26f3c2c
- bundle_id / package_name: com.emergent.mobiledev.swa3k5

## Status check
AUTH='Authorization: Bearer <emergent key>'
curl -sS -H "$AUTH" "$INTEGRATION_PROXY_URL/internal/revenuecat/projects/faea29eb-b938-4a57-8691-9a17e7c89c9d/status"

## Later updates to products (integration proxy APIs ONLY — NEVER call RevenueCat REST API)
- Change price/duration/trial OR add a package (upsert):
  POST $INTEGRATION_PROXY_URL/internal/revenuecat/projects/faea29eb-b938-4a57-8691-9a17e7c89c9d/products
  body: {"products":[{"package":"$rc_monthly","price":14.99,"currency":"USD","period":"P1M","trial":"P1W","prices":[{"amount_micros":14990000,"currency":"USD"}]}]}
  (amount_micros = price × 1,000,000; omit "trial" for none)
- Remove a package:
  DELETE $INTEGRATION_PROXY_URL/internal/revenuecat/projects/faea29eb-b938-4a57-8691-9a17e7c89c9d/products/%24rc_monthly

## Taking IAP live — store-side steps (USER does these; needed only for real store builds)
All steps are in the FAQ section of the payments panel. Test Store (Expo Go / web / dev build) needs none of this.

## App-specific note
This app has a server-enforced free-reel quota (3 free reels on the shared Emergent pool).
Subscribers get unlimited generation on that shared pool, so the BACKEND must know subscription
status. Frontend syncs the SDK-verified `pro` entitlement to the backend after logIn / on
customer-info updates (POST /api/subscription/sync). Backend `users.is_subscribed` bypasses the quota.
