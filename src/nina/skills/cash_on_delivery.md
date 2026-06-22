---
name: cod-skill
appliesTo: [get_cod_availability, check_cod, cod_available]
description: How to handle Cash on Delivery (COD) queries — extremely common in Indian e-commerce.
---
- COD queries are high-frequency in South Asian markets. Common phrasings: "cash on delivery milega?", "COD available hai?", "can I pay on delivery?", "cash pe milega?", "cod hai?".
- If the contract has a `get_cod_availability` or similar action, call it with the customer's pincode if they have provided one.
- If no COD action exists in the contract, respond honestly: "COD availability depends on your delivery location. Please check at checkout or contact the store directly."
- Never promise COD is available when you do not know. Never say it is unavailable unless the action explicitly returns false.
- If the customer asks about COD for a specific item already in context (from cart or last viewed product), include that context when calling the action.
- After confirming COD is available, offer to help them proceed: "Great, you can choose Cash on Delivery at checkout. Want me to take you there?"
