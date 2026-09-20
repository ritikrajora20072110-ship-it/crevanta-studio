# Crevanta Studio

> **Luxury Creator–Brand Partnership Automation Portal**  
> Powered by **100% Native Local Ollama AI** (Zero API fees, complete privacy) & **Verified Gmail SMTP/IMAP**.

---

## 🌟 Overview

**Crevanta** is an editorial-grade agency workflow engine designed for creator management, brand discovery, contact verification, and cold pitch automation.

### Key Highlights
- **100% Local Ollama AI**: Zero dependencies on commercial APIs (OpenAI/Claude). Complete data privacy and zero usage fees.
- **50-Brand Real-Time Discovery Engine**: Intelligent chunked multi-batching with deduplication to reliably discover and pitch up to 50 verified brand targets simultaneously.
- **Brand Research & Contact Verification Protocol**:
  - **Accuracy over completeness**: Never invent, assume, estimate, or guess contact info.
  - **Only official emails**: Accepts only addresses explicitly published on official brand websites or verified social profiles. Zero third-party, zero guessing.
  - **Two-layer protection**: Prompt rules + programmatic Python enforcement (`lead_verifier.py`).
  - **Brand skipping rule**: Discards unverified leads automatically when strict mode is active.
- **Unique Video Ideas Engine**:
  - Implements Crevanta's Strategic Creative Formula:  
    $$\text{Brand} \longrightarrow \text{Differentiator} \longrightarrow \text{Audience Problem/Desire} \longrightarrow \text{Creator Behaviour} \longrightarrow \text{Content Hook} \longrightarrow \text{Concept}$$
  - Mandatory 4-part breakdown: **Concept Title**, **Brand Insight**, **Creative Opportunity**, and **How It Works**.
  - Powered by 10 Concept Archetypes (*Transformation*, *Versatility*, *Challenge*, *Experiment*, *Discovery*, *Personality*, *Comparison*, *Real-life Scenario*, *Audience Participation*, *Story/Experience*).
- **Interactive Gmail Control & Diagnostics**: Live in-app SMTP/IMAP credential verification and 1-click batch dispatch or drafts mode.
- **Ollama AI Power & Control Center**: 1-click service start/stop to free Mac RAM, and instant switching between **Turbo (`llama3.2:1b`)** and **Standard (`llama3.2:latest`)**.
- **Persistent AI Talk Records**: Every conversation with the AI strategist is saved to disk with full session history and 1-click reload.

---

## 🏛️ Architecture & Modules

```
codexfile/
├── backend/
│   ├── app.py              # FastAPI server & REST API endpoints
│   ├── config.py           # Environment config & dynamic settings
│   ├── gmail_service.py    # Direct Gmail SMTP & IMAP draft engine
│   ├── lead_verifier.py    # Official website contact scanner & 2-layer rule engine
│   ├── ollama_client.py    # 50-brand chunked inference & 4-part creative strategist
│   └── storage.py          # Persistent JSON storage (creators, talks, commands, history)
├── frontend/
│   ├── index.html          # Public editorial agency website
│   ├── studio.html         # Crevanta Studio automation portal (Alabaster/Gold/Obsidian)
│   ├── app.js              # Client-side state manager, verification & batch dispatch
│   └── css/                # Custom typography and styling
├── tests/
│   ├── test_system.py      # Automated backend, verifier, and protocol unit tests (21 tests)
│   └── test_website.py     # Public portal and agency website tests
├── data/                   # Local persistent storage
├── requirements.txt        # Python dependencies
└── run.sh                  # One-click startup script
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) installed on your machine (`brew install ollama`)

### 2. Pull Recommended Models
```bash
# Turbo mode (Ultra fast, ~1.3 GB)
ollama pull llama3.2:1b

# Standard mode (Deeper editorial nuance)
ollama pull llama3.2:latest
```

### 3. Installation & Run
```bash
# Clone the repository
git clone https://github.com/ritikrajora20072110-ship-it/crevanta-studio.git
cd crevanta-studio

# Install dependencies
pip install -r requirements.txt

# Run Crevanta Studio
./run.sh
```

Open your browser at:  
👉 **[http://127.0.0.1:8000/studio](http://127.0.0.1:8000/studio)**

---

## ⚙️ Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `AI_PROVIDER` | AI engine | `ollama` |
| `OLLAMA_BASE_URL` | Local Ollama port | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Active model | `llama3.2:1b` |
| `GMAIL_USER` | Your Gmail address | — |
| `GMAIL_APP_PASSWORD` | Google 16-character App Password | — |
| `PORT` | Local web server port | `8000` |

---

## 🧪 Testing

Run all 21 automated unit tests:
```bash
python3 -m unittest discover tests -v
```

---

## 🔒 Security Notice

Never commit your `.env` file or Google App Passwords to GitHub. The `.gitignore` file is pre-configured to strictly exclude all secret keys and environment configurations.
