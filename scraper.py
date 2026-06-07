import json, re
from datetime import date, datetime, timezone
from playwright.sync_api import sync_playwright

_browser = None
_ctx = None

def fetch(url):
    page = _ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Try to wait for Cloudflare's "Just a moment" to clear
        for _ in range(15):  # up to ~15s
            page.wait_for_timeout(1000)
            html = page.content()
            low = html.lower()
            if "just a moment" not in low and "checking your browser" not in low and len(html) > 5000:
                break
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        html = page.content()
        # Diagnostic
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
    html = fetch(BASE + "/all-competitions")
    urls = sorted(set(re.findall(r'href="(https://bearcompetitions\.com/competition/[^"]+)"', html)))
    print("  bear found", len(urls), "competition links")
    comps = []
    for url in urls:
        try:
            h = fetch(url)
            d = {"site": "Bear Competitions", "url": url, "currency": "£"}
            m = re.search(r"<title>(.*?)\s*\|\s*Bear Competitions</title>", h, re.S)
            d["prize"] = (m.group(1).strip() if m else "Unknown").replace("&amp;", "&")
            m = re.search(r"([\d,]+)\s*/\s*([\d,]+)", h)
            if not m: continue
            sold_n = int(m.group(1).replace(",", ""))
            maxn = int(m.group(2).replace(",", ""))
            if not maxn: continue
            d["maxTickets"] = maxn
            d["sold"] = round(sold_n / maxn * 100, 1)
            price = None
            mm = re.search(r"text-\[28px\][^>]*>\s*(£[\d.,]+|\d+\s*p)", h)
            if mm: price = gbp(mm.group(1))
            if price is None:
                mm = re.search(r"(£[\d.,]+|\d+\s*p)\s*per ticket", h, re.I)
                if mm: price = gbp(mm.group(1))
            d["price"] = price if price else 0
            mm = re.search(r"£?\s*([\d,]+(?:\.\d+)?)\s*Cash Alternative", h, re.I)
            if mm:
                d["value"] = float(mm.group(1).replace(",", ""))
            else:
                d["value"] = max_amount(d["prize"], "£")
            mm = re.search(r"draw the winner on\s*([A-Za-z]+ [A-Za-z]+ \d+)", h)
            d["drawDate"] = mm.group(1) if mm else ""
            comps.append(d)
        except Exception as e:
            print("bear skip", url, e)
    return comps

# ---------- Ooosch (€) ----------
def scrape_ooosch():
    BASE = "https://www.ooosch.com"
    html = fetch(BASE + "/")
    comps = []
    markers = [(m.start(), m.group(1)) for m in re.finditer(r'(\w+)\.reference_id = "prod_', html)]
    markers.append((len(html), None))
    print("  ooosch found", len(markers) - 1, "product blocks")
    for i in range(len(markers) - 1):
        block = html[markers[i][0]:markers[i + 1][0]]
        status = re.search(r'\.status = "([^"]*)"', block)
        if not status or status.group(1) != "LIVE":
            continue
        title = re.search(r'\.title = "((?:[^"\\]|\\.)*)"', block)
        slug = re.search(r'\.slug = "([^"]*)"', block)
        stock = re.search(r'\.stock = (\d+)', block)
        sold = re.search(r'\.stock_sold = (\d+)', block)
        end = re.search(r'\.end_date = new Date\((\d+)\)', block)
        if not (title and slug and stock and int(stock.group(1)) > 0):
            continue
        prices = [int(p) for p in re.findall(r'price_eur: (\d+)', block) if int(p) > 0]
        price = (min(prices) / 100) if prices else 0
        maxn = int(stock.group(1))
        sold_n = int(sold.group(1)) if sold else 0
        prize = title.group(1)
        d = {
            "site": "Ooosch",
            "url": BASE + "/product/" + slug.group(1),
            "currency": "€",
            "prize": prize,
            "price": round(price, 2),
            "maxTickets": maxn,
            "sold": round(sold_n / maxn * 100, 1),
            "value": max_amount(prize, "€"),
            "drawDate": (datetime.fromtimestamp(int(end.group(1)) / 1000, tz=timezone.utc).date().isoformat() if end else "")
        }
        comps.append(d)
    return comps

def main():
    global _browser, _ctx
    all_comps = []
    with sync_playwright() as p:
        _browser = p.chromium.launch(headless=True)
        _ctx = _browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            locale="en-GB",
            viewport={"width": 1366, "height": 900},
        )
        for fn in (scrape_bear, scrape_ooosch):
            try:
                got = fn()
                all_comps += got
                print(fn.__name__, "ok", len(got))
            except Exception as e:
                print(fn.__name__, "FAILED", e)
        _browser.close()
    out = {"updated": str(date.today()), "competitions": all_comps}
    with open("data.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("Total", len(all_comps))

if __name__ == "__main__":
    main()
