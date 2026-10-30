"""One place for every call to Nebius Token Factory."""
import json
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

from core import budget

load_dotenv()

MODELS = {
    "nano": os.getenv("NANO_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
    "super": os.getenv("SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
    "ultra": os.getenv("ULTRA_MODEL", "nvidia/Nemotron-3-Ultra-550b-a55b"),
    "omni": os.getenv("OMNI_MODEL", "nvidia/Nemotron-3-Nano-Omni"),
}

# Max output tokens per tier: caps cost per call.
MAX_OUT = {"nano": 1500, "omni": 2000, "super": 2500, "ultra": 4000}

_client = None


def client() -> OpenAI:
    global _client
    if _client is None:
        if not os.getenv("NEBIUS_API_KEY"):
            raise RuntimeError("NEBIUS_API_KEY is missing. Add it to your .env file "
                               "(local) or to Secrets (Streamlit Cloud).")
        _client = OpenAI(
            base_url=os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"),
            api_key=os.getenv("NEBIUS_API_KEY"),
            timeout=120,
        )
    return _client


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def call(tier: str, system: str, user, trace: list, step: str) -> str:
    """Run one model call. `user` is a string or a list of content parts (for images)."""
    budget.check()
    model = MODELS[tier]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    # Turn off long "thinking" for fast tiers to save tokens (ignored if unsupported).
    extra = {"chat_template_kwargs": {"enable_thinking": False}} if tier != "ultra" else None

    start = time.time()
    try:
        resp = client().chat.completions.create(
            model=model, messages=messages, max_tokens=MAX_OUT[tier],
            temperature=0.2, extra_body=extra,
        )
    except Exception:
        if extra is None:
            raise
        resp = client().chat.completions.create(  # retry without the extra option
            model=model, messages=messages, max_tokens=MAX_OUT[tier], temperature=0.2,
        )

    text = _strip_thinking(resp.choices[0].message.content)
    usage = getattr(resp, "usage", None)
    t_in = getattr(usage, "prompt_tokens", None) or len(json.dumps(messages)) // 3
    t_out = getattr(usage, "completion_tokens", None) or len(text) // 3
    cost = budget.record(tier, t_in, t_out)
    trace.append({"step": step, "model": model, "tokens_in": t_in, "tokens_out": t_out,
                  "cost_usd": round(cost, 5), "seconds": round(time.time() - start, 1)})
    return text


def parse_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply, fixing common model mistakes."""
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON")
    raw = text[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Numbers written Indian-style, e.g. 4,820 or 1,42,600 -> 4820, 142600
    raw = re.sub(r"(:\s*)(-?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?)(?=\s*[,}\]\n])",
                 lambda m: m.group(1) + m.group(2).replace(",", ""), raw)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)                   # trailing commas
    raw = re.sub(r"(:\s*)None\b", r"\1null", raw)                # Python-style None
    return json.loads(raw)


def call_json(tier, system, user, trace, step) -> dict:
    """Call and parse JSON; one cheap repair retry if parsing fails."""
    text = call(tier, system, user, trace, step)
    try:
        return parse_json(text)
    except Exception:
        fixed = call("nano", "Return ONLY valid JSON. No prose.",
                     f"Fix this into valid JSON:\n{text[:6000]}", trace, step + " (repair)")
        return parse_json(fixed)