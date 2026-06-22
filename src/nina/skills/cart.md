---
name: cart-skill
appliesTo: [add_to_cart]
description: How to resolve which variantId to add to cart from prior search or product context.
---
- add_to_cart takes a variantId, never a product name, URL, or slug. The ONLY valid source for variantId is the `id` field on an entry in `last_search_results` from the REFERENCE MAP section. Never derive variantId from a productUrl, a navigation slug, or by reformatting the product's title/name — those are display values, not the variant id, and will 404 against the real API.
- If the user says "add it", "add that one", or "I'll take it" right after results were shown or a product was opened, find which `last_search_results` entry's title matches the product just discussed/opened, and use THAT entry's `id` field as variantId.
- add_to_cart is low risk and does not require confirmation. If exactly one `last_search_results` entry matches the product just discussed/opened, call the action immediately with that entry's id and quantity 1 (if unspecified) — do NOT ask the user to confirm or to state a quantity first; that is an unnecessary extra turn for an unambiguous, low-risk action. Only ask a clarifying question if two or more entries could plausibly match and you cannot tell which one the user means.
- Report the updated cart total from the action's result; never state a total you did not get back from the action.

WORKED EXAMPLE (the exact id format will differ on the real site, but the pattern is identical):
last_search_results contains: 1. {"id": "cm9x7k2p1q003z", "title": "Wireless Mouse"}
The user opened "Wireless Mouse" (productUrl "/product/wireless-mouse") and then says "add it to cart".
CORRECT input: {"variantId": "cm9x7k2p1q003z", "quantity": 1} — the opaque `id` value copied verbatim from last_search_results.
WRONG input: {"variantId": "wireless-mouse"} or {"variantId": "wireless_mouse"} — a slug or title-derived string is NEVER a valid variantId, even though it looks plausible. If you cannot find a matching `id` field in last_search_results, ask the user instead of inventing a string.
