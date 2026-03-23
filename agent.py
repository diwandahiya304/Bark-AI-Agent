"""
Bark.com AI Lead Agent
- Logs in with Playwright (human-like behaviour)
- Scrapes buyer requests / dashboard leads
- Scores each lead with FREE Google Gemini API
- Generates personalised pitch for leads scored > 0.8
"""

import asyncio
import json
import random
import time
import os
import urllib.request
from datetime import datetime
from playwright.async_api import async_playwright, Page

# ── Config ────────────────────────────────────────────────────────────────────
BARK_EMAIL      = os.getenv("BARK_EMAIL", "your@email.com")       # your Gmail
BARK_PASSWORD   = os.getenv("BARK_PASSWORD", "")    # your Bark password
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")   # Free at aistudio.google.com

IDEAL_CUSTOMER_PROFILE = """
You are a sales-qualification assistant for a premium web-development agency.
Our ideal customer:
  - Needs web development, web design, or a custom web application
  - Has a budget of at least $2,000 (or 'open to quotes' with strong signals of high value)
  - Is located in a major English-speaking market (US, UK, Canada, Australia) - but remote is fine
  - Describes a real business need (e-commerce, SaaS, corporate site, booking platform, etc.)
  - Is NOT looking for a logo-only, SEO-only, or social-media-only service
"""

SCORE_THRESHOLD = 0.8
OUTPUT_FILE     = "leads_output.json"
# ──────────────────────────────────────────────────────────────────────────────


# ── Human-like helpers ────────────────────────────────────────────────────────

async def human_delay(min_ms: int = 400, max_ms: int = 1400):
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def random_mouse_move(page: Page):
    x = random.randint(100, 1200)
    y = random.randint(100, 700)
    await page.mouse.move(x, y, steps=random.randint(5, 20))
    await human_delay(100, 300)


async def slow_scroll(page: Page, distance: int = 400):
    steps = random.randint(4, 8)
    step_size = distance // steps
    for _ in range(steps):
        await page.mouse.wheel(0, step_size)
        await human_delay(80, 200)

# ──────────────────────────────────────────────────────────────────────────────


# ── Playwright: Login & Scrape ────────────────────────────────────────────────

async def login(page: Page):
    """
    Automated login for Bark.com (FusionAuth).
    FusionAuth shows email and password on the SAME page.
    We fill both then click the Login button.
    """
    print("[*] Navigating to Bark login page ...")
    try:
        await page.goto("https://www.bark.com/en/gb/login/", wait_until="domcontentloaded", timeout=60000)
    except Exception:
        pass
    await human_delay(2500, 4000)

    # Fill email using JavaScript to be safe
    print("[*] Filling email ...")
    await page.evaluate(f"""
        const inputs = document.querySelectorAll('input');
        for (const inp of inputs) {{
            if (inp.type === 'email' || inp.name === 'loginId' || inp.name === 'email' || inp.placeholder.toLowerCase().includes('email')) {{
                inp.value = '{BARK_EMAIL}';
                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                break;
            }}
        }}
    """)
    await human_delay(600, 1000)
    print("[+] Email filled.")

    # Fill password using JavaScript
    print("[*] Filling password ...")
    await page.evaluate(f"""
        const inputs = document.querySelectorAll('input[type="password"]');
        if (inputs.length > 0) {{
            inputs[0].value = '{BARK_PASSWORD}';
            inputs[0].dispatchEvent(new Event('input', {{bubbles: true}}));
            inputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
        }}
    """)
    await human_delay(600, 1000)
    print("[+] Password filled.")

    await random_mouse_move(page)
    await human_delay(500, 800)

    # Click login button
    print("[*] Clicking Login button ...")
    clicked = False
    for sel in ['button[type="submit"]', 'input[type="submit"]',
                'button:has-text("Login")', 'button:has-text("Log in")']:
        try:
            await page.click(sel, timeout=4000)
            print("[+] Login button clicked.")
            clicked = True
            break
        except Exception:
            continue

    if not clicked:
        # Fallback: press Enter
        await page.keyboard.press("Enter")
        print("[+] Pressed Enter to submit.")

    await page.wait_for_load_state("load", timeout=60000)
    await human_delay(2000, 3000)

    current_url = page.url or ""
    if "login" in current_url.lower():
        raise RuntimeError("Login failed — check email/password.")
    print(f"[+] Logged in! URL: {current_url}")


async def navigate_to_leads(page: Page):
    print("[*] Navigating to leads ...")
    await random_mouse_move(page)
    for attempt_url in [
        "https://www.bark.com/en/gb/pro/responses/",
        "https://www.bark.com/en/gb/dashboard/",
        "https://www.bark.com/en/gb/leads/",
    ]:
        await page.goto(attempt_url, wait_until="domcontentloaded", timeout=60000)
        await human_delay(1000, 2000)
        if "login" not in page.url.lower():
            print(f"[+] On leads page: {page.url}")
            return
    raise RuntimeError("Could not reach leads page.")


async def scrape_leads(page: Page) -> list:
    leads = []
    await slow_scroll(page, 800)
    await human_delay(600, 1200)

    card_selectors = [
        ".response-card", ".lead-card", "[data-testid='lead-card']",
        ".request-card", "article.card", ".bark-card",
    ]

    cards = []
    for sel in card_selectors:
        cards = await page.query_selector_all(sel)
        if cards:
            print(f"[+] Found {len(cards)} cards with '{sel}'")
            break

    if not cards:
        print("[!] No cards found - using demo data.")
        return get_demo_leads()

    for card in cards[:20]:
        try:
            title       = await _safe_text(card, "h2, h3, .title, .lead-title")
            description = await _safe_text(card, "p, .description, .lead-description")
            budget      = await _safe_text(card, ".budget, .price, [class*='budget']")
            location    = await _safe_text(card, ".location, [class*='location']")
            if title:
                leads.append({
                    "title": title.strip(), "description": description.strip(),
                    "budget": budget.strip(), "location": location.strip(),
                })
        except Exception as e:
            print(f"  [!] Skipped card: {e}")

    print(f"[+] Scraped {len(leads)} leads.")
    return leads if leads else get_demo_leads()


async def _safe_text(element, selector: str) -> str:
    try:
        el = await element.query_selector(selector)
        return (await el.inner_text()) if el else ""
    except Exception:
        return ""

# ──────────────────────────────────────────────────────────────────────────────


# ── Demo data ─────────────────────────────────────────────────────────────────

def get_demo_leads() -> list:
    return [
        {
            "title": "Custom E-commerce Platform for Fashion Brand",
            "description": (
                "We run a mid-sized UK fashion label and need a fully custom e-commerce site "
                "replacing our aging Magento 1 install. Must support multi-currency, "
                "personalised recommendations, AR try-on, and seamless Shopify POS integration. "
                "Timeline is 4 months. We want a long-term agency partner."
            ),
            "budget": "$12,000 - $20,000",
            "location": "London, UK",
        },
        {
            "title": "Logo design for my coffee shop",
            "description": "Need a simple logo for a small local coffee shop. Nothing fancy.",
            "budget": "$50 - $100",
            "location": "Manchester, UK",
        },
        {
            "title": "SaaS Dashboard Web App - Property Management",
            "description": (
                "We're a PropTech startup building a cloud-based property-management platform. "
                "Need a React front-end with a Node/Express API, role-based auth, real-time "
                "notifications, and Stripe billing. Seed-funded, looking for a 6-month engagement."
            ),
            "budget": "$30,000+",
            "location": "Austin, TX",
        },
        {
            "title": "WordPress blog setup",
            "description": "I need someone to install WordPress and pick a theme for my personal blog.",
            "budget": "$100 - $200",
            "location": "Remote",
        },
        {
            "title": "Booking & Scheduling Platform for Wellness Studio",
            "description": (
                "Our yoga and wellness studio currently uses pen-and-paper booking. "
                "We want a bespoke online booking system with class scheduling, membership tiers, "
                "automated reminder emails/SMS, Zoom integration for virtual classes, and a "
                "branded mobile PWA. We have a serious budget and want this done right."
            ),
            "budget": "$5,000 - $8,000",
            "location": "Toronto, Canada",
        },
    ]

# ──────────────────────────────────────────────────────────────────────────────


# ── Gemini API (FREE) ─────────────────────────────────────────────────────────

def call_gemini(prompt: str) -> str:
    """Call Google Gemini 1.5 Flash - completely free tier, no credit card needed."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1000},
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def score_lead(lead: dict) -> dict:
    prompt = f"""
{IDEAL_CUSTOMER_PROFILE}

Analyse this Bark.com lead and return ONLY a JSON object, no extra text, no markdown fences.

Lead:
  Title:       {lead['title']}
  Description: {lead['description']}
  Budget:      {lead['budget']}
  Location:    {lead['location']}

Return exactly this JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<one sentence explaining the score>",
  "fit_signals": ["<signal 1>", "<signal 2>"],
  "red_flags": ["<flag 1>"]
}}
"""
    raw = call_gemini(prompt)
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def generate_pitch(lead: dict, score_data: dict) -> str:
    prompt = f"""
You are a senior account executive at a premium web-development agency.
Write a warm, confident, 3-paragraph pitch responding to this Bark.com buyer request.

Rules:
1. Paragraph 1 - Hook: Reference AT LEAST TWO specific details from their description.
2. Paragraph 2 - Value: Why your agency is the right fit.
3. Paragraph 3 - CTA: Invite to a discovery call, pressure-free.
4. Tone: professional yet human. No buzzwords.
5. Length: 150-220 words total.

Lead:
  Title:       {lead['title']}
  Description: {lead['description']}
  Budget:      {lead['budget']}
  Location:    {lead['location']}

Fit signals: {', '.join(score_data.get('fit_signals', []))}
"""
    return call_gemini(prompt)

# ──────────────────────────────────────────────────────────────────────────────


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run():
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-GB",
        )
        page = await context.new_page()

        try:
            await login(page)
            await navigate_to_leads(page)
            leads = await scrape_leads(page)
        except Exception as e:
            print(f"[!] Browser step failed ({e}). Using demo leads.")
            leads = get_demo_leads()
        finally:
            await browser.close()

    print(f"\n[*] Scoring {len(leads)} leads with Gemini AI ...\n")

    for i, lead in enumerate(leads, 1):
        print(f"  [{i}/{len(leads)}] {lead['title'][:60]} ...")
        try:
            score_data = score_lead(lead)
            score      = score_data.get("score", 0.0)
            pitch      = None

            print(f"         Score: {score:.2f}  - {score_data.get('reasoning', '')}")

            if score >= SCORE_THRESHOLD:
                print("         [*] Above threshold - generating pitch ...")
                pitch = generate_pitch(lead, score_data)

            results.append({
                "lead": lead,
                "score_data": score_data,
                "pitch": pitch,
                "processed_at": datetime.utcnow().isoformat() + "Z",
            })

        except Exception as e:
            print(f"         [!] AI step failed: {e}")
            results.append({"lead": lead, "error": str(e)})

        time.sleep(random.uniform(15, 20))   # avoid Gemini free tier rate limit

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)

    qualified = sum(1 for r in results if r.get("pitch"))
    print(f"\n[OK] Done. {qualified}/{len(results)} leads qualified (score >= {SCORE_THRESHOLD}).")
    print(f"[OK] Results saved to -> {OUTPUT_FILE}\n")

    for r in results:
        if r.get("pitch"):
            print("=" * 70)
            print(f"LEAD:  {r['lead']['title']}")
            print(f"SCORE: {r['score_data']['score']:.2f}")
            print(f"\nPITCH:\n{r['pitch']}")
            print()


if __name__ == "__main__":
    asyncio.run(run())
