"""Saakshi: the citizen's counter-agent for official notices."""
import datetime
import glob
import html
import json
import os
import re
import urllib.parse

import streamlit as st
import streamlit.components.v1 as components

from core import budget
from core.llm import MODELS
from pipeline import run, trust_gate

st.set_page_config(page_title="Saakshi · Is this notice real?", page_icon="🛡️", layout="wide")
SESSION_LIMIT = int(os.getenv("SESSION_LIMIT", "3"))
HERE = os.path.dirname(__file__)
E = html.escape

# ============================ STYLE ============================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;700;800&family=Archivo+Black&family=Courier+Prime&display=swap');
html, body, .stMarkdown, p, li, label, button { font-family: 'Public Sans', system-ui, sans-serif; }
.block-container { padding-top: 2.2rem; max-width: 1180px; }
:root { --scam:#C1271F; --pro:#B25A00; --act:#2756C5; --ok:#1E7A4C; --line: rgba(127,127,127,.28); }

.hero h1 { font-family: 'Archivo Black', 'Public Sans', sans-serif; font-size: clamp(2rem, 4.4vw, 3.3rem);
           line-height: 1.02; margin: 0 0 .7rem; letter-spacing: -.015em; }
.hero p { font-size: 1.1rem; max-width: 62ch; opacity: .8; margin: 0 0 .3rem; }
.helplines { font-size: .92rem; opacity: .75; }

/* Agent pipeline */
.pipe { display: flex; align-items: stretch; gap: 0; margin: .8rem 0 1.2rem; overflow-x: auto; }
.node { flex: 1; min-width: 118px; border: 1.5px solid var(--line); border-radius: 12px; padding: .65rem .7rem;
        position: relative; transition: all .3s; }
.node .ic { font-size: 1.25rem; } .node b { display: block; font-size: .95rem; margin-top: .15rem; }
.node small { opacity: .7; font-size: .76rem; display: block; line-height: 1.2; }
.link { width: 22px; align-self: center; height: 2px; background: var(--line); flex: 0 0 22px; }
.node.pending { opacity: .35; }
.node.active { border-color: var(--act); box-shadow: 0 0 0 4px rgba(39,86,197,.18); }
.node.done { border-color: var(--ok); } .node.done::after { content: '✓'; position: absolute; top: 6px; right: 9px;
        color: var(--ok); font-weight: 800; }
.node.skipped { opacity: .45; border-style: dashed; }
.pipe-msg { font-size: .92rem; opacity: .8; margin-top: -.6rem; }
@media (prefers-reduced-motion: no-preference) {
  .node.active { animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 50% { box-shadow: 0 0 0 9px rgba(39,86,197,.05); } }
  .stamp { animation: thud .4s cubic-bezier(.2,1.6,.4,1); }
  @keyframes thud { from { transform: rotate(-9deg) scale(2.2); opacity: 0; } to { transform: rotate(-9deg) scale(1); opacity: .92; } }
}

/* Paper notice with stamp */
.paper { background: #FDFDFB; color: #1d2330; border-radius: 4px; padding: 1.6rem 1.5rem 1.4rem;
         box-shadow: 0 1px 2px rgba(0,0,0,.15), 0 12px 32px -12px rgba(0,0,0,.35); position: relative;
         font-family: 'Courier Prime', 'Courier New', monospace; font-size: .86rem; line-height: 1.5;
         white-space: pre-wrap; max-height: 560px; overflow-y: auto; }
.paper mark.flag { background: rgba(193,39,31,.16); color: #8f1610; border-bottom: 2px solid #C1271F; padding: 0 2px; }
.paper mark.due { background: rgba(255,196,0,.35); color: inherit; padding: 0 2px; }
.stamp { position: absolute; top: 18px; right: 16px; font-family: 'Archivo Black', sans-serif; font-size: 1.35rem;
         padding: .3rem .8rem; border: 4px solid currentColor; border-radius: 8px; transform: rotate(-9deg);
         opacity: .92; background: rgba(253,253,251,.85); pointer-events: none; }
.legend { font-size: .8rem; opacity: .75; margin-top: .5rem; }

.c-SCAM { color: var(--scam); } .c-PROFESSIONAL { color: var(--pro); }
.c-RESPOND { color: var(--act); } .c-ROUTINE { color: var(--ok); }
.verdict { border-left: 7px solid currentColor; padding: .9rem 1.1rem; border-radius: 6px;
           background: rgba(127,127,127,.08); margin-bottom: 1rem; }
.verdict .t { font-family: 'Archivo Black', sans-serif; font-size: 1.05rem; }
.verdict p { color: inherit; font-size: 1.15rem; margin: .25rem 0 0; font-weight: 600; }

/* Trust meter */
.meter { height: 12px; border-radius: 99px; background: linear-gradient(90deg, #C1271F, #E0A100 50%, #1E7A4C);
         position: relative; margin: .4rem 0 .2rem; }
.meter i { position: absolute; top: -5px; width: 4px; height: 22px; background: currentColor; border-radius: 2px; }
.meter-row { display: flex; justify-content: space-between; font-size: .76rem; opacity: .65; }

.facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem; margin: 1rem 0; }
.fact { border: 1px solid var(--line); border-radius: 10px; padding: .6rem .75rem; }
.fact small { opacity: .65; display: block; font-size: .78rem; }
.fact b { font-size: 1.12rem; display: block; line-height: 1.25; }
.fact em { font-size: .74rem; opacity: .7; font-style: normal; }

.tl { margin: .4rem 0 0 .3rem; }
.tl .row { display: grid; grid-template-columns: 18px 1fr; gap: .8rem; padding-bottom: 1rem; position: relative; }
.tl .dot { width: 14px; height: 14px; border-radius: 50%; border: 3px solid currentColor; margin-top: 4px; }
.tl .row:not(:last-child)::before { content: ''; position: absolute; left: 6px; top: 20px; bottom: 0;
        width: 2px; background: var(--line); }
.tl b { display: block; }
.tag { font-size: .7rem; padding: 1px 8px; border-radius: 99px; border: 1px solid var(--line); opacity: .8; margin-left: .3rem; }
</style>
""", unsafe_allow_html=True)

STAMP = {"SCAM": "LIKELY SCAM", "PROFESSIONAL": "GET A PROFESSIONAL", "RESPOND": "ACTION NEEDED", "ROUTINE": "ROUTINE"}
STEPS = [("🛡️", "Trust Gate", "Rule checks, no AI"), ("📄", "Clerk", "Nemotron Nano"),
         ("🔎", "Investigator", "Tavily, gov.in only"), ("⚖️", "Judge", "Nemotron Ultra"),
         ("✍️", "Advocate", "Nemotron Super"), ("✅", "Guardian", "Nemotron Ultra")]
STEP_KEYS = ["genuine", "Extracting", "Searching", "Judging", "Writing|Explaining", "Guardian"]
LANG_CODE = {"English": "en-IN", "Hindi": "hi-IN", "Marathi": "mr-IN"}
SAMPLE_INFO = {
    "1_income_tax_intimation.txt": ("🧾", "Income tax intimation", "A ₹4,820 demand from the tax portal"),
    "2_gst_show_cause.txt": ("🏪", "GST show-cause notice", "A small business told it over-claimed credit"),
    "3_bank_sarfaesi_notice.txt": ("🏦", "Bank recovery notice", "A home loan marked as bad debt"),
    "4_fake_cbi_digital_arrest.txt": ("🚨", "'CBI digital arrest' letter", "Sent on WhatsApp to a retired teacher"),
}


def pipeline_html(states, msg=""):
    parts = []
    for i, ((ic, name, sub), s) in enumerate(zip(STEPS, states)):
        if i:
            parts.append('<div class="link"></div>')
        note = "Skipped to save cost" if s == "skipped" else sub
        parts.append(f'<div class="node {s}"><span class="ic">{ic}</span><b>{name}</b><small>{note}</small></div>')
    m = f'<div class="pipe-msg">{E(msg)}</div>' if msg else ""
    return f'<div class="pipe">{"".join(parts)}</div>{m}'


def highlight(text, facts):
    """Mark scam phrases in red and the verified deadline in yellow, on the original notice."""
    spans = []
    for pattern, _, _ in trust_gate.RED_FLAGS:
        for m in re.finditer(pattern.replace(" ", r"\s+"), text, re.I):
            spans.append((m.start(), m.end(), "flag"))
    q = facts.get("deadline_quote")
    if facts.get("deadline_verified") and q:
        idx = text.find(q)
        if idx >= 0:
            spans.append((idx, idx + len(q), "due"))
    spans.sort()
    out, pos = [], 0
    for s, e, cls in spans:
        if s < pos:
            continue
        out += [E(text[pos:s]), f'<mark class="{cls}">{E(text[s:e])}</mark>']
        pos = e
    out.append(E(text[pos:]))
    return "".join(out)


def trust_score(t):
    n = len(t["red_flags"])
    if t["status"] == "SCAM_LIKELY":
        return max(4, 22 - 3 * n)
    if t["status"] == "UNVERIFIED":
        return 48
    return max(62, 94 - 8 * n)


def days_left(iso):
    try:
        return (datetime.date.fromisoformat(iso) - datetime.date.today()).days
    except Exception:
        return None


def read_aloud(text, lang):
    try:
        _speak_button(text, lang)
    except Exception:
        pass  # older/newer Streamlit without this component: skip the button


def _speak_button(text, lang):
    components.html(f"""
<button id="b" style="font:600 15px 'Public Sans',system-ui,sans-serif;padding:9px 16px;border-radius:10px;
 border:1.5px solid #2756C5;background:#2756C5;color:#fff;cursor:pointer">🔊 Read this to me</button>
<button id="s" style="font:600 15px 'Public Sans',system-ui,sans-serif;padding:9px 14px;border-radius:10px;
 border:1.5px solid #888;background:transparent;color:#888;cursor:pointer;margin-left:6px">Stop</button>
<script>
const t = {json.dumps(text)}, lang = "{lang}";
document.getElementById('b').onclick = () => {{ speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(t); u.lang = lang; u.rate = 0.92;
  const v = speechSynthesis.getVoices().find(v => v.lang === lang); if (v) u.voice = v;
  speechSynthesis.speak(u); }};
document.getElementById('s').onclick = () => speechSynthesis.cancel();
</script>""", height=50)


# ============================ SIDEBAR ============================
with st.sidebar:
    language = st.selectbox("Explain it to me in", list(LANG_CODE))
    st.caption("Saakshi checks if a notice is genuine, explains it, and drafts your reply. It is not a lawyer or CA.")
    st.divider()
    used, cap = budget.spent(), budget.HARD_CAP_USD
    st.caption("Live AI budget used")
    st.progress(min(used / cap, 1.0), text=f"\\${used:.2f} of \\${cap:.2f}")
    st.divider()
    st.caption("Runs on NVIDIA Nemotron via Nebius Token Factory, with Tavily search")
    for tier in ["omni", "nano", "super", "ultra"]:
        st.caption(f"• `{MODELS[tier]}`")

# ============================ HERO ============================
st.markdown("""<div class="hero"><h1>Got a scary notice?<br>Check it before you act.</h1>
<p>Saakshi checks whether it's genuine, tells you what it really means and what happens if you ignore it,
then drafts your reply. Six AI agents, every claim verified.</p>
<p class="helplines">Cyber fraud helpline <b>1930</b> &nbsp;&nbsp; Free legal aid <b>15100</b></p></div>""",
            unsafe_allow_html=True)

text, source = None, None
tab_sample, tab_upload = st.tabs(["Try a real-world example", "Check my own notice"])

with tab_sample:
    cols = st.columns(4)
    for col, path in zip(cols, sorted(glob.glob(os.path.join(HERE, "samples", "*.txt")))):
        name = os.path.basename(path)
        ic, title, hint = SAMPLE_INFO.get(name, ("📄", name, ""))
        with col:
            with st.container(border=True):
                st.markdown(f"### {ic}\n**{title}**")
                st.caption(hint)
                if st.button("Check it", key=f"s_{name}", use_container_width=True):
                    with open(path, encoding="utf-8") as f:
                        text, source = f.read(), "sample"

with tab_upload:
    c1, c2 = st.columns([1, 1])
    with c1:
        up = st.file_uploader("Photo, screenshot, PDF or text file", type=["png", "jpg", "jpeg", "pdf", "txt"])
    with c2:
        pasted = st.text_area("Or paste the text, including WhatsApp or SMS messages", height=120)
    st.caption(f"Nothing is stored. Personal numbers are removed before any web search. "
               f"{SESSION_LIMIT} free checks per visit.")
    if st.button("Check my notice", type="primary"):
        runs = st.session_state.get("runs", 0)
        if runs >= SESSION_LIMIT:
            st.error(f"You've used your {SESSION_LIMIT} free checks for this visit. The examples still work.")
        elif up is None and not pasted.strip():
            st.warning("Add a file or paste the notice text first.")
        elif up is not None and up.size > 4 * 1024 * 1024:
            st.warning("That file is over 4 MB. Upload a smaller photo or screenshot.")
        else:
            st.session_state["runs"] = runs + 1
            source = "upload"
            if pasted.strip():
                text = pasted
            else:
                pre = []
                try:
                    with st.spinner("Reading your notice with Nemotron Omni…"):
                        text = run.perceive(up.getvalue(), up.name, pre)
                    st.session_state["pre_trace"] = pre
                except Exception as e:
                    st.error(f"Couldn't read that file: {e}")

# ============================ RUN ============================
if text:
    trace = st.session_state.pop("pre_trace", []) if source == "upload" else []
    ph = st.empty()
    ph.markdown(pipeline_html(["active"] + ["pending"] * 5, "Starting…"), unsafe_allow_html=True)

    def on_progress(msg):
        idx = max(i for i, k in enumerate(STEP_KEYS) if re.search(k, msg) or i == 0)
        states = ["done"] * idx + ["active"] + ["pending"] * (5 - idx)
        if "Explaining" in msg:
            states[2] = states[3] = "skipped"
        ph.markdown(pipeline_html(states, msg + "…"), unsafe_allow_html=True)

    try:
        result = run.analyze(text, language, progress=on_progress, trace=trace)
        st.session_state.update(result=result, text=text)
    except budget.BudgetExceeded as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Something went wrong while analysing: {e}. Try again, or try an example.")
    ph.empty()

# ============================ RESULTS ============================
r = st.session_state.get("result")
if r:
    v, a, facts, trust = r["verdict"], r["action"], r["facts"], r["trust"]
    tier = v.get("tier") if v.get("tier") in STAMP else "RESPOND"
    final = ["done"] * 6 if r.get("guard") else ["done", "done", "skipped", "skipped", "done", "skipped"]
    st.markdown(pipeline_html(final), unsafe_allow_html=True)
    if r.get("from_cache"):
        st.caption("Instant replay of an earlier full run of this exact notice.")

    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.markdown(f'<div class="paper"><div class="stamp c-{tier}">{STAMP[tier]}</div>'
                    f'{highlight(st.session_state.get("text", ""), facts)}</div>', unsafe_allow_html=True)
        st.markdown('<div class="legend"><mark style="background:rgba(193,39,31,.18)">red</mark> warning sign '
                    '&nbsp; <mark style="background:rgba(255,196,0,.4)">yellow</mark> deadline, '
                    'quoted word-for-word</div>', unsafe_allow_html=True)

    with right:
        st.markdown(f'<div class="verdict c-{tier}"><span class="t">{STAMP[tier].capitalize()}</span>'
                    f'<p>{E(v.get("one_line", ""))}</p></div>', unsafe_allow_html=True)

        score = trust_score(trust)
        st.markdown(f'<div><b>Trust score: {score}/100</b> '
                    f'<span class="tag">{E(trust["status"].replace("_", " ").lower())}</span>'
                    f'<div class="meter c-{tier}"><i style="left:calc({score}% - 2px)"></i></div>'
                    f'<div class="meter-row"><span>Likely fake</span><span>Likely genuine</span></div></div>',
                    unsafe_allow_html=True)

        amt = facts.get("amount_demanded_inr")
        amt_s = f"₹{amt:,.0f}" if isinstance(amt, (int, float)) else "Not stated"
        dl, d_note = "Read the notice", "Shown only if quoted in the notice"
        if facts.get("deadline_verified") and facts.get("response_deadline"):
            n = days_left(facts["response_deadline"])
            dl = facts["response_deadline"] if n is None else (f"{n} days left" if n >= 0 else f"{-n} days ago")
            d_note = f"Due {facts['response_deadline']}"
        law = {"IT_ACT_1961": "IT Act 1961", "IT_ACT_2025": "IT Act 2025"}.get(facts.get("law_regime"), "")
        st.markdown(f'''<div class="facts">
          <div class="fact"><small>Notice</small><b>{E(facts.get("notice_type") or "Unknown")}</b><em>{E(law)}</em></div>
          <div class="fact"><small>Amount</small><b>{amt_s}</b><em>{E(facts.get("issuing_authority") or "")[:40]}</em></div>
          <div class="fact"><small>Deadline</small><b>{E(dl)}</b><em>{E(d_note)}</em></div></div>''',
                    unsafe_allow_html=True)

        read_aloud(f'{v.get("one_line", "")} {a.get("explanation", "")}', LANG_CODE[language])

        if tier == "SCAM":
            warn = ("⚠️ Scam alert: fake 'CBI / police / digital arrest' notices are going around. No agency "
                    "arrests anyone on a video call or asks for money transfers. Don't pay. Report at 1930. "
                    "Checked with Saakshi.")
            st.link_button("Warn my family on WhatsApp", "https://wa.me/?text=" + urllib.parse.quote(warn),
                           use_container_width=True, type="primary")
        if a.get("where_to_respond"):
            st.info(a["where_to_respond"])

    t1, t2, t3, t4, t5 = st.tabs(["What it means", "If you do nothing", "Your reply", "Trust receipt", "How the agents worked"])
    with t1:
        st.write(a.get("explanation", ""))
        if trust["red_flags"]:
            st.markdown("**Warning signs found**")
            for fl in trust["red_flags"]:
                st.markdown(f"- {fl['flag']}")
        if a.get("checklist"):
            st.markdown("**What you'll need**")
            for item in a["checklist"]:
                st.markdown(f"- {item}")
        st.caption(trust["how_to_verify_officially"])
    with t2:
        rows = "".join(f'<div class="row c-{tier}"><span class="dot"></span><div><b>{E(t.get("when", ""))}'
                       f'<span class="tag">{E(t.get("source_tag", "GENERAL").lower())}</span></b>'
                       f'<span style="color:var(--text-color, inherit)">{E(t.get("what_happens", ""))}</span></div></div>'
                       for t in v.get("timeline", []))
        st.markdown(f'<div class="tl">{rows}</div>', unsafe_allow_html=True)
        st.caption("Tags show where each point comes from: the notice itself, an official source, or general guidance.")
    with t3:
        if a.get("reply_draft"):
            st.code(a["reply_draft"], language=None)
            st.download_button("Download reply", a["reply_draft"], file_name="saakshi_reply.txt")
            st.caption("Fill in the [placeholders] and check every detail before sending.")
        else:
            st.write("No reply needed. Don't respond to scammers. Report it at 1930 or cybercrime.gov.in.")
    with t4:
        g = r.get("guard")
        if g:
            claims = g.get("claims", [])
            kept = sum(1 for c in claims if c.get("kept", True))
            m1, m2, m3 = st.columns(3)
            m1.metric("Claims verified", kept)
            m2.metric("Claims removed", len(claims) - kept)
            m3.metric("Confidence", str(g.get("confidence", "?")).capitalize())
            for c in claims:
                mark = "✅" if c.get("kept", True) else "❌ Removed"
                st.markdown(f"{mark} **{c.get('tag')}**: {c.get('text')}")
                if c.get("evidence"):
                    st.caption(c["evidence"])
        else:
            st.write("For likely scams, Saakshi relies on rule-based evidence quoted directly from the notice, "
                     "so no AI verification step is needed.")
        if r.get("sources"):
            st.markdown("**Official sources checked**")
            for s_ in r["sources"]:
                st.markdown(f"- [{s_['title']}]({s_['url']})")
    with t5:
        tr = r["trace"]
        st.table([{"Step": t["step"], "Model": t["model"], "Tokens in / out": f"{t['tokens_in']} / {t['tokens_out']}",
                   "Seconds": t["seconds"]} for t in tr])
        st.caption(f"Total time {sum(t['seconds'] for t in tr):.0f}s, estimated cost "
                   f"${sum(t.get('cost_usd', 0) for t in tr):.4f}. Cheap models handle easy steps; "
                   f"Ultra is used only for judgment and verification.")

    st.caption("Saakshi is not a lawyer or chartered accountant. For notices marked 'Get a professional', "
               "consult one. Free legal aid: NALSA 15100.")