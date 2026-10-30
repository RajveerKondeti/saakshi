"""Layer 2: Trust Gate. Plain rules that run BEFORE any AI interprets the notice.

Rules can raise a notice to SCAM_LIKELY. The AI can add flags but can never
lower a rule-based SCAM verdict.
"""
import re

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_valid(g: str) -> bool:
    """Official GSTIN check-digit algorithm (mod 36)."""
    g = g.upper()
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]", g):
        return False
    total = 0
    for i, ch in enumerate(g[:14]):
        product = GSTIN_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36] == g[14]


# (pattern, flag shown to user, severity) - "hard" alone means scam
RED_FLAGS = [
    (r"digital arrest", "Mentions 'digital arrest'. No Indian agency arrests anyone over a call or video.", "hard"),
    (r"safe (custody )?account|rbi (safe|verification|secure) account|verification account",
     "Asks you to move money to a 'safe' or 'verification' account.", "hard"),
    (r"\b[\w.\-]+@(okaxis|oksbi|okicici|okhdfcbank|ybl|paytm|upi|axl|ibl|apl)\b",
     "Demands payment to a personal UPI ID.", "hard"),
    (r"gift ?cards?|bitcoin|crypto|usdt", "Demands payment in gift cards or crypto.", "hard"),
    (r"(stay|remain) on (the )?(video|skype|whatsapp) call|video call",
     "Demands you stay on a video call.", "medium"),
    (r"do not (tell|inform|disclose)|don'?t tell|keep (this )?(strictly )?confidential|secrecy",
     "Tells you to keep it secret from family.", "medium"),
    (r"within (\d+|one|two|three) hours?|immediately or|failing which.{0,40}arrest",
     "Threatens arrest or action within hours.", "medium"),
    (r"skype|whatsapp", "Claims to be official but uses WhatsApp/Skype.", "medium"),
    (r"@(gmail|yahoo|outlook|hotmail|rediffmail)\.com",
     "Official-sounding notice from a free email address.", "medium"),
]

DIN_PATTERN = r"ITBA/[A-Z]+/[A-Z]/[\w().\-]+/\d{4}-\d{2}/\d{6,}|\bDIN\s*[:\-]?\s*[A-Z0-9/().\-]{10,}"


def run(text: str) -> dict:
    norm = re.sub(r"\s+", " ", text)
    low = norm.lower()
    flags, hard, medium = [], 0, 0

    for pattern, message, severity in RED_FLAGS:
        m = re.search(pattern, low)
        if m:
            flags.append({"flag": message, "evidence": norm[max(0, m.start() - 40): m.end() + 40].strip()})
            hard += severity == "hard"
            medium += severity == "medium"

    checks = {}
    is_income_tax = bool(re.search(r"income[\s-]?tax|cbdt|assessing officer|section 14[38]|ITBA", text, re.I))
    if is_income_tax:
        checks["din_present"] = bool(re.search(DIN_PATTERN, text))

    gstins = re.findall(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b", text.upper())
    if gstins:
        checks["gstin_checksum_valid"] = all(gstin_valid(g) for g in gstins)
        if not checks["gstin_checksum_valid"]:
            flags.append({"flag": "GSTIN fails the official checksum, so it is not a real GST number.",
                          "evidence": ", ".join(gstins)})
            medium += 1

    if hard >= 1 or medium >= 2:
        status = "SCAM_LIKELY"
    elif is_income_tax and not checks.get("din_present"):
        status = "UNVERIFIED"
        flags.append({"flag": "No Document Identification Number (DIN). Since Oct 2019, genuine "
                              "Income Tax communications must carry one.", "evidence": "DIN not found"})
    else:
        status = "REAL_LIKELY"

    how = ("Verify Income Tax notices on incometax.gov.in → 'Authenticate notice/order issued by ITD'. "
           "Verify GST notices by logging in to gst.gov.in. Report fraud at 1930 or cybercrime.gov.in.")
    return {"status": status, "red_flags": flags, "checks": checks, "how_to_verify_officially": how}
