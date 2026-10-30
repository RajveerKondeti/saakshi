# Saakshi: the citizen's counter-agent for official notices

**Got a scary notice? Check it before you act.**

Governments now generate notices with data analytics and AI. Criminals forge them: "digital arrest" scam cases in India rose from 39,925 (2022) to 1,23,672 (2024). And since 1 April 2026, two Income-tax Acts apply at once. Citizens are stuck in the middle with a confusing letter and fear.

Saakshi takes a photo, PDF, screenshot or text of any official-looking notice and answers, in order:

1. **Is this real?** A Trust Gate runs *before* any AI interprets the notice.
2. **What does it actually say?** In English, Hindi or Marathi.
3. **How serious is it?** Routine / Action needed / Get a professional / Likely scam.
4. **What happens if I do nothing?** A step-by-step timeline.
5. **What do I do now?** A drafted reply, document checklist, and where to respond.

A **Guardian agent** checks every claim against the notice and official sources before you see it, and shows a Trust Receipt.

**Track:** Best Apps and Agents · **Live demo:** [ADD STREAMLIT URL] · **Video:** [ADD YOUTUBE URL]

## How NVIDIA Nemotron and Nebius Token Factory are used

Every model call is a runtime call to the Nebius Token Factory API. Models are routed by difficulty, so the expensive model runs only where reasoning matters:

| Agent | Model | Job |
|---|---|---|
| Perceiver | Nemotron 3 Nano Omni | Reads photos and screenshots of notices (OCR + layout) |
| Clerk | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Extracts facts to strict JSON; flags scam patterns |
| Judge | `nvidia/Nemotron-3-Ultra-550b-a55b` | Decides severity and builds the "if you do nothing" timeline |
| Advocate | `nvidia/nemotron-3-super-120b-a12b` | Writes the explanation, reply draft and checklist |
| Guardian | `nvidia/Nemotron-3-Ultra-550b-a55b` | Verifies each claim (Chain-of-Verification) and removes unsupported ones |
| Investigator | Tavily API | Searches only official `.gov.in` sources, after personal data is redacted |

**Scam path is cheap by design:** if the Trust Gate finds a likely scam, Ultra and web search are skipped entirely.

## What makes it different

- **Verify before interpret.** Deterministic rules run first: Income Tax DIN check (mandatory since Oct 2019), the official GSTIN checksum, personal-UPI payment demands, "digital arrest" and secrecy language. The AI can raise suspicion but can never overrule a rule-based scam verdict.
- **Deadlines are never hallucinated.** A deadline is shown only if its quote appears word-for-word in the notice.
- **Dual-law aware.** Detects whether the Income-tax Act 1961 or 2025 applies.
- **Privacy first.** PAN, Aadhaar, phone numbers and emails are redacted before any web search. Nothing is stored.
- **Budget guard.** Every call's cost is metered; the app stops live calls at a hard cap, and caps output tokens per model.

## Run it locally

Requires Python 3.10+.

```bash
git clone [YOUR REPO URL]
cd saakshi
pip install -r requirements.txt
cp .env.example .env        # then paste your keys into .env
streamlit run app.py
```

Get keys from [Nebius Token Factory](https://tokenfactory.nebius.com) and [Tavily](https://app.tavily.com).

## Project structure

```
app.py                  Streamlit interface
pipeline/trust_gate.py  Deterministic authenticity rules (no AI)
pipeline/run.py         Perceive → Trust → Extract → Ground → Judge → Draft → Guard
core/llm.py             Token Factory client, model router, JSON parsing
core/budget.py          Cost meter and hard spending cap
core/prompts.py         All agent prompts
core/pii.py             Personal data redaction
samples/                Synthetic notices (no real personal data)
cache/                  Saved results so sample demos cost nothing
docs/                   Design spec and architecture
```

## Feedback on Nebius Token Factory and NVIDIA Nemotron

[Write 4–6 honest points: setup experience, API compatibility, latency of Ultra vs Nano, model naming, documentation, what you'd improve.]

## Disclaimer

Saakshi is not a lawyer or chartered accountant. For high-stakes notices, consult a professional. Free legal aid in India: NALSA 15100. Report cyber fraud: 1930 or cybercrime.gov.in.

## License

MIT
