# Bark.com AI Lead Agent

An autonomous agent that logs into Bark.com, scrapes buyer requests, scores them with **Google Gemini AI** (free), and generates personalised pitches for high-value leads.

---

## How it works

```
Playwright (auto login + scrape Bark.com)
        │
        ▼
  List of raw leads (title, description, budget, location)
        │
        ▼
  Gemini AI – scores each lead 0.0–1.0
  based on Ideal Customer Profile
        │
        ├─ score < 0.8 → logged, skipped
        │
        └─ score ≥ 0.8 → Gemini generates personalised 3-paragraph pitch
                              │
                              ▼
                      leads_output.json
```

---

## Setup

### 1. Install dependencies

```bash
pip install playwright anthropic
playwright install chromium
```

### 2. Get a FREE Gemini API key

1. Go to https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key (starts with AIzaSy...)

### 3. Create a Bark.com Pro account

1. Go to https://www.bark.com
2. Sign up as a Professional / Service Provider
3. Complete your profile (add "Web Development" as your service)
4. Note your email and password

### 4. Set your credentials

Windows:
```
set BARK_EMAIL=your@email.com
set BARK_PASSWORD=yourpassword
set GEMINI_API_KEY=AIzaSy...
```

Mac/Linux:
```bash
export BARK_EMAIL="your@email.com"
export BARK_PASSWORD="yourpassword"
export GEMINI_API_KEY="AIzaSy..."
```

### 5. Run the agent

```bash
python agent.py
```

A Chromium browser window will open — watch the agent automatically log in, browse leads, and score them in real time.

---

## Output

Results are written to `leads_output.json`:

```json
[
  {
    "lead": {
      "title": "Custom E-commerce Platform for Fashion Brand",
      "description": "...",
      "budget": "$12,000 - $20,000",
      "location": "London, UK"
    },
    "score_data": {
      "score": 0.94,
      "reasoning": "High-budget, bespoke web project with long-term agency intent.",
      "fit_signals": ["$12k-$20k budget", "custom platform", "long-term partner"],
      "red_flags": []
    },
    "pitch": "3-paragraph personalised pitch here...",
    "processed_at": "2026-03-22T10:00:00Z"
  }
]
```

---

## Bot-detection mitigations

| Technique | Where used |
|---|---|
| Random delays between actions | human_delay() — every step |
| JavaScript-based form filling | Login form — bypasses FusionAuth restrictions |
| Random mouse movements | random_mouse_move() — before clicks |
| Incremental scrolling | slow_scroll() — lead page |
| Realistic User-Agent | Browser context |
| Rate limiting between AI calls | time.sleep(10-15s) between Gemini calls |

---

## Customising the Ideal Customer Profile

Edit the IDEAL_CUSTOMER_PROFILE string in agent.py to match your niche:

```python
IDEAL_CUSTOMER_PROFILE = """
Our ideal customer:
  - Needs web development or a custom web application
  - Has a budget of at least $2,000
  - Describes a real business need (e-commerce, SaaS, etc.)
"""
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Login fails | Double-check BARK_EMAIL and BARK_PASSWORD |
| No leads scraped | Agent falls back to demo data automatically |
| Gemini 429 error | Wait 2 minutes between runs (free tier rate limit) |
| playwright install error | Run playwright install-deps first |
| Browser closes immediately | Check your internet connection |
