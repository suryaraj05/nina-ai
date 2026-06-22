# Terms of Service

**Product:** NINA — AI Commerce Assistant  
**Operator:** Vedyn Technologies (suryaraj@vedyn.io)  
**Effective date:** 2026-06-22  
**Governing law:** Republic of India

---

## 1. Definitions

| Term | Meaning |
|---|---|
| **NINA** | The AI-powered commerce assistant platform provided by Vedyn Technologies |
| **Merchant** | A business or individual who integrates NINA into their website or app |
| **End User** | A shopper who interacts with the NINA widget on a Merchant's storefront |
| **Services** | The NINA API, widget SDK, console dashboard, and related tools |
| **Query** | A single conversational turn processed by NINA on behalf of a Merchant |

---

## 2. Acceptance

By using NINA, you (the Merchant) agree to these Terms. If you are using NINA on behalf of a company, you represent you have authority to bind that company.

These Terms form a binding contract. Read them carefully.

---

## 3. The Service

NINA provides:
- An AI conversational assistant widget embeddable on your storefront
- An API for processing natural-language shopping queries
- A console for onboarding, contract management, and usage monitoring
- Optional WhatsApp and channel integrations (where available)

### What NINA is not
NINA is a **query processor and commerce assistant** — not a payment processor, not a fulfilment provider, and not a legal or financial advisor. NINA's responses are AI-generated and may contain errors. You are responsible for your store's accuracy, inventory, and pricing.

---

## 4. Merchant Obligations

You agree to:

1. **Provide accurate information** — store URL, contact email, and API configuration
2. **Inform your customers** — include a disclosure that AI assistant functionality is powered by NINA and link to our Privacy Policy
3. **Maintain valid API endpoints** — NINA calls your configured endpoints to serve customers; broken endpoints degrade the experience
4. **Not use NINA for harmful purposes** — including spam, deception, scraping competitors' data, or generating illegal content
5. **Keep your dashboard token confidential** — treat it like a password; rotate it immediately if compromised
6. **Comply with applicable law** — including consumer protection laws, data protection laws, and e-commerce regulations in your jurisdiction

---

## 5. Prohibited Uses

You may not:
- Use NINA to process or store payment card data (it is not PCI-DSS certified for this use)
- Configure NINA to impersonate a human agent without disclosure
- Use NINA to send unsolicited marketing messages
- Attempt to extract, reverse-engineer, or reproduce NINA's underlying models or prompts
- Resell or sublicense NINA access without prior written agreement
- Configure action endpoints that target internal infrastructure (localhost, private IP ranges)

---

## 6. Plans and Billing (C2/C3)

### Free Plan
- 5,000 queries per month
- Powered by NINA's shared LLM (subject to availability)
- No SLA
- May be discontinued with 30 days notice

### Paid Plans (when billing is live)
- Starter (₹799/month): 30,000 queries/month
- Growth (₹1,999/month): 75,000 queries/month
- Scale (₹5,999/month): 200,000 queries/month
- Enterprise (₹14,999/month): Unlimited, dedicated SLA

**Overages:** Queries beyond your plan limit are blocked with a 402 response until the next billing cycle or a plan upgrade.

**Payment:** Via Razorpay (when billing is active). GST will be charged as applicable on Indian invoices.

**Refunds:** No refunds for partial months. If we terminate your account for cause, no refund is provided. If we terminate without cause, we refund the pro-rated remainder.

---

## 7. Data and Privacy

Your use of NINA is also governed by our [Privacy Policy](PRIVACY_POLICY.md).

For data processing as a sub-processor on behalf of your customers, see our [Data Processing Agreement](DATA_PROCESSING_AGREEMENT.md).

You must have a lawful basis for processing your customers' data through NINA. You are the Data Fiduciary under the DPDP Act 2023; NINA is your Data Processor.

---

## 8. Intellectual Property

- NINA's codebase, models, prompts, and infrastructure remain the property of Vedyn Technologies
- Your store data, product catalog, and customer data remain yours
- You grant NINA a limited license to process your store data solely to provide the service
- NINA does not claim ownership of any content generated on your behalf

---

## 9. Service Availability

We target 99.5% uptime on paid plans. The free plan has no uptime SLA.

We may perform maintenance with 24-hour notice where possible. Emergency maintenance may occur without notice.

We are not liable for downtime caused by:
- Your configured API endpoints being unavailable
- LLM provider outages (OpenAI, Google, Anthropic)
- Acts of God, internet infrastructure failures, or force majeure

---

## 10. Liability

**To the maximum extent permitted by Indian law:**

NINA is provided "as is." We make no warranty that AI responses are accurate, complete, or suitable for any particular purpose.

Our total liability to you for any claim shall not exceed the amount you paid us in the 3 months preceding the claim.

We are not liable for:
- Lost revenue, lost profits, or lost data
- Errors in AI-generated responses shown to your customers
- Actions taken by your customers based on NINA's responses
- Third-party LLM provider failures

---

## 11. Indemnification

You agree to indemnify and hold harmless Vedyn Technologies from any claims, damages, or expenses (including legal fees) arising from:
- Your use of NINA in violation of these Terms
- Your customers' claims about your store's products or services
- Your failure to disclose AI-generated content to your customers

---

## 12. Termination

**By you:** Cancel anytime by revoking all API keys and ceasing use. Email us for data deletion.

**By us:** We may suspend or terminate your account immediately for:
- Violation of these Terms
- Non-payment (after 7-day grace period)
- Activity that puts other users or our infrastructure at risk

On termination, your data is retained for 30 days then deleted, unless law requires longer retention.

---

## 13. Changes to Terms

We will notify you of material changes with 14 days notice via email. If you object, you may terminate before the changes take effect. Continued use after the effective date constitutes acceptance.

---

## 14. Governing Law and Disputes

These Terms are governed by the laws of India.

Disputes shall be resolved first through good-faith negotiation. If unresolved within 30 days, disputes shall be referred to arbitration in Bengaluru under the Arbitration and Conciliation Act 1996, with proceedings in English.

Nothing prevents either party from seeking injunctive relief from a court of competent jurisdiction.

---

## 15. Contact

**Email:** suryaraj@vedyn.io  
**Subject line:** NINA Legal — [your issue]

---

*This document is a starting template and should be reviewed by a qualified legal professional before public deployment.*
