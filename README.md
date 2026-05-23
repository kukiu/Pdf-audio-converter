# 🎧 PDF to Audio Converter (Hindi + English)

Convert any PDF into natural-sounding audio using Microsoft Edge TTS!

##  Features
-  **Hindi** (Swara Female, Madhur Male) — best-in-class quality
-  **English** (US & UK voices, Male & Female)
-  Speed control (0.75× to 1.5×)
-  Online playback in browser
-  Download as MP3
-  Word count, estimated duration stats

---

##  Deploy on Streamlit Community Cloud (FREE)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/pdf-audio-converter.git
git push -u origin main
```

### Step 2 — Deploy on Streamlit
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click **"New app"**
4. Select your repo → branch: `main` → file: `app.py`
5. Click **Deploy** 

That's it! Free hosting, no credit card needed.

---

##  Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

##  Project Structure
```
pdf-audio-converter/
├── app.py            ← Main Streamlit app
├── requirements.txt  ← Dependencies
└── README.md         ← This file
```

---

##  Notes
- Works best with text-based PDFs (not scanned images)
- Very large PDFs are auto-split into chunks and merged
- Edge TTS requires internet connection (no API key needed)