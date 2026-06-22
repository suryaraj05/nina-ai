# SOC 2 Type II Readiness Roadmap

**Product:** NINA — AI Commerce Assistant  
**Target:** SOC 2 Type II certification  
**Estimated timeline:** 12–18 months from start  
**Priority:** Required for enterprise merchants (₹14,999/month plan)

---

## What is SOC 2 Type II?

SOC 2 (System and Organization Controls 2) is an audit standard developed by the AICPA. Type II covers a **6–12 month observation period** — auditors verify that your controls are not just documented, but actually operating continuously.

The five Trust Services Criteria:

| Criteria | What it covers |
|---|---|
| **Security** (required) | Protection against unauthorized access |
| **Availability** | Uptime and performance commitments |
| **Processing Integrity** | Complete, accurate, timely processing |
| **Confidentiality** | Protection of confidential information |
| **Privacy** | Collection, use, retention, disclosure of personal data |

NINA needs **Security** (mandatory) + **Availability** + **Privacy** for enterprise credibility.

---

## Current Baseline (as of June 2026)

### Already In Place ✓

| Control | Status |
|---|---|
| Encryption in transit (TLS) | ✓ Render enforces HTTPS |
| Encryption at rest (LLM keys) | ✓ AES-128 Fernet |
| API key hashing | ✓ HMAC-SHA256, no plaintext |
| Session ID cryptographic randomness | ✓ `crypto.getRandomValues` (128-bit) |
| Rate limiting | ✓ Per-IP + per-key on `/v1/query` |
| Admin authentication | ✓ `NINA_CONSOLE_ADMIN_SECRET` |
| Input validation (SSRF, path traversal) | ✓ Phase 1 |
| XSS protection in widget | ✓ Phase 1 |
| Structured logging | ✓ JSON logs, Phase 3 |
| Error monitoring | ✓ Optional Sentry, Phase 3 |
| Circuit breaker | ✓ Phase 3 |
| Data retention policy | ✓ Documented |
| DPA and Privacy Policy | ✓ Documented |
| Non-root Docker user | ✓ Dockerfile |

### Gaps to Close Before Audit

| Gap | SOC 2 Criteria | Priority | Estimated effort |
|---|---|---|---|
| No persistent database (JSON file store) | Security, Integrity | CRITICAL | 3 weeks (PostgreSQL migration) |
| Single server instance (no HA/failover) | Availability | HIGH | 1 week (Render auto-scaling or replica) |
| No formal access control policy document | Security | HIGH | 1 day |
| No employee background check policy | Security | MEDIUM | 1 day (document) |
| No vendor risk management | Security | MEDIUM | 2 days |
| No formal incident response plan | Security | HIGH | 2 days (write the runbook) |
| No change management process (CI/CD gates) | Integrity | MEDIUM | 1 week |
| No penetration test (required by auditors) | Security | HIGH | ₹1.5–3L (external vendor) |
| No vulnerability scanning in CI | Security | MEDIUM | 1 day (Snyk/Trivy free tier) |
| No backup and disaster recovery test | Availability | HIGH | 2 days |
| No formal SLA document | Availability | MEDIUM | 1 day |
| No data classification policy | Confidentiality | MEDIUM | 1 day |
| No offboarding procedure (revoking access) | Security | LOW | 1 day |
| No audit log for admin operations | Security | HIGH | 1 week |
| Multi-factor authentication for console | Security | HIGH | 1 week |

---

## Recommended Timeline

### Months 1–3: Foundation
- [ ] Migrate ConsoleStore to PostgreSQL (C1 from main checklist)
- [ ] Write incident response runbook
- [ ] Write access control policy
- [ ] Set up vulnerability scanning in CI (Snyk/Trivy)
- [ ] Implement admin audit log (`/v1/audit/events`)
- [ ] Add MFA to console login (TOTP via `pyotp`)

### Months 4–6: Hardening
- [ ] Penetration test (hire external vendor)
- [ ] Fix all pentest findings
- [ ] Set up automated backups with restore testing
- [ ] Implement formal change management (PR reviews, staging env)
- [ ] Write vendor risk assessments (Render, OpenAI, Google, Anthropic)
- [ ] Set up availability monitoring + SLA tracking (UptimeRobot Pro)

### Months 7–12: Observation Period
- [ ] Select SOC 2 auditor (recommend: Prescient Assurance, Drata, or Vanta)
- [ ] Use Vanta or Drata to automate evidence collection (~₹8L/year)
- [ ] Begin the 6-month observation window
- [ ] Remediate any findings from preliminary review
- [ ] Receive Type II report

### Cost Estimate

| Item | Estimated cost |
|---|---|
| SOC 2 auditor (Type II) | ₹15–25L |
| Compliance automation (Vanta/Drata) | ₹6–10L/year |
| Penetration test | ₹1.5–3L |
| Engineering time (internal) | 8–12 weeks |
| **Total Year 1** | **~₹25–40L** |

---

## Quick Wins (Do This Week)

1. **Vulnerability scan in CI**: Add `trivy` or `pip-audit` to the GitHub Actions workflow — free, takes 1 hour.
2. **Formal access control doc**: Write a one-page policy on who has access to what and how access is revoked. Store in `legal/ACCESS_CONTROL_POLICY.md`.
3. **Backup script**: Write a daily cron job to copy `nina_console_store.json` to object storage (Cloudflare R2 is ₹0 for first 10GB).

---

## Why Bother?

Without SOC 2:
- Enterprise merchants (Myntra, Meesho, D2C brands doing ₹10Cr+/month) will not sign contracts
- You cannot serve BFSI (banking, insurance) clients
- Due diligence questionnaires from enterprise sales will block deals

With SOC 2 Type II:
- Sales unblocked for enterprise tier (₹14,999/month × 20 clients = ₹36L ARR)
- Differentiator vs. smaller competitors who don't have it
- Required for Shopify App Store "Enterprise" badge

---

*Review and update this document quarterly. Assign an owner for each gap item.*
