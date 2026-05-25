import streamlit as st
import asyncio
import edge_tts
import pdfplumber
import tempfile
import os
import re
from datetime import datetime
from deep_translator import GoogleTranslator

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="PDF → Audio Converter", page_icon="🎧", layout="centered")

# ── Session state ─────────────────────────────────────────────────────────────
DEFAULTS = {
    "history": [], "extracted_text": "", "pdf_info": {}, "preview_ready": False,
    "last_filename": "", "voice_sample_bytes": None, "voice_sample_label": "",
    "dark_mode": True, "last_audio_bytes": None, "last_audio_lang": "en",
    "chapters": [], "selected_chapter": "Full Document",
    "bilingual_en": [], "bilingual_hi": [],
    "reading_text": "", "reading_active": False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Theme ─────────────────────────────────────────────────────────────────────
D = st.session_state.dark_mode
T = {
    "bg":         "#0d0d0f"  if D else "#f4f4f6",
    "card":       "#141417"  if D else "#ffffff",
    "border":     "#2a2a30"  if D else "#e2e2ea",
    "text":       "#f0ede8"  if D else "#18181b",
    "muted":      "#7a7a85"  if D else "#6b7280",
    "input_bg":   "#0d0d0f"  if D else "#f9f9fb",
    "hist_bg":    "#1a1a1f"  if D else "#f0f0f5",
    "fi_bg":      "#1a1a1f"  if D else "#f0f0f5",
    "icon":       "☀️"       if D else "🌙",
    "wc":         "#f5a623"  if D else "#e05c2a",
    "read_hl":    "#f5a62328" if D else "#f5a62320",
    "read_hl_b":  "#f5a623",
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
:root{{
  --bg:{T['bg']};--card:{T['card']};--border:{T['border']};
  --accent:#f5a623;--accent2:#e05c2a;--text:{T['text']};--muted:{T['muted']};
  --success:#3ecf8e;--info:#38bdf8;--purple:#c084fc;
  --input-bg:{T['input_bg']};--hist-bg:{T['hist_bg']};--fi-bg:{T['fi_bg']};
}}
html,body,[data-testid="stAppViewContainer"]{{background:var(--bg)!important;color:var(--text)!important;font-family:'DM Sans',sans-serif!important;transition:background .3s,color .3s;}}
[data-testid="stHeader"]{{background:transparent!important;}}
[data-testid="stSidebar"]{{display:none!important;}}
.block-container{{padding-top:1.2rem!important;max-width:750px!important;}}
h1,h2,h3{{font-family:'Syne',sans-serif!important;}}

/* Hero */
.hero{{text-align:center;padding:1.2rem 1rem .8rem;}}
.hero-badge{{display:inline-block;background:linear-gradient(135deg,#f5a62322,#e05c2a22);border:1px solid #f5a62355;color:var(--accent);font-family:'Syne',sans-serif;font-size:.68rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;padding:.28rem .9rem;border-radius:100px;margin-bottom:.8rem;}}
.hero h1{{font-size:2.3rem!important;font-weight:800!important;background:linear-gradient(135deg,{T['text']} 30%,#f5a623 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1.15!important;margin-bottom:.45rem!important;}}
.hero p{{color:var(--muted);font-size:.9rem;max-width:480px;margin:0 auto;line-height:1.6;}}
.flow-steps{{display:flex;align-items:center;justify-content:center;gap:.35rem;flex-wrap:wrap;margin:.75rem 0 0;font-size:.74rem;color:var(--muted);}}
.flow-step{{background:var(--fi-bg);border:1px solid var(--border);border-radius:7px;padding:.18rem .5rem;}}
.flow-arrow{{color:var(--accent);font-weight:700;}}

/* Cards */
.card{{background:var(--card);border:1px solid var(--border);border-radius:15px;padding:1.2rem;margin-bottom:.85rem;transition:background .3s,border-color .3s;}}
.card-label{{font-family:'Syne',sans-serif;font-size:.65rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:.7rem;}}

/* File info grid */
.fi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:.55rem;margin-top:.35rem;}}
.fi-box{{background:var(--fi-bg);border:1px solid var(--border);border-radius:9px;padding:.55rem .4rem;text-align:center;}}
.fi-val{{font-size:1rem;font-weight:700;color:var(--accent);font-family:'Syne',sans-serif;}}
.fi-lbl{{font-size:.64rem;color:var(--muted);margin-top:.1rem;}}

/* Chapter chips */
.chapter-chips{{display:flex;flex-wrap:wrap;gap:.4rem;margin:.5rem 0;}}
.chapter-chip{{background:var(--fi-bg);border:1px solid var(--border);border-radius:7px;padding:.3rem .65rem;font-size:.76rem;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px;}}
.chapter-chip.active{{background:linear-gradient(135deg,#f5a62318,#e05c2a18);border-color:var(--accent);color:var(--accent);font-weight:600;}}

/* Badges */
.translate-badge{{display:inline-flex;align-items:center;gap:.35rem;background:linear-gradient(135deg,#7c3aed20,#a855f720);border:1px solid #7c3aed44;color:var(--purple);font-size:.72rem;font-weight:600;padding:.25rem .75rem;border-radius:100px;margin:.3rem 0;}}
.info-badge{{display:inline-flex;align-items:center;gap:.35rem;background:#38bdf810;border:1px solid #38bdf830;color:var(--info);font-size:.7rem;font-weight:500;padding:.22rem .7rem;border-radius:100px;margin:.22rem 0;}}
.success-badge{{display:inline-flex;align-items:center;gap:.35rem;background:#3ecf8e10;border:1px solid #3ecf8e30;color:var(--success);font-size:.7rem;font-weight:500;padding:.22rem .7rem;border-radius:100px;margin:.22rem 0;}}

/* Waveform */
.waveform-wrap{{background:var(--card);border:1px solid var(--border);border-radius:13px;padding:1rem .9rem .7rem;margin:.75rem 0;}}
.waveform-label{{font-family:'Syne',sans-serif;font-size:.64rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:.55rem;}}
#waveform-canvas{{width:100%;height:72px;border-radius:7px;background:{T['input_bg']};display:block;cursor:pointer;}}
.wf-controls{{display:flex;align-items:center;justify-content:space-between;margin-top:.5rem;font-size:.74rem;color:var(--muted);}}
.wf-time{{font-family:'Syne',sans-serif;font-size:.8rem;color:var(--accent);font-weight:700;}}

/* Bilingual */
.bi-pair{{display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-bottom:.55rem;}}
.bi-col{{background:var(--fi-bg);border:1px solid var(--border);border-radius:10px;padding:.75rem .85rem;}}
.bi-tag{{font-size:.58rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:.3rem;}}
.bi-text{{font-size:.82rem;line-height:1.75;color:var(--text);}}

/* Reading mode */
.reading-container{{background:var(--fi-bg);border:1px solid var(--border);border-radius:13px;padding:1.2rem;margin-top:.7rem;max-height:450px;overflow-y:auto;scroll-behavior:smooth;}}
.r-sent{{padding:.38rem .55rem;border-radius:7px;margin:.18rem 0;font-size:.88rem;line-height:1.82;color:var(--text);cursor:pointer;border-left:3px solid transparent;transition:all .18s;}}
.r-sent:hover{{background:{T['fi_bg']};}}
.r-sent.active{{background:{T['read_hl']};border-left-color:{T['read_hl_b']};color:var(--accent);font-weight:500;}}

/* Inputs */
[data-testid="stTextArea"] textarea{{background:var(--input-bg)!important;color:var(--text)!important;border:1px solid var(--border)!important;border-radius:9px!important;font-family:'DM Sans',sans-serif!important;font-size:.86rem!important;line-height:1.7!important;}}
[data-testid="stTextArea"] textarea:focus{{border-color:var(--accent)!important;box-shadow:0 0 0 2px #f5a62320!important;}}
div[data-baseweb="select"]>div{{background:var(--input-bg)!important;border-color:var(--border)!important;color:var(--text)!important;border-radius:9px!important;}}
[data-testid="stSelectbox"] label,[data-testid="stNumberInput"] label{{color:var(--muted)!important;font-size:.81rem!important;}}
[data-testid="stNumberInput"] input{{background:var(--input-bg)!important;color:var(--text)!important;border-color:var(--border)!important;border-radius:7px!important;}}
[data-testid="stFileUploader"]{{border:2px dashed var(--border)!important;border-radius:11px!important;background:var(--input-bg)!important;}}
[data-testid="stFileUploader"]:hover{{border-color:var(--accent)!important;}}
[data-testid="stFileUploaderDropzone"]{{background:transparent!important;}}

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"]{{background:var(--card)!important;border-radius:11px!important;padding:.28rem!important;gap:.18rem!important;border:1px solid var(--border)!important;}}
[data-testid="stTabs"] [data-baseweb="tab"]{{background:transparent!important;color:var(--muted)!important;border-radius:7px!important;font-family:'Syne',sans-serif!important;font-size:.78rem!important;font-weight:600!important;padding:.35rem .9rem!important;border:none!important;}}
[data-testid="stTabs"] [aria-selected="true"]{{background:linear-gradient(135deg,var(--accent),var(--accent2))!important;color:#0d0d0f!important;}}

/* Buttons */
div[data-testid="stButton"]>button{{background:linear-gradient(135deg,var(--accent),var(--accent2))!important;color:#0d0d0f!important;font-family:'Syne',sans-serif!important;font-weight:700!important;font-size:.91rem!important;border:none!important;border-radius:11px!important;height:2.8rem!important;box-shadow:0 4px 16px #f5a62328!important;transition:opacity .2s,transform .1s!important;width:100%;}}
div[data-testid="stButton"]>button:hover{{opacity:.86!important;transform:translateY(-1px)!important;}}
[data-testid="stProgress"]>div>div{{background:linear-gradient(90deg,var(--accent),var(--accent2))!important;border-radius:100px!important;}}
[data-testid="stProgress"]{{background:var(--border)!important;border-radius:100px!important;}}

/* Result */
.result-card{{background:linear-gradient(135deg,#3ecf8e10,#3ecf8e04);border:1px solid #3ecf8e40;border-radius:15px;padding:1.2rem;margin-top:.75rem;text-align:center;}}
.result-card h3{{color:var(--success)!important;font-size:1rem!important;margin-bottom:.22rem!important;}}
.result-card p{{color:var(--muted);font-size:.83rem;margin-bottom:.85rem;}}
.stats-row{{display:flex;gap:.5rem;margin-top:.6rem;flex-wrap:wrap;justify-content:center;}}
.stat-pill{{background:var(--fi-bg);border:1px solid var(--border);border-radius:7px;padding:.28rem .65rem;font-size:.72rem;color:var(--muted);}}
.stat-pill span{{color:var(--text);font-weight:500;}}
div[data-testid="stDownloadButton"]>button{{background:transparent!important;color:var(--success)!important;border:1.5px solid var(--success)!important;font-family:'Syne',sans-serif!important;font-weight:600!important;border-radius:11px!important;height:2.8rem!important;width:100%;}}
div[data-testid="stDownloadButton"]>button:hover{{background:#3ecf8e10!important;}}
audio{{width:100%;border-radius:9px;margin-top:.3rem;}}
[data-testid="stAudio"]{{background:var(--input-bg);border-radius:11px;padding:.45rem;border:1px solid var(--border);}}

/* History */
.hist-card{{background:var(--hist-bg);border:1px solid var(--border);border-radius:11px;padding:.85rem 1rem;margin-bottom:.6rem;display:flex;justify-content:space-between;align-items:center;}}
.hist-name{{font-family:'Syne',sans-serif;font-size:.86rem;font-weight:700;color:var(--text);}}
.hist-meta{{font-size:.71rem;color:var(--muted);margin-top:.1rem;}}
.hist-badge{{font-size:.66rem;font-weight:600;padding:.16rem .5rem;border-radius:100px;border:1px solid;white-space:nowrap;}}
.hist-badge.en{{color:var(--info);border-color:#38bdf840;background:#38bdf810;}}
.hist-badge.hi{{color:var(--purple);border-color:#c084fc40;background:#c084fc10;}}

/* Misc */
.status-text{{font-size:.8rem;color:var(--muted);text-align:center;margin-top:.3rem;font-style:italic;}}
.divider{{height:1px;background:var(--border);margin:.9rem 0;}}
.footer{{text-align:center;color:var(--muted);font-size:.71rem;padding:1.6rem 0 .8rem;}}
.empty-state{{text-align:center;color:var(--muted);padding:2.2rem 1rem;font-size:.84rem;line-height:1.8;}}
</style>
""", unsafe_allow_html=True)

# ── JavaScript ────────────────────────────────────────────────────────────────
WAVEFORM_JS = f"""
<script>
(function(){{
  function init(){{
    const audios = document.querySelectorAll('audio');
    const canvas = document.getElementById('waveform-canvas');
    const tEl = document.getElementById('wf-cur');
    const dEl = document.getElementById('wf-dur');
    if(!canvas||!audios.length){{setTimeout(init,500);return;}}
    const audio = audios[audios.length-1];
    const ctx = canvas.getContext('2d');
    const W=canvas.offsetWidth||680, H=72;
    canvas.width=W; canvas.height=H;
    const N=90, col='{T['wc']}';
    const bars=Array.from({{length:N}},(_,i)=>{{const s=Math.sin(i*127.1+311.7)*43758.5453;return .15+Math.abs(s-Math.floor(s))*.75;}});
    const fmt=s=>Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');
    const draw=p=>{{
      ctx.clearRect(0,0,W,H);
      const bw=(W-2*(N-1))/N;
      bars.forEach((b,i)=>{{
        const x=i*(bw+2),h=b*H*.85,y=(H-h)/2;
        ctx.fillStyle=i/N<=p?col:col+'44';
        ctx.beginPath();ctx.roundRect(x,y,bw,h,2);ctx.fill();
      }});
    }};
    draw(0);
    audio.addEventListener('timeupdate',()=>{{
      const p=audio.duration?audio.currentTime/audio.duration:0;
      draw(p);
      if(tEl)tEl.textContent=fmt(audio.currentTime);
    }});
    audio.addEventListener('loadedmetadata',()=>{{if(dEl)dEl.textContent=fmt(audio.duration);}});
    canvas.addEventListener('click',e=>{{
      const r=canvas.getBoundingClientRect();
      if(audio.duration)audio.currentTime=(e.clientX-r.left)/r.width*audio.duration;
    }});
  }}
  setTimeout(init,900);
}})();
</script>
"""

READING_JS = """
<script>
(function(){
  function init(){
    const audios=document.querySelectorAll('audio');
    const sents=document.querySelectorAll('.r-sent');
    if(!audios.length||!sents.length){setTimeout(init,600);return;}
    const audio=audios[audios.length-1];
    const total=sents.length;
    audio.addEventListener('timeupdate',function(){
      if(!audio.duration)return;
      const idx=Math.min(Math.floor((audio.currentTime/audio.duration)*total),total-1);
      sents.forEach((s,i)=>{
        s.classList.toggle('active',i===idx);
        if(i===idx)s.scrollIntoView({behavior:'smooth',block:'nearest'});
      });
    });
    sents.forEach((s,i)=>{
      s.addEventListener('click',()=>{
        if(audio.duration){audio.currentTime=(i/total)*audio.duration;audio.play();}
      });
    });
  }
  setTimeout(init,1100);
})();
</script>
"""

# ── Constants ─────────────────────────────────────────────────────────────────
VOICES = {
    "English": {
        "Jenny (Female, US) 🇺🇸": "en-US-JennyNeural",
        "Guy (Male, US) 🇺🇸":    "en-US-GuyNeural",
        "Sonia (Female, UK) 🇬🇧": "en-GB-SoniaNeural",
        "Ryan (Male, UK) 🇬🇧":   "en-GB-RyanNeural",
    },
    "Hindi 🇮🇳 (Auto-Translate)": {
        "Swara (Female) 🇮🇳": "hi-IN-SwaraNeural",
        "Madhur (Male) 🇮🇳":  "hi-IN-MadhurNeural",
    },
}
SPEEDS = {"0.75× Slow":"-25%","1× Normal":"+0%","1.25× Fast":"+25%","1.5× Faster":"+50%"}
SAMPLES = {
    "English": "Hello! This is how your audio will sound. Your PDF will be read in this voice.",
    "Hindi 🇮🇳 (Auto-Translate)": "नमस्ते! यह आपकी ऑडियो का नमूना है। आपकी पीडीएफ इसी आवाज़ में पढ़ी जाएगी।",
}
CHAPTER_RE = [
    r'^(chapter|ch\.?|part|section|unit)\s+(\d+|[ivxlcdm]+)',
    r'^\d+\.\s+[A-Z][a-z]{2,}',
    r'^[A-Z][A-Z\s]{4,28}$',
]
MAX_HIST = 5


# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_pdf(f, ps=None, pe=None):
    f.seek(0)
    with pdfplumber.open(f) as pdf:
        n = len(pdf.pages)
        s = (ps-1) if ps else 0
        e = min(pe if pe else n, n)
        pages = [p.extract_text().strip() for p in pdf.pages[s:e] if p.extract_text()]
    return "\n\n".join(pages), n


def pdf_info(f):
    f.seek(0,2); size=f.tell(); f.seek(0)
    with pdfplumber.open(f) as pdf:
        n=len(pdf.pages)
        sample="".join(p.extract_text() or "" for p in pdf.pages[:3])
    w=len(sample.split()); avg=w/min(3,n) if n else 150; est=int(avg*n)
    return {"pages":n,"size_mb":round(size/1024/1024,2),"est_words":est,"est_min":int(round(est/130))}


def detect_chapters(text):
    lines = text.split('\n')
    chapters, cur_title, cur_lines = [], "Introduction", []
    for line in lines:
        s = line.strip()
        if not s: cur_lines.append(line); continue
        heading = any(re.match(p, s, re.IGNORECASE) for p in CHAPTER_RE)
        # Short title-case line heuristic
        words = s.split()
        if not heading and 2 <= len(words) <= 7 and s[0].isupper() and not s.endswith('.') and len(s) < 65:
            heading = True
        if heading and cur_lines:
            body = "\n".join(cur_lines).strip()
            if len(body) > 80:
                chapters.append({"title": cur_title, "text": body})
            cur_title, cur_lines = s, []
        else:
            cur_lines.append(line)
    if cur_lines:
        body = "\n".join(cur_lines).strip()
        if body: chapters.append({"title": cur_title, "text": body})
    return chapters


def clean(text):
    text = re.sub(r'\s+',' ',text)
    text = re.sub(r'[^\w\s.,!?;:\-\'"()\u0900-\u097F]','',text)
    return text.strip()


def translate_bulk(text, pb, status):
    CHUNK = 4500
    sents = re.split(r'(?<=[.!?])\s+', text)
    batches, cur = [], ""
    for s in sents:
        if len(cur)+len(s)+1 <= CHUNK: cur += s+" "
        else:
            if cur: batches.append(cur.strip())
            cur = s+" "
    if cur: batches.append(cur.strip())
    tr = GoogleTranslator(source='en', target='hi')
    parts, total = [], len(batches)
    for i,b in enumerate(batches):
        parts.append(tr.translate(b))
        pb.progress(35+int((i+1)/total*25))
        status.markdown(f'<p class="status-text">🌐 Translating... ({i+1}/{total} parts)</p>', unsafe_allow_html=True)
    return " ".join(parts)


def translate_pairs(text, max_sents=60):
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 15][:max_sents]
    tr = GoogleTranslator(source='en', target='hi')
    hi = []
    for s in sents:
        try: hi.append(tr.translate(s))
        except: hi.append("—")
    return sents, hi


async def _gen(text, voice, rate, path):
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


async def _gen_all(chunks, voice, rate, base):
    paths = [f"{base}_c{i}.mp3" for i in range(len(chunks))]
    await asyncio.gather(*[_gen(c, voice, rate, p) for c,p in zip(chunks,paths)])
    return paths


def chunk_text(text, size=8000):
    sents = re.split(r'(?<=[।.!?])\s+', text)
    chunks, cur = [], ""
    for s in sents:
        if len(cur)+len(s)<size: cur+=s+" "
        else:
            if cur: chunks.append(cur.strip())
            cur=s+" "
    if cur: chunks.append(cur.strip())
    return chunks or [text]


def make_audio(text, voice, rate):
    chunks = chunk_text(text)
    with tempfile.NamedTemporaryFile(delete=False,suffix=".mp3") as tmp:
        base,path = tmp.name[:-4],tmp.name
    if len(chunks)==1:
        asyncio.run(_gen(text,voice,rate,path))
    else:
        cps = asyncio.run(_gen_all(chunks,voice,rate,base))
        with open(path,"wb") as out:
            for cp in cps:
                if os.path.exists(cp): out.write(open(cp,"rb").read()); os.unlink(cp)
    data = open(path,"rb").read(); os.unlink(path)
    return data


def push_history(name, lang, voice, words, mins, audio):
    st.session_state.history.insert(0,{
        "name":name,"lang":lang,"voice":voice,
        "words":words,"mins":mins,"audio":audio,
        "time":datetime.now().strftime("%d %b %Y, %I:%M %p"),
    })
    st.session_state.history = st.session_state.history[:MAX_HIST]


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

# Theme toggle
_, tcol = st.columns([6,1])
with tcol:
    if st.button(T['icon'], use_container_width=True):
        st.session_state.dark_mode = not D; st.rerun()

# Hero
st.markdown(f"""
<div class="hero">
  <div class="hero-badge">🎧 Free · No API Key · Premium</div>
  <h1>PDF to Audio<br>Converter</h1>
  <p>Chapters · Bilingual View · Reading Mode · Waveform · History</p>
  <div class="flow-steps">
    <span class="flow-step">📄 PDF</span><span class="flow-arrow">→</span>
    <span class="flow-step">📑 Chapters</span><span class="flow-arrow">→</span>
    <span class="flow-step">🌐 Translate</span><span class="flow-arrow">→</span>
    <span class="flow-step">🎵 Audio</span><span class="flow-arrow">→</span>
    <span class="flow-step">📖 Read Along</span>
  </div>
</div>
""", unsafe_allow_html=True)

# Tabs
tab_cvt, tab_bi, tab_read, tab_hist = st.tabs([
    "🎙️  Convert", "🔤  Bilingual", "📖  Read Along", "🕘  History"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CONVERT
# ══════════════════════════════════════════════════════════════════════════════
with tab_cvt:

    # Upload
    st.markdown('<div class="card"><div class="card-label">📄 Step 1 — Upload PDF</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Drop PDF here", type=["pdf"], label_visibility="collapsed")
    if not uploaded:
        st.markdown('<p style="text-align:center;font-size:.76rem;color:var(--muted);padding:.3rem 0 .1rem">🗂️ Drag & drop a PDF or click to browse</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # File info + Chapter detection (runs once per new file)
    if uploaded:
        if uploaded.name != st.session_state.last_filename:
            with st.spinner("Analysing PDF..."):
                info = pdf_info(uploaded)
                raw_full, _ = extract_pdf(uploaded)
                chapters = detect_chapters(raw_full)
                st.session_state.update({
                    "pdf_info": info, "chapters": chapters,
                    "last_filename": uploaded.name,
                    "preview_ready": False, "extracted_text": "",
                    "last_audio_bytes": None, "selected_chapter": "Full Document",
                    "bilingual_en": [], "bilingual_hi": [],
                    "reading_text": "", "reading_active": False,
                })
        else:
            info = st.session_state.pdf_info

        # File info card
        st.markdown(f"""
        <div class="card">
          <div class="card-label">📊 File — {uploaded.name}</div>
          <div class="fi-grid">
            <div class="fi-box"><div class="fi-val">{info['pages']}</div><div class="fi-lbl">Pages</div></div>
            <div class="fi-box"><div class="fi-val">{info['size_mb']} MB</div><div class="fi-lbl">Size</div></div>
            <div class="fi-box"><div class="fi-val">{info['est_words']:,}</div><div class="fi-lbl">Est. Words</div></div>
            <div class="fi-box"><div class="fi-val">~{info['est_min']} min</div><div class="fi-lbl">Est. Audio</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Chapter selector
        chapters = st.session_state.chapters
        if chapters:
            st.markdown('<div class="card"><div class="card-label">📑 Step 2 — Choose Chapter / Section</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="info-badge">🔍 {len(chapters)} sections detected automatically</div>', unsafe_allow_html=True)
            ch_names = ["📄 Full Document"] + [f"📑 {c['title'][:48]}" for c in chapters]
            sel = st.selectbox("Section", ch_names, index=0, label_visibility="collapsed")
            st.session_state.selected_chapter = sel

            if sel != "📄 Full Document":
                idx = ch_names.index(sel) - 1
                wc = len(chapters[idx]['text'].split())
                em = round(wc/130,1)
                st.markdown(f'<div class="success-badge">✅ {chapters[idx]["title"][:40]} · {wc:,} words · ~{em} min</div>', unsafe_allow_html=True)

            # Chapter chips (visual overview)
            chip_parts = []
            for c in chapters[:12]:
                chip_key = "📑 " + c["title"][:48]
                is_active = chip_key in ch_names and ch_names.index(chip_key) == ch_names.index(sel)
                css = "chapter-chip active" if is_active else "chapter-chip"
                chip_parts.append('<span class="' + css + '">' + c["title"][:32] + '</span>')
            chips_html = "".join(chip_parts)
            st.markdown(f'<div class="chapter-chips">{chips_html}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # Settings
    step = "3" if (uploaded and st.session_state.chapters) else "2"
    st.markdown(f'<div class="card"><div class="card-label">⚙️ Step {step} — Settings</div>', unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1: language = st.selectbox("Output Language", list(VOICES.keys()), index=0)
    with c2: voice_label = st.selectbox("Voice", list(VOICES[language].keys()))
    is_hindi = "Hindi" in language
    voice_id = VOICES[language][voice_label]
    rate     = SPEEDS[st.selectbox("Speed", list(SPEEDS.keys()), index=1)]

    if is_hindi:
        st.markdown('<div class="translate-badge">🌐 English PDF → Translated to Hindi → Hindi Audio</div>', unsafe_allow_html=True)

    vname = voice_label.split("🇺🇸")[0].split("🇬🇧")[0].split("🇮🇳")[0].strip()
    if st.button(f"🔊 Preview Voice — {vname}"):
        with st.spinner("Generating sample..."):
            try:
                sb = make_audio(SAMPLES[language], voice_id, "+0%")
                st.session_state.voice_sample_bytes = sb
                st.session_state.voice_sample_label = voice_label
            except Exception as e: st.error(f"Preview failed: {e}")

    if st.session_state.voice_sample_bytes and st.session_state.voice_sample_label == voice_label:
        st.markdown('<div class="info-badge">🎧 Voice Sample</div>', unsafe_allow_html=True)
        st.audio(st.session_state.voice_sample_bytes, format="audio/mp3")

    c3,c4 = st.columns(2)
    with c3: convert_mode = st.selectbox("Convert", ["Full PDF","Page Range"], index=0)
    page_start = page_end = None
    if convert_mode == "Page Range":
        with c4: pass  # spacer
        p1,p2 = st.columns(2)
        with p1: page_start = st.number_input("From Page", min_value=1, value=1, step=1)
        with p2: page_end   = st.number_input("To Page",   min_value=1, value=10, step=1)
        st.caption("💡 10–20 pages at a time is fastest")
    st.markdown('</div>', unsafe_allow_html=True)

    # Preview & Edit
    if uploaded:
        st.markdown('<div class="card"><div class="card-label">✏️ Preview & Edit Text (Optional)</div>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:.8rem;color:var(--muted);margin-bottom:.6rem;">Extract → review → trim or fix → then generate. Your edits are used directly.</p>', unsafe_allow_html=True)
        ce,cc = st.columns([3,1])
        with ce:
            if st.button("📖 Extract & Preview", use_container_width=True):
                with st.spinner("Extracting..."):
                    try:
                        sel = st.session_state.selected_chapter
                        chs = st.session_state.chapters
                        if sel not in ("📄 Full Document","Full Document") and chs:
                            ch_names2 = ["📄 Full Document"] + [f"📑 {c['title'][:48]}" for c in chs]
                            idx2 = ch_names2.index(sel)-1 if sel in ch_names2 else None
                            raw = chs[idx2]['text'] if idx2 is not None else extract_pdf(uploaded,page_start,page_end)[0]
                        else:
                            raw,_ = extract_pdf(uploaded, page_start, page_end)
                        st.session_state.extracted_text = clean(raw)
                        st.session_state.preview_ready = True
                    except Exception as e: st.error(f"Failed: {e}")
        with cc:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.extracted_text = ""; st.session_state.preview_ready = False; st.rerun()

        if st.session_state.preview_ready and st.session_state.extracted_text:
            wc = len(st.session_state.extracted_text.split())
            st.markdown(f'<div class="info-badge">📝 {wc:,} words — edit if needed</div>', unsafe_allow_html=True)
            edited = st.text_area("Extracted Text", value=st.session_state.extracted_text, height=210, label_visibility="collapsed", key="editor")
            st.session_state.extracted_text = edited
        st.markdown('</div>', unsafe_allow_html=True)

    # Generate button
    st.markdown('<div style="margin-top:.7rem"></div>', unsafe_allow_html=True)
    if st.button("🎙️ Generate Audio", use_container_width=True):
        if not uploaded:
            st.warning("⚠️ Upload a PDF first.")
        else:
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            pb = st.progress(0); stat = st.empty()
            try:
                # Resolve text
                if st.session_state.preview_ready and st.session_state.extracted_text.strip():
                    stat.markdown('<p class="status-text">✏️ Using your edited text...</p>', unsafe_allow_html=True)
                    pb.progress(20); txt = st.session_state.extracted_text.strip()
                else:
                    sel = st.session_state.selected_chapter
                    chs = st.session_state.chapters
                    if sel not in ("📄 Full Document","Full Document") and chs:
                        ch_names3 = ["📄 Full Document"] + [f"📑 {c['title'][:48]}" for c in chs]
                        idx3 = ch_names3.index(sel)-1 if sel in ch_names3 else None
                        raw = chs[idx3]['text'] if idx3 is not None else extract_pdf(uploaded,page_start,page_end)[0]
                    else:
                        stat.markdown('<p class="status-text">📖 Extracting text...</p>', unsafe_allow_html=True)
                        pb.progress(10)
                        raw,_ = extract_pdf(uploaded, page_start, page_end)
                    if not raw.strip(): st.error("❌ No text found — PDF may be scanned."); st.stop()
                    pb.progress(20); txt = clean(raw)

                wc  = len(txt.split())
                em  = round(wc/130, 1)

                if is_hindi:
                    stat.markdown('<p class="status-text">🌐 Translating English → Hindi...</p>', unsafe_allow_html=True)
                    pb.progress(28); final = translate_bulk(txt, pb, stat)
                else:
                    final = txt; pb.progress(35)

                nc = len(chunk_text(final))
                stat.markdown(f'<p class="status-text">⚡ Generating audio ({nc} chunk(s) in parallel)...</p>', unsafe_allow_html=True)
                pb.progress(65)
                audio = make_audio(final, voice_id, rate)
                pb.progress(100); stat.empty()

                # Store for Reading Mode & Bilingual
                st.session_state.last_audio_bytes  = audio
                st.session_state.last_audio_lang   = "hi" if is_hindi else "en"
                st.session_state.reading_text      = final
                st.session_state.reading_active    = True

                pdf_name   = uploaded.name.replace(".pdf","")
                lang_disp  = "Hindi 🇮🇳" if is_hindi else "English 🇺🇸"
                audio_fn   = f"{pdf_name}_{'hindi' if is_hindi else 'english'}_audio.mp3"
                ch_label   = sel.replace("📑 ","")[:30] if sel not in ("📄 Full Document","Full Document") else ""
                push_history(pdf_name, lang_disp, vname, wc, em, audio)

                st.markdown(f"""
                <div class="result-card">
                  <h3>✅ Audio Ready!</h3>
                  <p>{"Translated → Hindi audio" if is_hindi else "English audio"}{f" · {ch_label}" if ch_label else ""}</p>
                  <div class="stats-row">
                    <div class="stat-pill">Words <span>{wc:,}</span></div>
                    <div class="stat-pill">~Duration <span>{em} min</span></div>
                    <div class="stat-pill">Language <span>{lang_disp}</span></div>
                    <div class="stat-pill">Voice <span>{vname}</span></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Waveform
                st.markdown("""
                <div class="waveform-wrap">
                  <div class="waveform-label">🎵 Waveform — click to seek · switch to 📖 Read Along tab</div>
                  <canvas id="waveform-canvas"></canvas>
                  <div class="wf-controls">
                    <span class="wf-time"><span id="wf-cur">0:00</span> / <span id="wf-dur">--:--</span></span>
                    <span style="font-size:.7rem;color:var(--muted)">Click waveform bar to jump · Use player ▶ below</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                st.audio(audio, format="audio/mp3")
                st.components.v1.html(WAVEFORM_JS, height=0)
                st.download_button("⬇️ Download MP3", audio, audio_fn, "audio/mpeg", use_container_width=True)
                st.markdown('<p style="font-size:.75rem;color:var(--muted);text-align:center;margin-top:.4rem">💡 Switch to the <strong>📖 Read Along</strong> tab to follow sentences as audio plays</p>', unsafe_allow_html=True)

            except Exception as e:
                pb.empty(); stat.empty(); st.error(f"❌ Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — BILINGUAL VIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_bi:
    st.markdown('<div style="height:.3rem"></div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div class="card-label">🔤 Bilingual View — English + Hindi Side by Side</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:.8rem;color:var(--muted);margin-bottom:.75rem;">See each sentence in English alongside its Hindi translation. Great for learning or proofreading.</p>', unsafe_allow_html=True)

    bi_file = st.file_uploader("Upload PDF for bilingual view", type=["pdf"], key="bi_up", label_visibility="collapsed")
    bc1,bc2 = st.columns(2)
    with bc1: bi_pages = st.number_input("Pages to translate", min_value=1, max_value=15, value=2, step=1)
    with bc2: bi_max   = st.number_input("Max sentences shown", min_value=10, max_value=80, value=40, step=5)

    if bi_file and st.button("🌐 Generate Bilingual View", use_container_width=True):
        with st.spinner("Extracting & translating..."):
            try:
                raw,_ = extract_pdf(bi_file, 1, int(bi_pages))
                cleaned = clean(raw)
                en_s, hi_s = translate_pairs(cleaned, max_sents=int(bi_max))
                st.session_state.bilingual_en = en_s
                st.session_state.bilingual_hi = hi_s
            except Exception as e: st.error(f"❌ {e}")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.bilingual_en:
        en_s = st.session_state.bilingual_en
        hi_s = st.session_state.bilingual_hi
        st.markdown(f'<div class="info-badge">📝 {len(en_s)} sentences · Blue = English · Purple = Hindi</div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-top:.5rem"></div>', unsafe_allow_html=True)

        for i,(en,hi) in enumerate(zip(en_s,hi_s)):
            st.markdown(f"""
            <div class="bi-pair">
              <div class="bi-col" style="border-left:3px solid #38bdf8">
                <div class="bi-tag" style="color:#38bdf8">EN · {i+1}</div>
                <div class="bi-text">{en}</div>
              </div>
              <div class="bi-col" style="border-left:3px solid #c084fc">
                <div class="bi-tag" style="color:#c084fc">HI · {i+1}</div>
                <div class="bi-text">{hi}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("🗑️ Clear Bilingual View", use_container_width=True):
            st.session_state.bilingual_en = []; st.session_state.bilingual_hi = []; st.rerun()
    else:
        st.markdown("""
        <div class="empty-state">
          🔤<br><br>
          <strong style="font-family:'Syne',sans-serif">No bilingual content yet</strong><br>
          Upload a PDF above and click Generate to see<br>English + Hindi side by side.
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — READ ALONG (Reading Mode)
# ══════════════════════════════════════════════════════════════════════════════
with tab_read:
    st.markdown('<div style="height:.3rem"></div>', unsafe_allow_html=True)

    if not st.session_state.reading_active or not st.session_state.last_audio_bytes:
        st.markdown("""
        <div class="empty-state">
          📖<br><br>
          <strong style="font-family:'Syne',sans-serif">No audio yet</strong><br>
          Generate audio in the <strong>🎙️ Convert</strong> tab first,<br>
          then come back here to read along sentence by sentence.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown('<div class="card"><div class="card-label">📖 Read Along — Sentences highlight as audio plays</div>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:.79rem;color:var(--muted);margin-bottom:.6rem;">Press ▶ Play below → sentences highlight automatically. Click any sentence to jump there.</p>', unsafe_allow_html=True)

        # Audio player
        st.audio(st.session_state.last_audio_bytes, format="audio/mp3")

        # Waveform
        st.markdown("""
        <div class="waveform-wrap" style="margin:.55rem 0">
          <canvas id="waveform-canvas"></canvas>
          <div class="wf-controls">
            <span class="wf-time"><span id="wf-cur">0:00</span> / <span id="wf-dur">--:--</span></span>
            <span style="font-size:.68rem;color:var(--muted)">Click waveform to seek</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Sentences
        text = st.session_state.reading_text
        sents = [s.strip() for s in re.split(r'(?<=[।.!?])\s+', text) if len(s.strip()) > 12]

        sents_html = "\n".join(f'<div class="r-sent" data-idx="{i}">{s}</div>' for i,s in enumerate(sents))

        st.markdown(f"""
        <div style="margin-bottom:.4rem">
          <div class="info-badge">📝 {len(sents)} sentences · Orange = current · Click = jump + play</div>
        </div>
        <div class="reading-container">
          {sents_html}
        </div>
        """, unsafe_allow_html=True)

        st.components.v1.html(WAVEFORM_JS + READING_JS, height=0)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.markdown('<div style="height:.3rem"></div>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown("""
        <div class="empty-state">
          🕘<br><br>
          <strong style="font-family:'Syne',sans-serif">No conversions yet</strong><br>
          Your last 5 converted files will appear here.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f'<p style="font-size:.76rem;color:var(--muted);margin-bottom:.8rem;">{len(st.session_state.history)} of {MAX_HIST} slots · oldest auto-removed</p>', unsafe_allow_html=True)
        for i,e in enumerate(st.session_state.history):
            b = "hi" if "Hindi" in e["lang"] else "en"
            st.markdown(f"""
            <div class="hist-card">
              <div>
                <div class="hist-name">📄 {e['name']}</div>
                <div class="hist-meta">{e['time']} · {e['words']:,} words · ~{e['mins']} min · {e['voice']}</div>
              </div>
              <span class="hist-badge {b}">{e['lang']}</span>
            </div>""", unsafe_allow_html=True)
            ha,hb = st.columns(2)
            with ha: st.audio(e["audio"], format="audio/mp3")
            with hb: st.download_button("⬇️ Download", e["audio"], f"{e['name']}_audio.mp3",
                                        "audio/mpeg", use_container_width=True, key=f"h{i}{e['time']}")

        if st.button("🗑️ Clear All History", use_container_width=True):
            st.session_state.history = []; st.rerun()

# Footer
st.markdown("""
<div class="footer">
  Built By Shaurya · Edge TTS · Google Translate · pdfplumber · Streamlit<br>
  English PDF → Hindi Audio 🇮🇳 &nbsp;|&nbsp; English Audio 🇺🇸🇬🇧
</div>
""", unsafe_allow_html=True)