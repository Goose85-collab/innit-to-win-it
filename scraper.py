import json, re
from datetime import date, datetime, timezone
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth_sync
except Exception:
    stealth_sync = None

_ctx = None

def fetch(url, raw=False, cf=False):
    page = _ctx.new_page()
    if stealth_sync:
        try: stealth_sync(page)
        except Exception: pass
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if raw:
            try:
                html = resp.text()
                print(f"  fetched(raw) {url} -> {len(html)} chars")
                return html
            except Exception:
                pass
        waits = 30 if cf else 6
        for _ in range(waits):
            page.wait_for_timeout(1000)
            html = page.content()
            low = html.lower()
            if "just a moment" not in low and "checking your browser" not in low and len(html) > 5000:
                break
        html = page.content()
        flag = ""
        l = html.lower()
        if "just a moment" in l or "checking your browser" in l or "cf-challenge" in l:
            flag = " [CLOUDFLARE CHALLENGE]"
        print(f"  fetched {url} -> {len(html)} chars{flag}")
        return html
    finally:
        page.close()

def gbp(text):
    m = re.search(r"£\s*([\d,]+(?:\.\d+)?)", text)
    if m: return float(m.group(1).replace(",", ""))
    m = re.search(r"(\d+)\s*p\b", text, re.I)
    if m: return round(int(m.group(1))/100, 2)
    return None

def max_amount(text, symbol):
    amts = []
    for a in re.findall(re.escape(symbol) + r"\s*([\d,]+(?:\.\d+)?)", text):
        try: amts.append(float(a.replace(",", "")))
        except: pass
    return max(amts) if amts else 0

# ---------- Bear Competitions (£) ----------
def scrape_bear():
    BASE = "https://bearcompetitions.com"
    html = fetch(BASE +
