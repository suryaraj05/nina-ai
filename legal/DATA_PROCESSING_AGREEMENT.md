# Data Processing Agreement (DPA)

**Between:**  
- **Data Fiduciary / Controller:** The Merchant (identified in the NINA Console during onboarding)  
- **Data Processor / Sub-Processor:** Vedyn Technologies, operating NINA  

**Effective date:** Date of merchant onboarding  
**Applicable law:** India DPDP Act 2023 · EU GDPR Article 28 · IT (Amendment) Act 2008

This DPA is incorporated by reference into the NINA Terms of Service and governs all processing of personal data NINA performs on behalf of the Merchant.

---

## 1. Scope

This DPA applies when NINA processes personal data belonging to the Merchant's end users (shoppers) in the course of providing the NINA AI Commerce Assistant service.

**Nature of processing:** Real-time conversational query processing  
**Purpose:** Helping shoppers find products, check order status, and complete purchases on the Merchant's store  
**Categories of data subjects:** Shoppers visiting the Merchant's website or app  
**Categories of personal data:** Chat messages, session identifiers, page URLs; potentially order IDs or contact details if volunteered by the user  
**Duration:** For the term of the Merchant's NINA subscription

---

## 2. NINA's Obligations as Processor

NINA agrees to:

1. **Process only on documented instructions** — NINA will process personal data only as directed by the Merchant's configured contract (the `agent.json` file) and these Terms. NINA will not use end-user chat data for training its own models.

2. **Ensure confidentiality** — All personnel with access to personal data are bound by confidentiality obligations.

3. **Implement appropriate security measures** including:
   - TLS encryption in transit
   - AES-128 Fernet encryption for stored LLM API keys
   - HMAC-SHA256 for API key verification (no plaintext keys at rest)
   - Cryptographically secure session IDs
   - Rate limiting to prevent bulk data extraction
   - Same-origin restrictions on widget fetch instructions

4. **Assist with data subject rights** — NINA will assist the Merchant in responding to requests from data subjects exercising their rights under DPDP Act 2023 or GDPR (access, correction, erasure, portability), to the extent technically feasible given NINA's architecture (anonymous sessions with no persistent user identity).

5. **Notify of data breaches** — In the event of a personal data breach, NINA will notify the Merchant within 72 hours of becoming aware, providing: nature of the breach, categories affected, likely consequences, and measures taken.

6. **Sub-processors** — NINA uses the following sub-processors:

   | Sub-processor | Location | Purpose | Safeguard |
   |---|---|---|---|
   | Render.com | USA | Hosting | Standard Contractual Clauses |
   | OpenAI / Google / Anthropic (configurable) | USA | LLM inference | DPA with each provider; merchants may supply their own key |
   | Redis provider (optional) | Configurable | Session storage | Operator-configured |

   NINA will inform the Merchant of any intended changes to sub-processors, providing 14 days' notice, during which the Merchant may object.

7. **Allow audits** — Upon request with 30 days notice, NINA will make available information necessary to demonstrate compliance with this DPA.

8. **Delete or return data** — Upon termination, NINA will delete all Merchant data (including end-user session data) within 30 days, unless law requires longer retention.

---

## 3. Merchant's Obligations as Fiduciary

The Merchant agrees to:

1. Have a valid **lawful basis** for processing end-user data through NINA (consent, contract, or legitimate interest as appropriate)
2. Provide end users with a **privacy notice** disclosing that their queries are processed by an AI assistant, and including a link to NINA's Privacy Policy or an equivalent
3. Not configure NINA to collect **sensitive personal data** (health, financial, biometric, etc.) unless appropriate safeguards are in place
4. Not instruct NINA to process data in a way that violates applicable law
5. Ensure any **API endpoints** configured in NINA contracts collect and transmit only the minimum data necessary

---

## 4. Data Localisation (India DPDP Act 2023)

As of the effective date, the DPDP Act 2023 does not yet impose mandatory data localisation for general personal data (notification awaited from the Central Government). Merchants in regulated sectors (finance, health, defence) must assess their sector-specific localisation requirements independently.

If mandatory localisation is introduced, NINA commits to providing a compliant hosting option within a reasonable timeframe.

---

## 5. International Transfers

Where personal data is transferred outside India or the EEA:
- Transfers to the USA rely on standard contractual clauses or the DPF framework
- NINA will update this DPA if the legal basis for international transfers changes

---

## 6. Liability

The liability of each party under this DPA is subject to the limitations set out in the NINA Terms of Service. NINA is not liable for processing instructions given by the Merchant that violate applicable data protection law.

---

## 7. Term and Termination

This DPA remains in effect for the duration of the NINA Terms of Service and terminates automatically on termination of those Terms.

---

## 8. Governing Law

This DPA is governed by Indian law. Disputes are resolved per the dispute resolution clause in the NINA Terms of Service.

---

## 9. Contact for Data Protection Matters

**Data Protection Point of Contact:** Suryaraj  
**Email:** suryaraj@vedyn.io  
**Response time:** Within 72 hours

---

*This DPA is a starting template compliant with DPDP Act 2023 structure and GDPR Article 28. It should be reviewed by a qualified legal professional before public deployment and should be executed as a signed agreement for enterprise customers.*
