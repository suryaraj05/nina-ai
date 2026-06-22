# Privacy Policy

**Product:** NINA — AI Commerce Assistant  
**Operator:** Vedyn Technologies (suryaraj@vedyn.io)  
**Effective date:** 2026-06-22  
**Applicable law:** India DPDP Act 2023 · EU GDPR · applicable Indian IT Rules

---

## 1. Who This Policy Covers

This policy covers two relationships:

| Party | Role | What data we collect |
|---|---|---|
| **End users** (shoppers) | Data Principal | Chat messages, session ID, page URL, language, rough location |
| **Merchants** (store owners) | Data Fiduciary → see DPA | Business name, email, store URL, API keys, usage stats |

---

## 2. Data We Collect From End Users

When a shopper interacts with the NINA widget embedded on a merchant's store:

| Data | Purpose | Retention |
|---|---|---|
| Chat messages (text only) | Generating AI responses | Session lifetime (see §5) |
| Session ID (anonymous random token) | Maintaining conversation context | Stored in browser localStorage; server-side TTL per §5 |
| Current page URL and page title | Understanding shopping context | Not stored beyond the request |
| Browser language | Responding in the user's language | Not stored beyond the request |
| IP address | Rate limiting and abuse prevention | Discarded after rate-limit window (60 seconds) |

**We do not collect:** names, email addresses, phone numbers, payment details, or any other personally identifiable information unless the user voluntarily types it in the chat.

If a user types personal data into the chat (e.g., their phone number to check an order), that data is processed only to complete the requested action and is not stored beyond the session TTL.

---

## 3. Data We Collect From Merchants

When a merchant signs up via the NINA Console:

- **Organisation name and email address** — used for account identification and communication
- **Store URL and allowed origins** — used to verify widget embedding
- **LLM API keys** — stored encrypted at rest using AES-128 Fernet encryption; decrypted only at query time in memory
- **Usage statistics** — query counts per site, used for plan management and billing
- **Dashboard token digest** — a one-way cryptographic hash used for authentication

---

## 4. Legal Basis for Processing

| Processing activity | Legal basis (DPDP Act 2023 / GDPR) |
|---|---|
| Answering user shopping queries | Legitimate interest / Performance of service |
| Rate limiting and abuse prevention | Legitimate interest |
| Merchant account management | Performance of contract |
| LLM API key storage | Consent (provided during onboarding) |
| Usage metering for billing | Performance of contract |

---

## 5. Data Retention

| Data | Retention period |
|---|---|
| Chat session data (in-memory) | Until session expires (default: 30 minutes of inactivity) |
| Redis session store | 24 hours TTL maximum |
| Merchant org/site data | Retained while account is active; deleted within 30 days of account deletion request |
| API key digests | Deleted immediately on key revocation |
| Usage statistics | Rolling 12-month window |
| Server access logs | 30 days |

**Chat transcripts are not stored permanently.** Once a session expires, the conversation is gone.

---

## 6. Data Sharing and Third Parties

We share data with:

| Third party | What is shared | Purpose |
|---|---|---|
| **LLM provider** (OpenAI / Google / Anthropic, configurable) | Chat messages within the session | Generating AI responses |
| **Cloud host** (Render.com) | All server-side data | Hosting infrastructure |
| **Redis provider** (optional) | Session IDs and conversation state | Session persistence |

We do **not** sell data to any third party. We do not use chat data to train our own models.

The LLM provider receives chat messages. Their own privacy policy governs their data handling. We recommend merchants inform their customers of this.

---

## 7. Data Transfers

NINA's servers may be located outside India. Data transfers to the EU are covered by standard contractual clauses. Data transfers to the US rely on the DPF framework where applicable, or contractual safeguards.

Merchants operating in India under the DPDP Act 2023 should review their data localisation obligations independently.

---

## 8. User Rights

Under the DPDP Act 2023 and GDPR, end users have the right to:

- **Access** — Know what personal data we hold about you
- **Correction** — Request correction of inaccurate data
- **Erasure** — Request deletion of your personal data
- **Withdrawal of consent** — Where processing is based on consent
- **Grievance redressal** — Lodge a complaint with the Data Protection Board of India (once operational) or a supervisory authority in your country

To exercise these rights, email: **suryaraj@vedyn.io**

Since NINA chat sessions are anonymous by default (no name/email collected), we may be unable to identify records belonging to a specific person without additional information you provide.

---

## 9. Children's Privacy

NINA is not directed at children under 18. We do not knowingly collect personal data from minors. If you believe we have collected data from a child, contact us immediately.

---

## 10. Security

- LLM API keys are encrypted at rest (AES-128 Fernet)
- Session IDs use cryptographically secure random generation (`crypto.getRandomValues`)
- All API communications use TLS (HTTPS only in production)
- API keys use HMAC-SHA256 digests — plaintext keys are never stored
- Widget fetch instructions are restricted to same-origin calls only

---

## 11. Cookie and Storage Policy

The NINA widget uses **browser localStorage** to store a session ID. This is a functional necessity — without it, the widget cannot maintain conversation context across page loads.

We do not use advertising cookies, tracking pixels, or third-party analytics.

---

## 12. Changes to This Policy

We will notify merchants of material changes via email and update the effective date above. Continued use of NINA after the effective date constitutes acceptance.

---

## 13. Contact

**Data Protection contact:** Suryaraj  
**Email:** suryaraj@vedyn.io  
**Response time:** Within 72 hours for privacy requests

---

*This policy is a starting template and should be reviewed by a qualified legal professional before public deployment.*
