---
name: checkout-skill
appliesTo: [checkout]
description: How to handle the checkout/order-placement flow safely.
---
- checkout is high-risk and requires explicit confirmation. Never call it on the first mention of "checkout" or "buy it now" — resolve to "confirm" first and let the user explicitly say yes.
- If the session is not authenticated, do not attempt to bypass login; let NINA's existing auth-replay flow handle it.
- After checkout succeeds, state the order reference/confirmation number exactly as returned by the action. Never fabricate one if the result does not include it.
