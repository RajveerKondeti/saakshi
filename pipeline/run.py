"""The Saakshi pipeline: Perceive -> Trust Gate -> Extract -> Ground -> Reason -> Act -> Guard."""
import base64
import hashlib
import io
import json
import os
import re

from core import llm, prompts
from core.pii import redact
from pipeline import trust_gate

MAX_CHARS = 12000
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
OFFICIAL_DOMAINS = [
    "incometax.gov.in", "incometaxindia.gov.in", "cbic-gst.gov.in", "gst.gov.in",
    "cybercrime.gov.in", "mha.gov.in", "pib.gov.in", "rbi.org.in", "nalsa.gov.in",
    "indiacode.nic.in",
]


# ---------- L1: Perception ----------
def perceive(data: bytes, filename: str, trace: list) -> str:
    name = filename.lower()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:5])
        trace.append({"step": "Read PDF text", "model": "pypdf (no AI cost)",
                      "tokens_in": 0, "tokens_out": 0, "cost_usd": 0, "seconds": 0})
        if len(text.strip()) > 50:
            return text
        raise ValueError("This PDF is a scan. Upload a photo or screenshot of the page instead.")
    mime = "image/png" if name.endswith(".png") else "image/jpeg"
    b64 = base64.b64encode(data).decode()
    content = [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
               {"type": "text", "text": "Transcribe this document."}]
    return llm.call("omni", prompts.PERCEIVE, content, trace, "Read the notice (Omni)")


# ---------- L4: Grounding ----------
def ground(facts: dict, trace: list) -> list:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    from tavily import TavilyClient
    query = redact(f"{facts.get('notice_type', '')} {facts.get('issuing_authority', '')} "
                   f"India notice how to respond")[:300]
    try:
        res = TavilyClient(api_key=key).search(
            query=query, include_domains=OFFICIAL_DOMAINS, max_results=4, search_depth="basic")
        sources = [{"title": r.get("title", ""), "url": r.get("url", ""),
                    "snippet": (r.get("content") or "")[:600]} for r in res.get("results", [])]
    except Exception as e:
        sources = []
        query += f"  (search failed: {e})"
    trace.append({"step": "Search official sources (Tavily)", "model": f"query: {query}",
                  "tokens_in": 0, "tokens_out": 0, "cost_usd": 0, "seconds": 0})
    return sources


def _quote_is_real(quote, text) -> bool:
    """Deadline is only shown if its quote really appears in the notice."""
    if not quote:
        return False
    norm = lambda s: re.sub(r"\W+", "", s.lower())
    return norm(quote) in norm(text)


# ---------- Full pipeline ----------
def analyze(text: str, language: str, progress=lambda msg: None, trace=None) -> dict:
    trace = trace if trace is not None else []
    text = text[:MAX_CHARS]

    cache_key = hashlib.sha256(f"{language}|{text}".encode()).hexdigest()[:16]
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, encoding="utf-8") as f:
                result = json.load(f)
            result["from_cache"] = True
            return result
        except Exception:
            os.remove(cache_file)  # broken cache file: delete it and run fresh

    progress("Checking if the notice is genuine")
    trust = trust_gate.run(text)

    progress("Extracting the facts (Nemotron Nano)")
    facts = llm.call_json("nano", prompts.EXTRACT, text, trace, "Extract facts (Nano)")

    # The AI can raise suspicion but never lower a rule-based SCAM verdict.
    if trust["status"] != "SCAM_LIKELY" and float(facts.get("scam_probability") or 0) >= 0.8 \
            and facts.get("scam_signals"):
        trust["status"] = "SCAM_LIKELY"
        trust["red_flags"] += [{"flag": s, "evidence": "AI pattern check"} for s in facts["scam_signals"]]
    facts["deadline_verified"] = _quote_is_real(facts.get("deadline_quote"), text)

    if trust["status"] == "SCAM_LIKELY":
        # Cheap path: no web search, no Ultra calls.
        verdict = {"tier": "SCAM",
                   "one_line": "This looks like a fake notice. Do not pay and do not share any OTP.",
                   "why": "Saakshi's trust checks found signs that genuine government notices never have.",
                   "timeline": [{"when": "Today", "what_happens": "Do nothing they ask. Report it at 1930 "
                                 "or cybercrime.gov.in.", "source_tag": "OFFICIAL"}]}
        sources, guard = [], None
        progress("Explaining the warning signs (Nemotron Super)")
        action = llm.call_json("super", prompts.ACT.replace("{language}", language),
                               json.dumps({"tier": "SCAM", "red_flags": trust["red_flags"],
                                           "notice": text[:4000]}), trace, "Explain (Super)")
    else:
        progress("Searching official government sources (Tavily)")
        sources = ground(facts, trace)

        progress("Judging how serious it is (Nemotron Ultra)")
        verdict = llm.call_json("ultra", prompts.REASON, json.dumps(
            {"facts": facts, "trust": trust, "sources": sources}), trace, "Judge severity (Ultra)")

        progress("Writing your explanation and reply (Nemotron Super)")
        action = llm.call_json("super", prompts.ACT.replace("{language}", language), json.dumps(
            {"facts": facts, "verdict": verdict, "sources": sources}), trace, "Draft reply (Super)")

        progress("Guardian is verifying every claim (Nemotron Ultra)")
        guard = llm.call_json("ultra", prompts.GUARD, json.dumps(
            {"notice_text": text, "sources": sources,
             "draft": {"explanation": action.get("explanation"), "timeline": verdict.get("timeline")}}),
            trace, "Verify claims (Guardian, Ultra)")
        if guard.get("revised_explanation"):
            action["explanation"] = guard["revised_explanation"]

    result = {"trust": trust, "facts": facts, "sources": sources, "verdict": verdict,
              "action": action, "guard": guard, "trace": trace, "from_cache": False}
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return result