# Bark.com AI Lead Agent

An autonomous agent that logs into Bark.com, scrapes buyer requests, scores them with Claude AI, and generates personalised pitches for high-value leads.

---

## How it works

```
Playwright (login + scrape)
        │
        ▼
  List of raw leads
        │
        ▼
  Claude API – scores each lead 0.0–1.0
        │
        ├─ score < 0.8 → logged, skipped
        │
        └─ score ≥ 0.8 → Claude generates 3-paragraph pitch
                              │
                              ▼
                      leads_output.json
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your Bark.com login and Anthropic API key
export $(cat .env | xargs)
```

Or set env vars directly:

```bash
export BARK_EMAIL="your@email.com"
export BARK_PASSWORD="yourpassword"
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Create a Bark.com pro account

1. Go to https://www.bark.com/en/gb/
2. Sign up as a **service provider / professional**
3. Complete your profile — this gives you access to buyer requests
4. Use those credentials in `.env`

### 4. Run the agent

```bash
python agent.py
```

A Chromium browser window will open (headless=False) so you can watch the agent work and solve any CAPTCHA if needed.

---

## Output

Results are written to `leads_output.json`:

```json
[
  {
    "lead": {
      "title": "Custom E-commerce Platform for Fashion Brand",
      "description": "...",
      "budget": "$12,000 – $20,000",
      "location": "London, UK"
    },
    "score_data": {
      "score": 0.94,
      "reasoning": "High-budget, bespoke web project with long-term agency intent.",
      "fit_signals": ["$12k–$20k budget", "custom platform", "long-term partner"],
      "red_flags": []
    },
    "pitch": "...",
    "processed_at": "2026-03-22T10:00:00Z"
  }
]
```

---

## Bot-detection mitigations

| Technique | Where used |
|---|---|
| Random delays between actions | `human_delay()` — every step |
| Character-by-character typing | `human_type()` — login form |
| Random mouse movements | `random_mouse_move()` — before clicks |
| Incremental scrolling | `slow_scroll()` — lead page |
| Realistic User-Agent | Browser context |
| Rate limiting between AI calls | `time.sleep(random …)` |

---

## Customising the Ideal Customer Profile

Edit the `IDEAL_CUSTOMER_PROFILE` string in `agent.py` to match your agency's niche. The scoring prompt feeds this directly to Claude.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Login fails | Check credentials; solve CAPTCHA manually in the open browser |
| No leads scraped | Bark may have updated their HTML — inspect the live page and update card selectors in `scrape_leads()` |
| `anthropic.AuthenticationError` | Check your `ANTHROPIC_API_KEY` |
| `playwright install` error | Run `playwright install-deps` first |
