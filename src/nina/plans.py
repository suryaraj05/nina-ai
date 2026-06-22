"""Shared plan definitions — imported by both console_app and pg_store."""
from __future__ import annotations

from datetime import datetime, timezone

# Monthly query caps per plan. None = unlimited (enterprise).
# Update billing docs and Razorpay plan IDs whenever this changes.
PLAN_LIMITS: dict[str, int | None] = {
    "free":       5_000,
    "starter":   30_000,   # ₹799/month
    "growth":    75_000,   # ₹1,999/month
    "scale":    200_000,   # ₹5,999/month
    "enterprise": None,
}

VALID_PLANS = set(PLAN_LIMITS)


def current_period() -> str:
    """Return YYYYMM string for the current UTC billing period, e.g. '202601'."""
    dt = datetime.now(timezone.utc)
    return f"{dt.year:04d}{dt.month:02d}"
