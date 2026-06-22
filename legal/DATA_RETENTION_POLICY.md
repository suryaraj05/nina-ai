# Data Retention Policy

**Product:** NINA — AI Commerce Assistant  
**Effective date:** 2026-06-22  
**Review cycle:** Annually or when legal requirements change

---

## 1. Purpose

This policy defines how long NINA retains different categories of data, the legal basis for each retention period, and the deletion procedures.

---

## 2. Retention Schedule

### 2.1 End-User Data (Shoppers)

| Data type | Storage location | Retention period | Deletion trigger |
|---|---|---|---|
| Chat session messages | In-memory (NinaPool) | Session lifetime | Session eviction or service restart |
| Session ID → conversation mapping | Redis (if configured) | 24 hours TTL (max) | TTL expiry, automatic |
| Session ID in user's browser | localStorage | Until user clears browser storage | User action — outside NINA's control |
| IP addresses (rate limiting) | In-memory sliding window | 60 seconds | Automatic eviction |
| Page URL and page title | In-memory, per request | Not persisted | End of request |

**Key principle:** NINA does not persist chat transcripts beyond the active session. There is no "chat history" database. Once a session expires, the conversation is unrecoverable.

### 2.2 Merchant Data

| Data type | Storage location | Retention period | Deletion trigger |
|---|---|---|---|
| Organisation record (name, email) | ConsoleStore (JSON / future: database) | Duration of subscription + 30 days | Account deletion request |
| Site configuration | ConsoleStore | Duration of subscription + 30 days | Account deletion request |
| API key digests (HMAC-SHA256) | ConsoleStore | Until key is revoked; then 30 days | Revocation + 30-day cleanup cycle |
| LLM API keys (encrypted) | ConsoleStore | Until merchant removes or rotates | Merchant action |
| Dashboard token digest | ConsoleStore | Until token is rotated | Token rotation |
| Usage statistics (query counts) | ConsoleStore | Rolling 12 months | Automatic eviction of months > 12 |
| Webhook events (broken selectors) | ConsoleStore (capped at 500) | Until evicted by the 500-event cap | FIFO eviction |

### 2.3 Infrastructure and Security Logs

| Data type | Retention period | Purpose |
|---|---|---|
| Server access logs (Render) | 30 days | Incident investigation |
| Error logs | 30 days | Debugging |
| Rate-limit counters | 60 seconds (sliding window) | Abuse prevention |

---

## 3. Deletion Procedures

### 3.1 Automatic Deletion
- Redis sessions: TTL enforced by Redis server; no manual action required
- Rate-limit counters: evicted from in-memory deque automatically
- Webhook events: oldest events evicted when list reaches 500 entries

### 3.2 Merchant-Initiated Deletion
A merchant may request full data deletion by emailing suryaraj@vedyn.io with subject "NINA Data Deletion Request — [Org Name]".

Within 30 days we will:
1. Revoke all API keys for the organisation
2. Delete all site configurations including contracts and LLM configs
3. Delete the organisation record
4. Delete usage statistics
5. Confirm deletion in writing

### 3.3 End-User Deletion Requests
Since end-user sessions are anonymous (no name/email associated), we cannot identify records belonging to a specific person without:
- The session ID stored in their browser
- The approximate time of their chat

If an end user provides these, we will confirm whether any in-session data remains (extremely unlikely after 24 hours) and delete it if found.

---

## 4. Data Minimisation Commitments

NINA is designed to collect the minimum data required:
- No user accounts for shoppers
- No persistent chat history
- No advertising profiles
- Session IDs are random 128-bit values with no personal data embedded
- IP addresses are used only for rate limiting and discarded after 60 seconds

---

## 5. Legal Holds

In the event of a legal hold (court order, regulatory investigation), we may retain specific data beyond these standard periods. We will notify affected parties to the extent permitted by law.

---

## 6. Backups

The ConsoleStore JSON file may be present in infrastructure backups (e.g., Render volume snapshots). Backup retention is governed by the infrastructure provider's policy (typically 7–30 days). Data deleted from the live store will be removed from backups as those backups age out.

---

## 7. Policy Review

This policy is reviewed annually. Significant changes will be communicated to merchants via email with 14 days' notice.

---

**Contact:** suryaraj@vedyn.io
