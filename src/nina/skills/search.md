---
name: search-skill
appliesTo: [search_products]
description: How to interpret search requests, including price filters and vague phrasing.
fastPath:
  - "search for {query}"
  - "search {query}"
  - "find {query}"
  - "look for {query}"
---
- A "{query}" fast path is only safe for literal, already-concrete search terms (e.g. "search for running shoes"). Never add a pattern like "show me {query}" or "I want {query}" — those phrasings often carry a goal that needs reasoning first (e.g. "show me clothes for summer" needs to be translated into concrete attributes like lightweight fabric and short sleeves before searching), and a literal fast path would search for the unreasoned sentence verbatim and silently skip that reasoning.
- Treat price phrases like "under ₹70,000", "below 70k", or "less than 1000 rupees" as a maximum-price constraint. If the action's parameters have no dedicated price field, fold the constraint into the search query text rather than inventing a parameter the schema doesn't define.
- Normalize currency shorthand (70k = 70,000) yourself before calling the action.
- A vague request ("show me something nice for summer", "what laptops do you have") still has enough signal to call search_products with your best-guess query terms. Prefer calling the action over asking a clarifying question — a broad result list is more useful to the user than no action at all.
- Never state a product exists, or quote a price, that did not come back in this action's result. If the result is empty, say so plainly instead of inventing items.
