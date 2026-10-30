"""Budget guard. Every model call passes through here.

Why: Token Factory credits are limited ($25). This file:
  1. estimates the cost of every call from the real token counts,
  2. keeps a running total in .spend.json,
  3. refuses new calls once the hard cap is reached.
"""
import json
import os
import threading

# USD per 1M tokens (input, output). Check the Token Factory pricing page
# and update if different. A 20% safety margin is added on top.
PRICES = {
    "ultra": (1.00, 3.00),
    "super": (0.30, 0.90),
    "nano": (0.06, 0.24),
    "omni": (0.06, 0.24),
}
SAFETY_MARGIN = 1.2

HARD_CAP_USD = float(os.getenv("HARD_CAP_USD", "8.0"))  # stop well before $25
LEDGER = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".spend.json")
_lock = threading.Lock()


class BudgetExceeded(Exception):
    pass


def _read() -> float:
    try:
        with open(LEDGER) as f:
            return float(json.load(f).get("spent_usd", 0.0))
    except Exception:
        return 0.0


def spent() -> float:
    return _read()


def check() -> None:
    """Call BEFORE every model call."""
    if _read() >= HARD_CAP_USD:
        raise BudgetExceeded(
            f"Spending cap of ${HARD_CAP_USD:.2f} reached. Live analysis is paused; "
            "the sample notices still work from saved results."
        )


def record(tier: str, tokens_in: int, tokens_out: int) -> float:
    """Call AFTER every model call. Returns the cost of this call."""
    p_in, p_out = PRICES[tier]
    cost = (tokens_in * p_in + tokens_out * p_out) / 1_000_000 * SAFETY_MARGIN
    with _lock:
        total = _read() + cost
        with open(LEDGER, "w") as f:
            json.dump({"spent_usd": round(total, 6)}, f)
    return cost
