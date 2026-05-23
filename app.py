import streamlit as st
import asyncio
import edge_tts
import pdfplumber
import tempfile
import os
import re
import base64
from datetime import datetime
from deep_translator import GoogleTranslator

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PDF → Audio Converter",
    page_icon="🎧",
    layout="centered",
)

# ── Session state init ────────────────────────────────────────────────────────
defaults = {
    "history": [],
    "extracted_text": "",
    "pdf_info": {},
    "preview_ready": False,
    "last_filename": "",
    "voice_sample_bytes": None,
    "voice_sample_label": "",
    "dark_mode": True,
    "last_audio_bytes": None,
    "last_audio_name": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Theme variables ───────────────────────────────────────────────────────────
if st.session_state.dark_mode:
    T = {
        "bg": "#0d0d0f", "card": "#141417", "border": "#2a2a30",
        "text": "#f0ede8", "muted": "#7a7a85", "input_bg": "#0d0d0f",
        "hist_bg": "#1a1a1f", "fi_bg": "#1a1a1f", "toggle_icon": "☀️",
        "toggle_label": "Light Mode", "waveform_color": "#f5a623",
        "drop_bg": "#0d0d0f", "drop_border": "#2a2a30",
    }
else:
    T = {
        "bg": "#f5f5f7", "card": "#ffffff", "border": "#e0e0e8",
        "text": "#1a1a2e", "muted": "#6b7280", "input_bg": "#f9f9fb",
        "hist_bg": "#f0f0f5", "fi_bg": "#f0f0f5", "toggle_icon": "🌙",
        "toggle_label": "Dark Mode", "waveform_color": "#e05c2a",
        "drop_bg": "#f9f9fb", "drop_border": "#d0d0da",
    }

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

:root {{
    --bg: {T['bg']};
    --card: {T['card']};
    --border: {T['border']};
    --accent: #f5a623;
    --accent2: #e05c2a;
    --text: {T['text']};
    --muted: {T['muted']};
    --success: #3ecf8e;
    --info: #38bdf8;
    --purple: #c084fc;
    --input-bg: {T['input_bg']};
    --hist-bg: {T['hist_bg']};
    --fi-bg: {T['fi_bg']};
}}

html, body, [data-testid="stAppViewContainer"] {{
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
    transition: background 0.3s, color 0.3s;
}}
[data-testid="stHeader"] {{ background: transparent !important; }}
[data-testid="stSidebar"] {{ display: none !important; }}
.block-container {{ padding-top: 1.5rem !important; max-width: 740px !important; }}
h1, h2, h3 {{ font-family: 'Syne', sans-serif !important; }}

/* ── Theme toggle bar ── */
.topbar {{
    display: flex; justify-content: flex-end; align-items: center;
    margin-bottom: 0.5rem; padding: 0 0.2rem;
}}
.theme-pill {{
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 100px; padding: 0.3rem 0.9rem;
    font-size: 0.75rem; font-weight: 600; color: var(--muted);
    cursor: pointer;
}}

/* ── Hero ── */
.hero {{ text-align: center; padding: 1.5rem 1rem 1rem; }}
.hero-badge {{
    display: inline-block;
    background: linear-gradient(135deg, #f5a62322, #e05c2a22);
    border: 1px solid #f5a62355; color: var(--accent);
    font-family: 'Syne', sans-serif; font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.15em; text-transform: uppercase;
    padding: 0.3rem 1rem; border-radius: 100px; margin-bottom: 0.9rem;
}}
.hero h1 {{
    font-size: 2.4rem !important; font-weight: 800 !important;
    background: linear-gradient(135deg, {T['text']} 30%, #f5a623 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; line-height: 1.15 !important; margin-bottom: 0.5rem !important;
}}
.hero p {{ color: var(--muted); font-size: 0.92rem; max-width: 460px; margin: 0 auto; line-height: 1.6; }}
.flow-steps {{
    display: flex; align-items: center; justify-content: center;
    gap: 0.4rem; flex-wrap: wrap; margin: 0.8rem 0 0;
    font-size: 0.76rem; color: var(--muted);
}}
.flow-step {{ background: var(--fi-bg); border: 1px solid var(--border); border-radius: 8px; padding: 0.2rem 0.55rem; }}
.flow-arrow {{ color: var(--accent); font-weight: bold; }}

/* ── Cards ── */
.card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 16px; padding: 1.3rem; margin-bottom: 0.9rem;
    transition: background 0.3s, border-color 0.3s;
}}
.card-label {{
    font-family: 'Syne', sans-serif; font-size: 0.67rem; font-weight: 700;
    letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.75rem;
}}

/* ── Drag & Drop zone ── */
.drop-zone {{
    border: 2px dashed var(--border); border-radius: 14px;
    background: {T['drop_bg']}; padding: 2.2rem 1rem; text-align: center;
    transition: border-color 0.2s, background 0.2s; cursor: pointer;
    position: relative;
}}
.drop-zone:hover {{ border-color: var(--accent); background: #f5a62308; }}
.drop-icon {{ font-size: 2rem; margin-bottom: 0.5rem; }}
.drop-title {{ font-family: 'Syne', sans-serif; font-size: 0.95rem; font-weight: 700; color: var(--text); }}
.drop-sub {{ font-size: 0.78rem; color: var(--muted); margin-top: 0.25rem; }}
.drop-badge {{
    display: inline-block; background: var(--fi-bg); border: 1px solid var(--border);
    border-radius: 6px; font-size: 0.7rem; padding: 0.15rem 0.5rem;
    color: var(--muted); margin-top: 0.5rem;
}}

/* ── File info grid ── */
.file-info-grid {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.6rem; margin-top: 0.4rem;
}}
.fi-box {{
    background: var(--fi-bg); border: 1px solid var(--border);
    border-radius: 10px; padding: 0.6rem 0.5rem; text-align: center;
}}
.fi-box .fi-val {{ font-size: 1.05rem; font-weight: 700; color: var(--accent); font-family: 'Syne', sans-serif; }}
.fi-box .fi-lbl {{ font-size: 0.67rem; color: var(--muted); margin-top: 0.12rem; }}

/* ── Waveform container ── */
.waveform-wrap {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 14px; padding: 1.2rem 1rem 0.8rem;
    margin: 0.8rem 0;
}}
.waveform-label {{
    font-family: 'Syne', sans-serif; font-size: 0.67rem; font-weight: 700;
    letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.6rem;
}}
#waveform-canvas {{
    width: 100%; height: 80px; border-radius: 8px;
    background: {T['input_bg']}; display: block;
}}
.waveform-controls {{
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 0.6rem; font-size: 0.78rem; color: var(--muted);
}}
.wf-time {{ font-family: 'Syne', sans-serif; font-size: 0.82rem; color: var(--accent); font-weight: 700; }}

/* ── Badges ── */
.translate-badge {{
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: linear-gradient(135deg, #7c3aed22, #a855f722);
    border: 1px solid #7c3aed55; color: var(--purple);
    font-size: 0.74rem; font-weight: 600;
    padding: 0.28rem 0.8rem; border-radius: 100px; margin: 0.35rem 0;
}}
.info-badge {{
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: #38bdf811; border: 1px solid #38bdf833; color: var(--info);
    font-size: 0.72rem; font-weight: 500;
    padding: 0.25rem 0.75rem; border-radius: 100px; margin: 0.25rem 0;
}}

/* ── Textarea ── */
[data-testid="stTextArea"] textarea {{
    background: var(--input-bg) !important; color: var(--text) !important;
    border: 1px solid var(--border) !important; border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important; font-size: 0.87rem !important; line-height: 1.7 !important;
}}
[data-testid="stTextArea"] textarea:focus {{ border-color: var(--accent) !important; box-shadow: 0 0 0 2px #f5a62322 !important; }}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    background: var(--card) !important; border-radius: 12px !important;
    padding: 0.3rem !important; gap: 0.2rem !important; border: 1px solid var(--border) !important;
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
    background: transparent !important; color: var(--muted) !important;
    border-radius: 8px !important; font-family: 'Syne', sans-serif !important;
    font-size: 0.8rem !important; font-weight: 600 !important;
    padding: 0.38rem 1rem !important; border: none !important;
}}
[data-testid="stTabs"] [aria-selected="true"] {{
    background: linear-gradient(135deg, var(--accent), var(--accent2)) !important; color: #0d0d0f !important;
}}

/* ── History ── */
.hist-card {{
    background: var(--hist-bg); border: 1px solid var(--border);
    border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
    display: flex; justify-content: space-between; align-items: center;
}}
.hist-info .hist-name {{ font-family: 'Syne', sans-serif; font-size: 0.88rem; font-weight: 700; color: var(--text); }}
.hist-info .hist-meta {{ font-size: 0.73rem; color: var(--muted); margin-top: 0.12rem; }}
.hist-badge {{ font-size: 0.68rem; font-weight: 600; padding: 0.18rem 0.55rem; border-radius: 100px; border: 1px solid; }}
.hist-badge.en {{ color: var(--info); border-color: #38bdf844; background: #38bdf811; }}
.hist-badge.hi {{ color: var(--purple); border-color: #c084fc44; background: #c084fc11; }}

/* ── Inputs ── */
div[data-baseweb="select"] > div {{
    background: var(--input-bg) !important; border-color: var(--border) !important;
    color: var(--text) !important; border-radius: 10px !important;
}}
[data-testid="stSelectbox"] label {{ color: var(--muted) !important; font-size: 0.82rem !important; }}
[data-testid="stNumberInput"] label {{ color: var(--muted) !important; font-size: 0.82rem !important; }}
[data-testid="stNumberInput"] input {{
    background: var(--input-bg) !important; color: var(--text) !important;
    border-color: var(--border) !important; border-radius: 8px !important;
}}

/* ── File uploader ── */
[data-testid="stFileUploader"] {{
    border: 2px dashed {T['drop_border']} !important; border-radius: 12px !important;
    background: {T['drop_bg']} !important;
}}
[data-testid="stFileUploader"]:hover {{ border-color: var(--accent) !important; }}
[data-testid="stFileUploaderDropzone"] {{ background: transparent !important; }}
[data-testid="stFileUploader"] section {{ padding: 1.5rem !important; }}
[data-testid="stFileUploader"] section > div {{ gap: 0.5rem !important; }}

/* ── Buttons ── */
div[data-testid="stButton"] > button {{
    background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
    color: #0d0d0f !important; font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important; font-size: 0.93rem !important;
    border: none !important; border-radius: 12px !important; height: 2.9rem !important;
    box-shadow: 0 4px 18px #f5a62330 !important; transition: opacity 0.2s, transform 0.1s !important; width: 100%;
}}
div[data-testid="stButton"] > button:hover {{ opacity: 0.87 !important; transform: translateY(-1px) !important; }}

/* ── Progress ── */
[data-testid="stProgress"] > div > div {{
    background: linear-gradient(90deg, var(--accent), var(--accent2)) !important; border-radius: 100px !important;
}}
[data-testid="stProgress"] {{ background: var(--border) !important; border-radius: 100px !important; }}

/* ── Result card ── */
.result-card {{
    background: linear-gradient(135deg, #3ecf8e12, #3ecf8e05);
    border: 1px solid #3ecf8e44; border-radius: 16px; padding: 1.3rem; margin-top: 0.8rem; text-align: center;
}}
.result-card h3 {{ color: var(--success) !important; font-size: 1.02rem !important; margin-bottom: 0.25rem !important; }}
.result-card p {{ color: var(--muted); font-size: 0.84rem; margin-bottom: 0.9rem; }}
.stats-row {{ display: flex; gap: 0.55rem; margin-top: 0.65rem; flex-wrap: wrap; justify-content: center; }}
.stat-pill {{
    background: var(--fi-bg); border: 1px solid var(--border); border-radius: 8px;
    padding: 0.3rem 0.7rem; font-size: 0.74rem; color: var(--muted);
}}
.stat-pill span {{ color: var(--text); font-weight: 500; }}

/* ── Download button ── */
div[data-testid="stDownloadButton"] > button {{
    background: transparent !important; color: var(--success) !important;
    border: 1.5px solid var(--success) !important; font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important; border-radius: 12px !important; height: 2.9rem !important; width: 100%;
}}
div[data-testid="stDownloadButton"] > button:hover {{ background: #3ecf8e12 !important; }}

/* ── Audio ── */
audio {{ width: 100%; border-radius: 10px; margin-top: 0.3rem; }}
[data-testid="stAudio"] {{
    background: var(--input-bg); border-radius: 12px; padding: 0.5rem; border: 1px solid var(--border);
}}

/* ── Misc ── */
.status-text {{ font-size: 0.82rem; color: var(--muted); text-align: center; margin-top: 0.35rem; font-style: italic; }}
.divider {{ height: 1px; background: var(--border); margin: 1rem 0; }}
.footer {{ text-align: center; color: var(--muted); font-size: 0.73rem; padding: 1.8rem 0 1rem; }}
.empty-history {{ text-align: center; color: var(--muted); padding: 2.5rem 1rem; font-size: 0.86rem; }}
</style>
""", unsafe_allow_html=True)

# ── Waveform JS ───────────────────────────────────────────────────────────────
WAVEFORM_JS = """
<script>
(function() {
    // Wait for audio element to exist
    function initWaveform() {
        const audioEls = document.querySelectorAll('audio');
        const canvas = document.getElementById('waveform-canvas');
        const timeEl = document.getElementById('wf-current');
        const durEl = document.getElementById('wf-duration');
        const progressEl = document.getElementById('wf-progress-bar');

        if (!canvas || audioEls.length === 0) {
            setTimeout(initWaveform, 400);
            return;
        }

        // Use the last audio element (main result)
        const audio = audioEls[audioEls.length - 1];
        const ctx = canvas.getContext('2d');
        const W = canvas.offsetWidth || 600;
        const H = 80;
        canvas.width = W;
        canvas.height = H;

        const BAR_COUNT = 80;
        const accent = '%s';

        // Generate pseudo-random static waveform bars
        const bars = [];
        for (let i = 0; i < BAR_COUNT; i++) {
            const seed = Math.sin(i * 127.1 + 311.7) * 43758.5453;
            bars.push(0.15 + Math.abs(seed - Math.floor(seed)) * 0.75);
        }

        function fmt(s) {
            const m = Math.floor(s / 60);
            const sec = Math.floor(s %% 60);
            return m + ':' + String(sec).padStart(2, '0');
        }

        function drawWave(progress) {
            ctx.clearRect(0, 0, W, H);
            const gap = 2;
            const bw = (W - gap * (BAR_COUNT - 1)) / BAR_COUNT;
            for (let i = 0; i < BAR_COUNT; i++) {
                const x = i * (bw + gap);
                const h = bars[i] * H * 0.85;
                const y = (H - h) / 2;
                const done = i / BAR_COUNT <= progress;
                ctx.fillStyle = done ? accent : (accent + '44');
                ctx.beginPath();
                ctx.roundRect(x, y, bw, h, 2);
                ctx.fill();
            }
        }

        drawWave(0);

        audio.addEventListener('timeupdate', function() {
            const p = audio.duration ? audio.currentTime / audio.duration : 0;
            drawWave(p);
            if (timeEl) timeEl.textContent = fmt(audio.currentTime);
            if (progressEl) progressEl.style.width = (p * 100) + '%%';
        });

        audio.addEventListener('loadedmetadata', function() {
            if (durEl) durEl.textContent = fmt(audio.duration);
        });

        canvas.addEventListener('click', function(e) {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const p = x / rect.width;
            if (audio.duration) audio.currentTime = p * audio.duration;
        });
    }
    setTimeout(initWaveform, 800);
})();
</script>
""" % T['waveform_color']


# ── Constants ─────────────────────────────────────────────────────────────────
VOICES = {
    "English": {
        "Jenny (Female, US) 🇺🇸": "en-US-JennyNeural",
        "Guy (Male, US) 🇺🇸": "en-US-GuyNeural",
        "Sonia (Female, UK) 🇬🇧": "en-GB-SoniaNeural",
        "Ryan (Male, UK) 🇬🇧": "en-GB-RyanNeural",
    },
    "Hindi 🇮🇳 (Auto-Translate)": {
        "Swara (Female) 🇮🇳": "hi-IN-SwaraNeural",
        "Madhur (Male) 🇮🇳": "hi-IN-MadhurNeural",
    }
}

SPEED_OPTIONS = {
    "0.75× Slow": "-25%",
    "1× Normal": "+0%",
    "1.25× Fast": "+25%",
    "1.5× Faster": "+50%",
}

VOICE_SAMPLE_TEXT = {
    "English": "Hello! This is a preview of how your audio will sound. I will read your PDF in this voice.",
    "Hindi 🇮🇳 (Auto-Translate)": "नमस्ते! यह आपकी ऑडियो का एक नमूना है। मैं आपकी पीडीएफ इसी आवाज़ में पढूंगा।"
}

MAX_HISTORY = 5


# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_text_from_pdf(uploaded_file, page_start=None, page_end=None):
    uploaded_file.seek(0)
    with pdfplumber.open(uploaded_file) as pdf:
        total_pages = len(pdf.pages)
        start = (page_start - 1) if page_start else 0
        end = min(page_end if page_end else total_pages, total_pages)
        pages_text = [p.extract_text().strip() for p in pdf.pages[start:end] if p.extract_text()]
    return "\n\n".join(pages_text), total_pages


def get_pdf_info(uploaded_file):
    uploaded_file.seek(0, 2)
    size_bytes = uploaded_file.tell()
    uploaded_file.seek(0)
    size_mb = round(size_bytes / (1024 * 1024), 2)
    with pdfplumber.open(uploaded_file) as pdf:
        total_pages = len(pdf.pages)
        sample = "".join(p.extract_text() or "" for p in pdf.pages[:3])
    words = len(sample.split())
    avg = words / min(3, total_pages) if total_pages else 150
    est_words = int(avg * total_pages)
    return {"pages": total_pages, "size_mb": size_mb, "est_words": est_words, "est_minutes": int(round(est_words / 130))}


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,!?;:\-\'\"()\u0900-\u097F]', '', text)
    return text.strip()


def translate_to_hindi(text, progress_bar, status):
    CHUNK = 4500
    sentences = re.split(r'(?<=[.!?])\s+', text)
    batches, cur = [], ""
    for s in sentences:
        if len(cur) + len(s) + 1 <= CHUNK:
            cur += s + " "
        else:
            if cur: batches.append(cur.strip())
            cur = s + " "
    if cur: batches.append(cur.strip())
    translator = GoogleTranslator(source='en', target='hi')
    parts, total = [], len(batches)
    for i, batch in enumerate(batches):
        parts.append(translator.translate(batch))
        progress_bar.progress(35 + int((i + 1) / total * 25))
        status.markdown(f'<p class="status-text">🌐 Translating... ({i+1}/{total} parts)</p>', unsafe_allow_html=True)
    return " ".join(parts)


async def gen_chunk(text, voice, rate, path):
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


async def gen_all(chunks, voice, rate, base):
    paths = [f"{base}_c{i}.mp3" for i in range(len(chunks))]
    await asyncio.gather(*[gen_chunk(c, voice, rate, p) for c, p in zip(chunks, paths)])
    return paths


def gen_parallel(chunks, voice, rate, base):
    return asyncio.run(gen_all(chunks, voice, rate, base))


def smart_chunk(text, size=8000):
    sents = re.split(r'(?<=[।.!?])\s+', text)
    chunks, cur = [], ""
    for s in sents:
        if len(cur) + len(s) < size: cur += s + " "
        else:
            if cur: chunks.append(cur.strip())
            cur = s + " "
    if cur: chunks.append(cur.strip())
    return chunks or [text]


def make_audio(text, voice_id, rate):
    chunks = smart_chunk(text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        base, path = tmp.name.replace(".mp3", ""), tmp.name
    if len(chunks) == 1:
        asyncio.run(gen_chunk(text, voice_id, rate, path))
    else:
        cps = gen_parallel(chunks, voice_id, rate, base)
        with open(path, "wb") as out:
            for cp in cps:
                if os.path.exists(cp):
                    out.write(open(cp, "rb").read())
                    os.unlink(cp)
    data = open(path, "rb").read()
    os.unlink(path)
    return data


def add_history(name, lang, voice, words, minutes, audio):
    st.session_state.history.insert(0, {
        "name": name, "lang": lang, "voice": voice,
        "words": words, "minutes": minutes, "audio": audio,
        "time": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    })
    st.session_state.history = st.session_state.history[:MAX_HISTORY]


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

# ── Theme toggle (top right) ──────────────────────────────────────────────────
col_spacer, col_toggle = st.columns([5, 1])
with col_toggle:
    if st.button(f"{T['toggle_icon']}", help=T['toggle_label'], use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
    <div class="hero-badge">🎧 Free · No API Key · Premium Features</div>
    <h1>PDF to Audio<br>Converter</h1>
    <p>Upload any English PDF — listen in English or auto-translated natural Hindi.</p>
    <div class="flow-steps">
        <span class="flow-step">📄 PDF</span><span class="flow-arrow">→</span>
        <span class="flow-step">✏️ Preview & Edit</span><span class="flow-arrow">→</span>
        <span class="flow-step">🌐 Translate</span><span class="flow-arrow">→</span>
        <span class="flow-step">🎵 Waveform Audio</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_convert, tab_history = st.tabs(["🎙️  Convert", "🕘  History"])

with tab_convert:

    # ── Upload ────────────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-label">📄 Step 1 — Upload PDF</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Drag & drop your PDF here, or click to browse",
        type=["pdf"],
        label_visibility="collapsed",
        help="Supports text-based PDFs. Max recommended: 50MB."
    )
    if uploaded_file is None:
        st.markdown("""
        <div style="text-align:center;padding:0.5rem 0 0.2rem;color:var(--muted);font-size:0.78rem;">
            🗂️ &nbsp;Drag & drop a <strong style="color:var(--text)">PDF file</strong> above, or click to browse &nbsp;·&nbsp; Max 50MB
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── File info ─────────────────────────────────────────────────────────────
    if uploaded_file is not None:
        if uploaded_file.name != st.session_state.last_filename:
            with st.spinner("Reading file..."):
                info = get_pdf_info(uploaded_file)
                st.session_state.pdf_info = info
                st.session_state.last_filename = uploaded_file.name
                st.session_state.preview_ready = False
                st.session_state.extracted_text = ""
                st.session_state.last_audio_bytes = None
        else:
            info = st.session_state.pdf_info

        st.markdown(f"""
        <div class="card">
            <div class="card-label">📊 File Info — {uploaded_file.name}</div>
            <div class="file-info-grid">
                <div class="fi-box"><div class="fi-val">{info['pages']}</div><div class="fi-lbl">Pages</div></div>
                <div class="fi-box"><div class="fi-val">{info['size_mb']} MB</div><div class="fi-lbl">Size</div></div>
                <div class="fi-box"><div class="fi-val">{info['est_words']:,}</div><div class="fi-lbl">Est. Words</div></div>
                <div class="fi-box"><div class="fi-val">~{info['est_minutes']} min</div><div class="fi-lbl">Est. Audio</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Settings ──────────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-label">⚙️ Step 2 — Settings</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        language = st.selectbox("Output Language", list(VOICES.keys()), index=0)
    with col2:
        voice_label = st.selectbox("Voice", list(VOICES[language].keys()))

    is_hindi = "Hindi" in language
    voice_id = VOICES[language][voice_label]

    if is_hindi:
        st.markdown('<div class="translate-badge">🌐 English PDF → Auto-Translated → Hindi Audio</div>', unsafe_allow_html=True)

    # Voice preview
    if st.button(f"🔊 Preview Voice — {voice_label.split('🇺🇸')[0].split('🇬🇧')[0].split('🇮🇳')[0].strip()}"):
        with st.spinner("Generating sample..."):
            try:
                sample = make_audio(VOICE_SAMPLE_TEXT[language], voice_id, "+0%")
                st.session_state.voice_sample_bytes = sample
                st.session_state.voice_sample_label = voice_label
            except Exception as e:
                st.error(f"Preview failed: {e}")

    if st.session_state.voice_sample_bytes and st.session_state.voice_sample_label == voice_label:
        st.markdown('<div class="info-badge">🎧 Voice Sample Preview</div>', unsafe_allow_html=True)
        st.audio(st.session_state.voice_sample_bytes, format="audio/mp3")

    col3, col4 = st.columns(2)
    with col3:
        speed_label = st.selectbox("Speed", list(SPEED_OPTIONS.keys()), index=1)
    with col4:
        convert_mode = st.selectbox("Convert", ["Full PDF", "Page Range"], index=0)

    page_start, page_end = None, None
    if convert_mode == "Page Range":
        c5, c6 = st.columns(2)
        with c5: page_start = st.number_input("From Page", min_value=1, value=1, step=1)
        with c6: page_end = st.number_input("To Page", min_value=1, value=10, step=1)
        st.caption("💡 10–20 pages at a time is fastest")

    st.markdown('</div>', unsafe_allow_html=True)
    rate = SPEED_OPTIONS[speed_label]

    # ── Preview & Edit ────────────────────────────────────────────────────────
    if uploaded_file is not None:
        st.markdown('<div class="card"><div class="card-label">✏️ Step 3 — Preview & Edit Text (Optional)</div>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:0.81rem;color:var(--muted);margin-bottom:0.65rem;">Extract text first, then trim or fix it before generating audio.</p>', unsafe_allow_html=True)

        c_ext, c_clr = st.columns([3, 1])
        with c_ext:
            if st.button("Extract & Preview Text", use_container_width=True):
                with st.spinner("Extracting..."):
                    try:
                        raw, _ = extract_text_from_pdf(uploaded_file, page_start, page_end)
                        st.session_state.extracted_text = clean_text(raw)
                        st.session_state.preview_ready = True
                    except Exception as e:
                        st.error(f"Extraction failed: {e}")
        with c_clr:
            if st.button("Clear", use_container_width=True):
                st.session_state.extracted_text = ""
                st.session_state.preview_ready = False
                st.rerun()

        if st.session_state.preview_ready and st.session_state.extracted_text:
            wc = len(st.session_state.extracted_text.split())
            st.markdown(f'<div class="info-badge">📝 {wc:,} words — edit below if needed</div>', unsafe_allow_html=True)
            edited = st.text_area("", value=st.session_state.extracted_text, height=240, label_visibility="collapsed", key="editor")
            st.session_state.extracted_text = edited

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Generate ──────────────────────────────────────────────────────────────
    st.markdown('<div style="margin-top:0.8rem"></div>', unsafe_allow_html=True)
    gen_clicked = st.button("🎙️ Generate Audio", use_container_width=True)

    if gen_clicked:
        if uploaded_file is None:
            st.warning("⚠️ Upload a PDF first.")
        else:
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            pb = st.progress(0)
            status = st.empty()
            try:
                if st.session_state.preview_ready and st.session_state.extracted_text.strip():
                    status.markdown('<p class="status-text">✏️ Using your edited text...</p>', unsafe_allow_html=True)
                    pb.progress(20)
                    clean = st.session_state.extracted_text.strip()
                else:
                    status.markdown('<p class="status-text">📖 Extracting text...</p>', unsafe_allow_html=True)
                    pb.progress(10)
                    raw, _ = extract_text_from_pdf(uploaded_file, page_start, page_end)
                    if not raw.strip():
                        st.error("❌ No text found — PDF may be scanned/image-based.")
                        st.stop()
                    pb.progress(20)
                    clean = clean_text(raw)

                word_count = len(clean.split())
                est_min = round(word_count / 130, 1)

                if is_hindi:
                    status.markdown('<p class="status-text">🌐 Translating English → Hindi...</p>', unsafe_allow_html=True)
                    pb.progress(28)
                    final_text = translate_to_hindi(clean, pb, status)
                else:
                    final_text = clean
                    pb.progress(35)

                chunks = smart_chunk(final_text)
                status.markdown(f'<p class="status-text">⚡ Generating audio ({len(chunks)} chunk(s) in parallel)...</p>', unsafe_allow_html=True)
                pb.progress(65)

                audio_bytes = make_audio(final_text, voice_id, rate)
                pb.progress(100)
                status.empty()

                # Store for waveform
                st.session_state.last_audio_bytes = audio_bytes
                pdf_name = uploaded_file.name.replace(".pdf", "")
                lang_tag = "hindi" if is_hindi else "english"
                audio_filename = f"{pdf_name}_{lang_tag}_audio.mp3"
                lang_display = "Hindi 🇮🇳" if is_hindi else "English 🇺🇸"
                voice_name = voice_label.split(" 🇮🇳")[0].split(" 🇺🇸")[0].split(" 🇬🇧")[0].strip()

                add_history(pdf_name, lang_display, voice_name, word_count, est_min, audio_bytes)

                st.markdown(f"""
                <div class="result-card">
                    <h3>✅ Audio Ready!</h3>
                    <p>{"Translated from English to Hindi and converted to audio." if is_hindi else "Converted to English audio successfully."}</p>
                    <div class="stats-row">
                        <div class="stat-pill">Words <span>{word_count:,}</span></div>
                        <div class="stat-pill">~Duration <span>{est_min} min</span></div>
                        <div class="stat-pill">Language <span>{lang_display}</span></div>
                        <div class="stat-pill">Voice <span>{voice_name}</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # ── Waveform Player ────────────────────────────────────────────
                st.markdown(f"""
                <div class="waveform-wrap">
                    <div class="waveform-label">🎵 Audio Waveform Player — click to seek</div>
                    <canvas id="waveform-canvas"></canvas>
                    <div class="waveform-controls">
                        <span class="wf-time"><span id="wf-current">0:00</span> / <span id="wf-duration">--:--</span></span>
                        <span style="font-size:0.72rem;color:var(--muted)">Click waveform to seek · Use player below to play/pause</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.audio(audio_bytes, format="audio/mp3")

                # Inject waveform JS
                st.components.v1.html(WAVEFORM_JS, height=0)

                st.download_button(
                    "⬇️ Download MP3",
                    data=audio_bytes,
                    file_name=audio_filename,
                    mime="audio/mpeg",
                    use_container_width=True,
                )

            except Exception as e:
                pb.empty()
                status.empty()
                st.error(f"❌ Error: {str(e)}")

# ── History Tab ───────────────────────────────────────────────────────────────
with tab_history:
    st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown("""
        <div class="empty-history">
            🕘<br><br>
            <strong>No conversions yet</strong><br>
            Your last 5 converted files will appear here.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f'<p style="font-size:0.78rem;color:var(--muted);margin-bottom:0.9rem;">{len(st.session_state.history)} of {MAX_HISTORY} slots used</p>', unsafe_allow_html=True)
        for i, e in enumerate(st.session_state.history):
            badge = "hi" if "Hindi" in e["lang"] else "en"
            st.markdown(f"""
            <div class="hist-card">
                <div class="hist-info">
                    <div class="hist-name">📄 {e['name']}</div>
                    <div class="hist-meta">{e['time']} · {e['words']:,} words · ~{e['minutes']} min · {e['voice']}</div>
                </div>
                <span class="hist-badge {badge}">{e['lang']}</span>
            </div>""", unsafe_allow_html=True)
            ca, cb = st.columns(2)
            with ca:
                st.audio(e["audio"], format="audio/mp3")
            with cb:
                st.download_button("⬇️ Download", e["audio"], f"{e['name']}_audio.mp3",
                                   "audio/mpeg", use_container_width=True, key=f"dl_{i}_{e['time']}")

        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.history = []
            st.rerun()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    Built By Shaurya · Edge TTS · Google Translate · pdfplumber · Streamlit<br>
    English PDF → Hindi Audio 🇮🇳 &nbsp;|&nbsp; English Audio 🇺🇸🇬🇧
</div>
""", unsafe_allow_html=True)