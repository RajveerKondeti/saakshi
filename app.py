"""Saakshi: the citizen's counter-agent for official notices. (Premium UI)"""
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

st.set_page_config(page_title="Saakshi · Is this notice real?", page_icon="🛡️",
                   layout="wide", initial_sidebar_state="collapsed")
SESSION_LIMIT = int(os.getenv("SESSION_LIMIT", "3"))
HERE = os.path.dirname(__file__)
E = html.escape

# =============================================================== DESIGN TOKENS + GLOBAL STYLE
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Instrument+Serif&family=Courier+Prime&display=swap');
:root{
  --ink:#070A12; --panel:rgba(255,255,255,.035); --panel2:rgba(255,255,255,.06);
  --line:rgba(255,255,255,.09); --text:#E9EDF5; --muted:#8C96AA;
  --gold:#E8B84A; --teal:#39D3A8; --red:#FF5B4E; --indigo:#7B8CFF; --amber:#FFA53D;
}
/* ---------- base ---------- */
.stApp{background:var(--ink); color:var(--text);}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp div{font-family:'Geist',system-ui,sans-serif;}
.stApp p, .stApp li, [data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"]{color:var(--text);}
[data-testid="stCaptionContainer"], .stApp small{color:var(--muted)!important;}
header[data-testid="stHeader"]{background:transparent;}
[data-testid="stToolbar"], [data-testid="stDecoration"]{display:none!important;}
[data-testid="stSidebar"]{display:none;}
[data-testid="stSidebarCollapsedControl"]{display:none;}
.block-container{max-width:1180px; padding-top:4.6rem; position:relative; z-index:2;}

/* ---------- ambient light rays (fixed, behind everything) ---------- */
.rays{position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden;}
.rays::before{content:''; position:absolute; left:50%; top:-35vh; width:140vw; height:120vh; transform:translateX(-50%);
  background:conic-gradient(from 180deg at 50% 0%, transparent 38%, rgba(123,140,255,.10) 44%, transparent 47%,
  rgba(232,184,74,.07) 50%, transparent 53%, rgba(57,211,168,.08) 56%, transparent 62%);
  filter:blur(18px); transform-origin:50% 0;}
.rays::after{content:''; position:absolute; inset:0;
  background:radial-gradient(60% 40% at 50% 0%, rgba(123,140,255,.12), transparent 70%),
             radial-gradient(30% 30% at 85% 60%, rgba(57,211,168,.05), transparent 70%);}
@media (prefers-reduced-motion:no-preference){ .rays::before{animation:sway 14s ease-in-out infinite alternate;} }
@keyframes sway{from{transform:translateX(-50%) rotate(-4deg);} to{transform:translateX(-50%) rotate(4deg);}}
.grain{position:fixed; inset:0; z-index:1; pointer-events:none; opacity:.05;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence baseFrequency='.9' numOctaves='2'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");}

/* ---------- navbar with progressive blur ---------- */
.nav{position:fixed; top:0; left:0; right:0; height:64px; z-index:999; display:flex; align-items:center;
  justify-content:space-between; padding:0 clamp(16px,4vw,48px);}
.nav::before{content:''; position:absolute; inset:0 0 -28px 0; z-index:-1; backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px); background:linear-gradient(rgba(7,10,18,.85), rgba(7,10,18,0));
  mask-image:linear-gradient(to bottom, #000 55%, transparent); -webkit-mask-image:linear-gradient(to bottom,#000 55%,transparent);}
.brand{display:flex; align-items:center; gap:.6rem; font-weight:600; letter-spacing:.01em; font-size:1.05rem; color:var(--text);}
.brand .seal{width:26px; height:26px; border-radius:50%; background:radial-gradient(circle at 35% 30%, #FFE7A3, var(--gold) 45%, #8a6214);
  box-shadow:0 0 18px rgba(232,184,74,.45), inset 0 -2px 4px rgba(0,0,0,.35);}
.navlinks{display:flex; gap:1.4rem; font-size:.88rem; color:var(--muted);}
.navlinks b{color:var(--text); font-weight:600;}
.pill{border:1px solid var(--line); border-radius:999px; padding:.3rem .8rem; background:var(--panel); font-size:.82rem; color:var(--muted);}
.pill i{display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--teal); margin-right:.45rem;
  box-shadow:0 0 10px var(--teal);}
@media (max-width:760px){ .navlinks{display:none;} }

/* ---------- section titles ---------- */
.kick{color:var(--muted); font-size:.9rem; margin:2.6rem 0 .3rem;}
.stApp .h2{font-family:'Instrument Serif',Georgia,serif; font-size:clamp(1.9rem,3.2vw,2.6rem); line-height:1.05; margin:0 0 1.1rem; color:var(--text); font-weight:400;}

/* ---------- bento ---------- */
.bento{display:grid; grid-template-columns:repeat(6,1fr); grid-auto-rows:minmax(150px,auto); gap:14px; perspective:1200px;}
.tile{grid-column:span 2; border:1px solid var(--line); border-radius:20px; padding:1.2rem 1.25rem; position:relative; overflow:hidden;
  background:linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.015)); transition:transform .35s cubic-bezier(.2,.8,.2,1), border-color .35s;}
.tile:hover{transform:rotateX(4deg) rotateY(-4deg) translateY(-3px); border-color:rgba(255,255,255,.2);}
.tile h4{margin:.2rem 0 .35rem; font-size:1.06rem; font-weight:600; color:var(--text);}
.tile p{margin:0; color:var(--muted)!important; font-size:.92rem; line-height:1.45; max-width:46ch;}
.tile.big{grid-column:span 4; grid-row:span 2;}
.tile.wide{grid-column:span 3;}
.tile .glow{position:absolute; width:260px; height:260px; border-radius:50%; filter:blur(60px); opacity:.35; right:-80px; bottom:-90px;}
.ic{font-size:1.4rem;}
@media (max-width:900px){ .bento{grid-template-columns:1fr 1fr;} .tile,.tile.big,.tile.wide{grid-column:span 2; grid-row:auto;} }
.rulelist{display:flex; flex-wrap:wrap; gap:.45rem; margin-top:1rem;}
.rule{font-size:.8rem; border:1px solid var(--line); border-radius:999px; padding:.25rem .65rem; color:var(--text); background:rgba(255,255,255,.03);}
.rule.r{border-color:rgba(255,91,78,.4); color:#ffb3ad;} .rule.g{border-color:rgba(57,211,168,.4); color:#9ff0d8;}
.agents-mini{display:grid; grid-template-columns:repeat(3,1fr); gap:6px; margin-top:.9rem;}
.agents-mini span{font-size:.74rem; border:1px solid var(--line); border-radius:10px; padding:.35rem .45rem; color:var(--muted); text-align:center;}

/* ---------- Streamlit widgets restyled ---------- */
.stTabs [data-baseweb="tab-list"]{gap:.4rem; border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{background:transparent; color:var(--muted); border-radius:10px 10px 0 0; padding:.5rem .9rem;}
.stTabs [aria-selected="true"]{color:var(--text)!important;}
.stTabs [data-baseweb="tab-highlight"]{background:linear-gradient(90deg,var(--indigo),var(--teal));}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line)!important; border-radius:18px!important;
  background:linear-gradient(180deg, rgba(255,255,255,.045), rgba(255,255,255,.012)); transition:transform .3s, border-color .3s;}
[data-testid="stVerticalBlockBorderWrapper"]:hover{transform:translateY(-3px); border-color:rgba(255,255,255,.22)!important;}
.stButton>button, .stDownloadButton>button, .stLinkButton>a{border-radius:999px!important; border:1px solid rgba(255,255,255,.16)!important;
  background:rgba(255,255,255,.04)!important; color:var(--text)!important; font-weight:500; transition:all .25s;}
.stButton>button:hover, .stDownloadButton>button:hover, .stLinkButton>a:hover{border-color:var(--teal)!important;
  box-shadow:0 0 0 4px rgba(57,211,168,.12), 0 0 24px rgba(57,211,168,.25); color:#fff!important;}
.stButton>button[kind="primary"], .stLinkButton>a[kind="primary"]{background:linear-gradient(135deg,#8E9BFF,#5B6CF0)!important;
  border-color:transparent!important; color:#fff!important; box-shadow:0 8px 30px -8px rgba(91,108,240,.7);}
.stTextArea textarea, [data-testid="stFileUploaderDropzone"], [data-baseweb="select"] > div, [data-baseweb="select"] div{background-color:#121725!important;
  border:1px solid var(--line)!important; border-radius:14px!important; color:var(--text)!important;}
[data-testid="stFileUploaderDropzone"] *{color:var(--muted)!important;}
[data-baseweb="select"] *{color:var(--text)!important;} [data-baseweb="popover"] li{background:#121725; color:var(--text);}
.stTextArea textarea{background-color:#0E1320!important;}
[data-testid="stMetricValue"]{color:var(--text);} [data-testid="stMetricLabel"] p{color:var(--muted)!important;}
.stAlert{border-radius:14px;}
h3{color:var(--text)!important;}

/* ---------- agent pipeline ---------- */
.pipe{display:flex; align-items:stretch; margin:1.4rem 0 1.4rem; overflow-x:auto; padding:6px 2px 10px;}
.node{flex:1; min-width:128px; border:1px solid var(--line); border-radius:16px; padding:.75rem .8rem; position:relative;
  background:rgba(255,255,255,.03); transition:all .4s;}
.node .ic{font-size:1.2rem;} .node b{display:block; font-size:.93rem; margin-top:.2rem; color:var(--text);}
.node small{color:var(--muted); font-size:.74rem; display:block; line-height:1.25;}
.link{flex:0 0 26px; align-self:center; height:2px; background:var(--line); position:relative; overflow:hidden;}
.link.on{background:linear-gradient(90deg, transparent, var(--teal), transparent); background-size:200% 100%;}
.node.pending{opacity:.32;}
.node.active{border-color:var(--indigo); background:rgba(123,140,255,.08); box-shadow:0 0 0 1px rgba(123,140,255,.4), 0 0 34px -6px rgba(123,140,255,.7);}
.node.done{border-color:rgba(57,211,168,.45); background:rgba(57,211,168,.05);}
.node.done::after{content:'✓'; position:absolute; top:8px; right:10px; color:var(--teal); font-weight:700;}
.node.skipped{opacity:.45; border-style:dashed;}
.pipe-msg{color:var(--muted); font-size:.9rem; margin-top:-.8rem;}
@media (prefers-reduced-motion:no-preference){
  .node.active{animation:breathe 1.4s ease-in-out infinite;}
  .link.on{animation:flow 1.6s linear infinite;}
  .stamp{animation:thud .45s cubic-bezier(.2,1.6,.4,1);}
}
@keyframes breathe{50%{box-shadow:0 0 0 1px rgba(123,140,255,.5), 0 0 50px -4px rgba(123,140,255,.9);}}
@keyframes flow{to{background-position:-200% 0;}}
@keyframes thud{from{transform:rotate(-9deg) scale(2.3); opacity:0;} to{transform:rotate(-9deg) scale(1); opacity:.95;}}

/* ---------- results ---------- */
.paperwrap{position:relative; padding:18px; border-radius:22px; background:radial-gradient(80% 60% at 50% 0%, rgba(255,255,255,.08), transparent 70%);}
.paper{background:#FBFAF6; color:#1c2230; border-radius:6px; padding:1.7rem 1.5rem 1.4rem; position:relative;
  box-shadow:0 30px 60px -20px rgba(0,0,0,.8), 0 0 0 1px rgba(255,255,255,.06); font-family:'Courier Prime','Courier New',monospace;
  font-size:.86rem; line-height:1.55; white-space:pre-wrap; max-height:600px; overflow-y:auto;}
.paper mark.flag{background:rgba(255,91,78,.18); color:#a3150c; border-bottom:2px solid #E23B2E; padding:0 2px;}
.paper mark.due{background:rgba(255,196,0,.4); color:inherit; padding:0 2px;}
.stamp{position:absolute; top:20px; right:18px; font-family:'Geist',sans-serif; font-weight:700; font-size:1.25rem; letter-spacing:.03em;
  padding:.3rem .85rem; border:4px double currentColor; border-radius:10px; transform:rotate(-9deg); opacity:.95;
  background:rgba(251,250,246,.85); pointer-events:none;}
.legend{font-size:.8rem; color:var(--muted); margin-top:.6rem;}
.legend mark{padding:0 4px; border-radius:3px; color:#1c2230;}
.c-SCAM{color:var(--red);} .c-PROFESSIONAL{color:var(--amber);} .c-RESPOND{color:var(--indigo);} .c-ROUTINE{color:var(--teal);}
.paper .c-SCAM{color:#D7261B;} .paper .c-PROFESSIONAL{color:#B25A00;} .paper .c-RESPOND{color:#3348C9;} .paper .c-ROUTINE{color:#16865A;}
.verdict{border:1px solid currentColor; border-radius:20px; padding:1.1rem 1.25rem; position:relative; overflow:hidden;
  background:linear-gradient(135deg, rgba(255,255,255,.05), rgba(255,255,255,.01));}
.verdict::before{content:''; position:absolute; inset:0; background:currentColor; opacity:.07;}
.verdict .t{font-size:.85rem; font-weight:600; position:relative;}
.verdict p{color:var(--text)!important; font-family:'Instrument Serif',Georgia,serif; font-size:1.55rem; line-height:1.18; margin:.35rem 0 0; position:relative;}
.score{margin:1.1rem 0 .2rem; display:flex; justify-content:space-between; align-items:baseline;}
.score b{font-size:2.2rem; font-weight:600; color:var(--text);} .score span{color:var(--muted); font-size:.85rem;}
.meter{height:10px; border-radius:99px; background:linear-gradient(90deg,var(--red),var(--amber) 50%,var(--teal)); position:relative; opacity:.9;}
.meter i{position:absolute; top:-6px; width:22px; height:22px; border-radius:50%; background:#fff; border:4px solid var(--ink);
  box-shadow:0 0 0 2px currentColor, 0 0 16px currentColor; transform:translateX(-50%);}
.meter-row{display:flex; justify-content:space-between; font-size:.74rem; color:var(--muted); margin-top:.45rem;}
.facts{display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:1.1rem 0;}
.fact{border:1px solid var(--line); border-radius:16px; padding:.75rem .85rem; background:var(--panel);}
.fact small{display:block; font-size:.76rem;} .fact b{display:block; font-size:1.08rem; line-height:1.25; margin:.15rem 0; color:var(--text);}
.fact em{font-style:normal; font-size:.74rem; color:var(--muted);}
@media (max-width:700px){ .facts{grid-template-columns:1fr;} }
.tl .row{display:grid; grid-template-columns:20px 1fr; gap:.9rem; padding-bottom:1.1rem; position:relative;}
.tl .dot{width:14px; height:14px; border-radius:50%; border:3px solid currentColor; margin-top:5px; box-shadow:0 0 12px currentColor;}
.tl .row:not(:last-child)::before{content:''; position:absolute; left:6px; top:22px; bottom:0; width:2px; background:var(--line);}
.tl b{display:block; color:var(--text);} .tl .txt{color:var(--muted);}
.tag{font-size:.68rem; padding:1px 8px; border-radius:99px; border:1px solid var(--line); color:var(--muted); margin-left:.4rem; font-weight:500;}
.flags{display:grid; gap:8px;} .flagc{border:1px solid rgba(255,91,78,.3); background:rgba(255,91,78,.06); border-radius:14px; padding:.65rem .8rem;}
.flagc b{color:#ffc2bd;} .flagc small{display:block; margin-top:.2rem;}

/* ---------- footer ---------- */
.foot{margin-top:4.5rem; border-top:1px solid var(--line); padding-top:2.2rem; position:relative;}
.foot-grid{display:grid; grid-template-columns:1.4fr 1fr 1fr 1fr; gap:1.5rem;}
.foot h5{font-size:.85rem; color:var(--muted); font-weight:500; margin:0 0 .6rem;}
.foot p, .foot li{font-size:.9rem; color:var(--text); margin:.2rem 0; list-style:none;}
.foot ul{padding:0; margin:0;}
.stApp .wordmark{font-family:'Instrument Serif',Georgia,serif; font-size:clamp(4rem,15vw,11rem); line-height:.85; margin-top:2rem;
  background:linear-gradient(180deg, rgba(255,255,255,.16), rgba(255,255,255,0)); -webkit-background-clip:text; background-clip:text; color:transparent;
  user-select:none; letter-spacing:-.02em;}
.bar{height:6px; border-radius:99px; background:rgba(255,255,255,.08); overflow:hidden; margin-top:.4rem;}
.bar span{display:block; height:100%; background:linear-gradient(90deg,var(--teal),var(--indigo));}
@media (max-width:800px){ .foot-grid{grid-template-columns:1fr 1fr;} }
</style>
<div class="rays"></div><div class="grain"></div>
""", unsafe_allow_html=True)

# =============================================================== CONSTANTS
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


# =============================================================== HELPERS
def pipeline_html(states, msg=""):
    parts = []
    for i, ((ic, name, sub), s) in enumerate(zip(STEPS, states)):
        if i:
            on = "on" if s in ("done", "active") else ""
            parts.append(f'<div class="link {on}"></div>')
        note = "Skipped to save cost" if s == "skipped" else sub
        parts.append(f'<div class="node {s}"><span class="ic">{ic}</span><b>{name}</b><small>{note}</small></div>')
    m = f'<div class="pipe-msg">{E(msg)}</div>' if msg else ""
    return f'<div class="pipe">{"".join(parts)}</div>{m}'


def highlight(text, facts):
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
        components.html(f"""
<style>body{{margin:0;font-family:Geist,system-ui,sans-serif}}
button{{font:600 14px Geist,system-ui,sans-serif;padding:10px 18px;border-radius:999px;cursor:pointer;transition:.25s}}
#b{{border:0;color:#fff;background:linear-gradient(135deg,#8E9BFF,#5B6CF0);box-shadow:0 8px 26px -8px rgba(91,108,240,.8)}}
#s{{border:1px solid rgba(255,255,255,.18);background:transparent;color:#C9D0DE;margin-left:6px}}
.w{{display:inline-flex;gap:3px;margin-left:8px;vertical-align:middle;height:14px;align-items:flex-end}}
.w i{{width:3px;background:#fff;border-radius:2px;height:4px}}
.on .w i{{animation:eq .8s ease-in-out infinite}} .w i:nth-child(2){{animation-delay:.15s}} .w i:nth-child(3){{animation-delay:.3s}}
@keyframes eq{{50%{{height:14px}}}}</style>
<button id="b">🔊 Read this to me<span class="w"><i></i><i></i><i></i></span></button><button id="s">Stop</button>
<script>
const t={json.dumps(text)}, lang="{lang}", b=document.getElementById('b');
b.onclick=()=>{{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(t);u.lang=lang;u.rate=.92;
 const v=speechSynthesis.getVoices().find(v=>v.lang===lang); if(v)u.voice=v;
 u.onend=()=>b.classList.remove('on'); b.classList.add('on'); speechSynthesis.speak(u);}};
document.getElementById('s').onclick=()=>{{speechSynthesis.cancel();b.classList.remove('on');}};
</script>""", height=52)
    except Exception:
        pass


def hero():
    """Interactive 3D hero: a stack of notices that tilts with the cursor, scanned by a light beam."""
    try:
        components.html("""
<!doctype html><html><head><style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Instrument+Serif&family=Courier+Prime&display=swap');
*{box-sizing:border-box} html,body{margin:0;background:transparent;color:#E9EDF5;font-family:Geist,system-ui,sans-serif;overflow:hidden}
.wrap{display:grid;grid-template-columns:1.1fr 1fr;align-items:center;gap:24px;height:470px;padding:0 4px}
h1{font-family:'Instrument Serif',Georgia,serif;font-weight:400;font-size:clamp(40px,5.4vw,72px);line-height:.98;margin:14px 0 16px;letter-spacing:-.01em}
p.sub{color:#A3ACBE;font-size:17px;line-height:1.55;max-width:46ch;margin:0 0 22px}
.chip{display:inline-flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,.1);border-radius:999px;padding:6px 12px;font-size:13px;color:#C9D0DE;background:rgba(255,255,255,.03)}
.chip i{width:7px;height:7px;border-radius:50%;background:#39D3A8;box-shadow:0 0 10px #39D3A8}
.lines{display:flex;gap:10px;flex-wrap:wrap}
.lines div{border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:10px 14px;background:rgba(255,255,255,.03)}
.lines small{display:block;color:#8C96AA;font-size:12px} .lines b{font-size:20px;font-weight:600}
.stage{height:440px;perspective:1100px;display:grid;place-items:center;position:relative}
.beam{position:absolute;left:50%;top:-40px;width:420px;height:520px;transform:translateX(-50%);pointer-events:none;
 background:conic-gradient(from 180deg at 50% 0%,transparent 42%,rgba(232,184,74,.16) 48%,rgba(255,255,255,.22) 50%,rgba(232,184,74,.16) 52%,transparent 58%);filter:blur(8px)}
.stack{position:relative;width:250px;height:330px;transform-style:preserve-3d;transition:transform .25s ease-out;transform:rotateX(14deg) rotateY(-22deg)}
.doc{position:absolute;inset:0;border-radius:6px;background:#FBFAF6;box-shadow:0 40px 70px -25px rgba(0,0,0,.9);padding:22px 20px;color:#1c2230;
 font-family:'Courier Prime',monospace;font-size:10px;line-height:1.5;overflow:hidden}
.d3{transform:translateZ(-90px) translateX(34px) translateY(-22px) rotateZ(6deg);background:#E9E6DD;opacity:.75}
.d2{transform:translateZ(-45px) translateX(16px) translateY(-10px) rotateZ(3deg);background:#F2F0E9}
.d1{transform:translateZ(0)}
.l{height:6px;border-radius:3px;background:#D8D4C8;margin:7px 0} .l.s{width:55%} .l.m{width:78%} .l.r{background:rgba(226,59,46,.35)}
.hd{font-weight:700;font-size:11px;letter-spacing:.06em;margin-bottom:10px}
.scan{position:absolute;left:0;right:0;height:46px;top:-50px;background:linear-gradient(180deg,transparent,rgba(57,211,168,.35),transparent);
 border-bottom:1.5px solid rgba(57,211,168,.9);animation:scan 3.2s cubic-bezier(.6,0,.4,1) infinite}
@keyframes scan{0%{top:-50px}70%,100%{top:340px}}
.stamp{position:absolute;right:14px;bottom:44px;font:700 15px Geist,sans-serif;color:#D7261B;border:3px double #D7261B;border-radius:8px;
 padding:5px 10px;transform:rotate(-10deg) translateZ(30px);opacity:0;animation:stamp 6.4s infinite}
@keyframes stamp{0%,40%{opacity:0;transform:rotate(-10deg) scale(2)}46%,92%{opacity:.95;transform:rotate(-10deg) scale(1)}100%{opacity:0}}
.seal{position:absolute;left:-26px;top:-26px;width:64px;height:64px;border-radius:50%;transform:translateZ(60px);
 background:radial-gradient(circle at 35% 30%,#FFF1C2,#E8B84A 45%,#7d560f);box-shadow:0 14px 30px -6px rgba(0,0,0,.7),0 0 30px rgba(232,184,74,.4);
 display:grid;place-items:center;font-size:26px}
.orb{position:absolute;right:-30px;top:40px;width:90px;height:90px;border-radius:50%;transform:translateZ(110px);
 background:radial-gradient(circle at 30% 30%,rgba(255,255,255,.55),rgba(123,140,255,.35) 40%,rgba(57,211,168,.12) 70%,transparent 72%);
 backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,.25);display:grid;place-items:center;font-size:12px;color:#fff;text-align:center;font-weight:600}
@media (prefers-reduced-motion:reduce){.scan,.stamp{animation:none}.stamp{opacity:.95}}
@media (max-width:760px){.wrap{grid-template-columns:1fr;height:auto}.stage{display:none}}
</style></head><body>
<div class="wrap">
 <div>
  <span class="chip"><i></i>Six AI agents · built on NVIDIA Nemotron</span>
  <h1>Got a scary notice?<br>Check it before you act.</h1>
  <p class="sub">Saakshi checks whether a notice is genuine, explains what it really means and what happens if you ignore it, then drafts your reply. Every claim is verified before you see it.</p>
  <div class="lines">
   <div><small>Cyber fraud helpline</small><b>1930</b></div>
   <div><small>Free legal aid</small><b>15100</b></div>
   <div><small>Cost to you</small><b>₹0</b></div>
  </div>
 </div>
 <div class="stage" id="stage">
  <div class="beam"></div>
  <div class="stack" id="stack">
   <div class="doc d3"></div>
   <div class="doc d2"><div class="hd">FORM GST DRC-01</div><div class="l m"></div><div class="l"></div><div class="l s"></div></div>
   <div class="doc d1">
    <div class="hd">CENTRAL BUREAU OF INVESTIGATION</div>
    <div class="l"></div><div class="l m"></div><div class="l r"></div><div class="l"></div><div class="l s"></div>
    <div class="l r"></div><div class="l m"></div><div class="l"></div><div class="l r"></div><div class="l s"></div>
    <div class="scan"></div><div class="stamp">LIKELY SCAM</div>
   </div>
   <div class="seal">🛡️</div>
   <div class="orb">Trust<br>Gate</div>
  </div>
 </div>
</div>
<script>
const st=document.getElementById('stack'), sg=document.getElementById('stage');
let tx=-22, ty=14;
document.addEventListener('mousemove',e=>{const r=sg.getBoundingClientRect();
 const x=(e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5;
 st.style.transform=`rotateX(${14-y*22}deg) rotateY(${-22+x*36}deg)`;});
sg.addEventListener('mouseleave',()=>{st.style.transform='rotateX(14deg) rotateY(-22deg)'});
</script></body></html>""", height=480)
    except Exception:
        st.markdown('<h1 class="h2">Got a scary notice? Check it before you act.</h1>', unsafe_allow_html=True)


# =============================================================== NAV
used, cap = budget.spent(), budget.HARD_CAP_USD
st.markdown(f"""<div class="nav"><div class="brand"><span class="seal"></span>Saakshi</div>
<div class="navlinks"><span>Trust Gate</span><span>Six agents</span><span>Help: <b>1930</b> · <b>15100</b></span></div>
<span class="pill"><i></i>Live on Nebius Token Factory</span></div>""", unsafe_allow_html=True)

# =============================================================== HERO
hero()

# =============================================================== CHECK
st.markdown('<div class="kick">Start here</div><div class="h2">Check a notice in under a minute</div>',
            unsafe_allow_html=True)
lc1, lc2 = st.columns([1, 3])
with lc1:
    language = st.selectbox("Explain it to me in", list(LANG_CODE))
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

# =============================================================== RUN
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

# =============================================================== RESULTS
r = st.session_state.get("result")
if r:
    v, a, facts, trust = r["verdict"], r["action"], r["facts"], r["trust"]
    tier = v.get("tier") if v.get("tier") in STAMP else "RESPOND"
    final = ["done"] * 6 if r.get("guard") else ["done", "done", "skipped", "skipped", "done", "skipped"]
    st.markdown('<div class="kick">Result</div><div class="h2">Here’s what Saakshi found</div>', unsafe_allow_html=True)
    st.markdown(pipeline_html(final), unsafe_allow_html=True)
    if r.get("from_cache"):
        st.caption("Instant replay of an earlier full run of this exact notice.")

    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.markdown(f'<div class="paperwrap"><div class="paper"><div class="stamp c-{tier}">{STAMP[tier]}</div>'
                    f'{highlight(st.session_state.get("text", ""), facts)}</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="legend"><mark style="background:rgba(255,91,78,.35)">red</mark> warning sign '
                    '&nbsp; <mark style="background:rgba(255,196,0,.6)">yellow</mark> deadline, quoted word-for-word</div>',
                    unsafe_allow_html=True)

    with right:
        st.markdown(f'<div class="verdict c-{tier}"><span class="t">{STAMP[tier].capitalize()}</span>'
                    f'<p>{E(v.get("one_line", ""))}</p></div>', unsafe_allow_html=True)
        score = trust_score(trust)
        st.markdown(f'<div class="score"><span>Trust score</span><b>{score}<span>/100</span></b></div>'
                    f'<div class="meter c-{tier}"><i style="left:{score}%"></i></div>'
                    f'<div class="meter-row"><span>Likely fake</span><span>{E(trust["status"].replace("_", " ").lower())}</span>'
                    f'<span>Likely genuine</span></div>', unsafe_allow_html=True)

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
          <div class="fact"><small>Amount</small><b>{amt_s}</b><em>{E((facts.get("issuing_authority") or "")[:40])}</em></div>
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

    t1, t2, t3, t4, t5 = st.tabs(["What it means", "If you do nothing", "Your reply", "Trust receipt",
                                  "How the agents worked"])
    with t1:
        st.write(a.get("explanation", ""))
        if trust["red_flags"]:
            st.markdown("**Warning signs found**")
            st.markdown('<div class="flags">' + "".join(
                f'<div class="flagc"><b>{E(fl["flag"])}</b><small>“{E(fl["evidence"])}”</small></div>'
                for fl in trust["red_flags"]) + "</div>", unsafe_allow_html=True)
        if a.get("checklist"):
            st.markdown("**What you'll need**")
            for item in a["checklist"]:
                st.markdown(f"- {item}")
        st.caption(trust["how_to_verify_officially"])
    with t2:
        rows = "".join(f'<div class="row c-{tier}"><span class="dot"></span><div><b>{E(t.get("when", ""))}'
                       f'<span class="tag">{E(t.get("source_tag", "GENERAL").lower())}</span></b>'
                       f'<span class="txt">{E(t.get("what_happens", ""))}</span></div></div>'
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

# =============================================================== HOW IT WORKS (BENTO)
st.markdown('<div class="kick">How it protects you</div><div class="h2">Verify first. Explain second.</div>',
            unsafe_allow_html=True)
st.markdown("""<div class="bento">
 <div class="tile big"><span class="ic">🛡️</span><h4>The Trust Gate runs before any AI</h4>
  <p>Fake notices are built to trick people and AI alike. So plain rules check authenticity first, and the AI
  can raise suspicion but never overrule a scam verdict.</p>
  <div class="rulelist"><span class="rule g">Income Tax DIN present</span><span class="rule g">GSTIN checksum valid</span>
  <span class="rule r">“Digital arrest” language</span><span class="rule r">Personal UPI payment</span>
  <span class="rule r">Secrecy demands</span><span class="rule r">Gmail “officials”</span><span class="rule r">Hours-long deadlines</span></div>
  <div class="glow" style="background:#7B8CFF"></div></div>
 <div class="tile"><span class="ic">⚖️</span><h4>Six agents, one job each</h4>
  <p>Cheap models read and extract. Ultra only judges and verifies.</p>
  <div class="agents-mini"><span>Nano</span><span>Omni</span><span>Super</span><span>Ultra</span><span>Tavily</span><span>Rules</span></div></div>
 <div class="tile"><span class="ic">📅</span><h4>Deadlines are never guessed</h4>
  <p>A date is shown only if it appears word-for-word in your notice.</p><div class="glow" style="background:#E8B84A"></div></div>
 <div class="tile wide"><span class="ic">🔊</span><h4>Explained in your language, out loud</h4>
  <p>English, Hindi and Marathi, with a read-aloud button for parents and grandparents.</p></div>
 <div class="tile wide"><span class="ic">🔒</span><h4>Private by default</h4>
  <p>PAN, Aadhaar, phone numbers and emails are removed before any web search. Nothing is stored.</p>
  <div class="glow" style="background:#39D3A8"></div></div>
</div>""", unsafe_allow_html=True)

# =============================================================== FOOTER
used, cap = budget.spent(), budget.HARD_CAP_USD
pct = min(used / cap * 100, 100)
st.markdown(f"""<div class="foot"><div class="foot-grid">
 <div><h5>Saakshi</h5><p style="color:var(--muted)">The citizen's counter-agent for official notices.
 Not a lawyer or chartered accountant. For serious notices, consult one.</p></div>
 <div><h5>Get help</h5><ul><li>Cyber fraud: <b>1930</b></li><li>cybercrime.gov.in</li><li>Free legal aid: <b>15100</b></li></ul></div>
 <div><h5>Built with</h5><ul><li>NVIDIA Nemotron 3</li><li>Nebius Token Factory</li><li>Tavily search</li></ul></div>
 <div><h5>Live AI budget</h5><p>&#36;{used:.2f} of &#36;{cap:.2f} used</p><div class="bar"><span style="width:{pct:.1f}%"></span></div></div>
</div><div class="wordmark">Saakshi</div></div>""", unsafe_allow_html=True)
