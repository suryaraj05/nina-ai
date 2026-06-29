"""WhatsApp channel + Razorpay billing webhooks.

Inbound WhatsApp messages (AiSensy / Meta Cloud API) routed through NINA, the
WhatsApp-number<->site mapping, and Razorpay subscription webhooks that move a
site between plans. Mounted via ``include_router`` in ``console_app.create_app``.
"""

from __future__ import annotations

import hmac
import json
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .console_deps import POOL, STORE
from .console_infra import logger
from .crypto import unseal_llm_config

router = APIRouter()


# ── WhatsApp channel (H1–H3) ─────────────────────────────────────────────
# Set NINA_WHATSAPP_VERIFY_TOKEN for webhook verification handshake.
# Set NINA_AISENSY_API_KEY to send replies via AiSensy BSP.
# Map WhatsApp business numbers to site IDs in the site's waNumber field.

class _WAWebhookIn(BaseModel):
    object: str = ""
    entry: list[dict[str, Any]] = Field(default_factory=list)

@router.get("/v1/channels/whatsapp/webhook")
def whatsapp_verify(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
) -> Any:
    """WhatsApp webhook verification handshake (Meta requirement)."""
    expected = os.environ.get("NINA_WHATSAPP_VERIFY_TOKEN", "")
    if hub_mode == "subscribe" and hub_verify_token == expected:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification token mismatch.")

@router.post("/v1/channels/whatsapp/webhook")
async def whatsapp_webhook(body: _WAWebhookIn, request: Request) -> dict[str, Any]:
    """Receive WhatsApp messages from AiSensy BSP and route through NINA."""
    # Extract messages from the WhatsApp webhook payload
    for entry in body.entry:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            wa_number = value.get("metadata", {}).get("phone_number_id", "")

            # Find which site is registered to this WhatsApp number
            site = STORE.find_site_by_wa_number(wa_number)
            if not site:
                logger.info("whatsapp: unknown wa_number_id=%s", wa_number)
                continue

            for msg in value.get("messages", []):
                msg_type = msg.get("type", "")
                if msg_type != "text":
                    continue  # Only handle text messages for now

                from_number = msg.get("from", "")
                text = msg.get("text", {}).get("body", "")
                session_id = f"wa_{from_number}"

                sealed_llm = site.get("llmConfig")
                if not sealed_llm:
                    _raw = os.environ.get("NINA_DEFAULT_LLM_CONFIG")
                    if _raw:
                        try:
                            sealed_llm = json.loads(_raw)
                        except json.JSONDecodeError:
                            pass
                if not sealed_llm or not site.get("agentContract"):
                    continue

                try:
                    llm_config = unseal_llm_config(sealed_llm)
                except Exception:
                    continue

                envelope = await POOL.run(
                    site["id"],
                    llm_config,
                    site["agentContract"],
                    text,
                    session_id,
                )
                reply = ""
                if envelope.get("ok") and envelope.get("data"):
                    reply = (envelope["data"].get("naturalLanguageResponse") or "").strip()

                if reply:
                    await _send_whatsapp_reply(wa_number, from_number, reply)

                STORE.record_usage(site["id"])

    return {"ok": True}

async def _send_whatsapp_reply(wa_number_id: str, to: str, text: str) -> None:
    """Send a text reply via the WhatsApp Cloud API / AiSensy."""
    api_key = os.environ.get("NINA_WHATSAPP_API_KEY", "")
    if not api_key:
        logger.info("whatsapp: NINA_WHATSAPP_API_KEY not set — reply not sent")
        return
    url = f"https://graph.facebook.com/v18.0/{wa_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text[:4096]},  # WhatsApp max text length
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
    except Exception as exc:
        logger.info("whatsapp: send failed — %s", exc)

@router.put("/v1/sites/{site_id}/whatsapp")
def configure_whatsapp(site_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Associate a WhatsApp business number ID with a site."""
    if not STORE.get_site(site_id):
        raise HTTPException(status_code=404, detail="Unknown site_id")
    wa_number_id = body.get("waNumberId", "")
    if not wa_number_id:
        raise HTTPException(status_code=400, detail="waNumberId is required")
    STORE.update_site_fields(site_id, waNumberId=wa_number_id)
    return {"ok": True, "data": {"siteId": site_id, "waNumberId": wa_number_id}}

# ── Razorpay billing webhooks (H4–H6) ────────────────────────────────────
# Set NINA_RAZORPAY_WEBHOOK_SECRET to validate Razorpay webhook signatures.
# Events handled: subscription.activated, subscription.charged,
#                 subscription.cancelled, subscription.expired

# Map Razorpay plan IDs to NINA plan names — set via env or hardcode
_RAZORPAY_PLAN_MAP = {
    os.environ.get("RAZORPAY_PLAN_STARTER", "plan_starter"):    "starter",
    os.environ.get("RAZORPAY_PLAN_GROWTH",  "plan_growth"):     "growth",
    os.environ.get("RAZORPAY_PLAN_SCALE",   "plan_scale"):      "scale",
    os.environ.get("RAZORPAY_PLAN_ENTERPRISE", "plan_ent"):     "enterprise",
}

@router.post("/v1/billing/razorpay/webhook")
async def razorpay_webhook(request: Request) -> dict[str, Any]:
    """Validate Razorpay webhook signature and apply plan changes."""
    body_bytes = await request.body()
    secret = os.environ.get("NINA_RAZORPAY_WEBHOOK_SECRET", "")

    if secret:
        # Razorpay signs with HMAC-SHA256 of the raw body
        import hmac as _hmac
        import hashlib as _hashlib
        sig = request.headers.get("x-razorpay-signature", "")
        expected_sig = _hmac.new(
            secret.encode(), body_bytes, _hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise HTTPException(status_code=400, detail="Invalid Razorpay signature.")

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event = payload.get("event", "")
    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    notes = entity.get("notes", {})
    site_id = notes.get("nina_site_id", "")
    plan_id = entity.get("plan_id", "")

    if not site_id:
        logger.info("razorpay: webhook %s — no nina_site_id in notes", event)
        return {"ok": True, "data": {"processed": False, "reason": "no nina_site_id"}}

    site = STORE.get_site(site_id)
    if not site:
        logger.info("razorpay: webhook %s — unknown site_id=%s", event, site_id)
        return {"ok": True, "data": {"processed": False, "reason": "unknown_site"}}

    plan = _RAZORPAY_PLAN_MAP.get(plan_id)

    if event in ("subscription.activated", "subscription.charged") and plan:
        STORE.set_plan(site_id, plan)
        logger.info("razorpay: site=%s upgraded to plan=%s", site_id, plan)
        return {"ok": True, "data": {"siteId": site_id, "plan": plan, "event": event}}

    if event in ("subscription.cancelled", "subscription.expired", "subscription.halted"):
        STORE.set_plan(site_id, "free")
        logger.info("razorpay: site=%s downgraded to free (event=%s)", site_id, event)
        return {"ok": True, "data": {"siteId": site_id, "plan": "free", "event": event}}

    return {"ok": True, "data": {"processed": False, "event": event}}
