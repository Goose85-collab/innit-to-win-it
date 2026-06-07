import json, re
from datetime import date
import urllib.request

BASE = "https://bearcompetitions.com"
LIST_URL = BASE + "/all-competitions"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InnitBot/1.0)"}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")

def money(text):
    m = re.search(r"£\s*([\d,]+(?:\.\d+)?)", text)
    if m: return float(m.group(1).replace(",", ""))
    m = re.search(r"(\d+)\s*p\b", text, re.I)
    if m: return round(int(m.group(1)) / 100, 2)
    return None

def parse(url):
    html = fetch(url)
    d = {"site": "Bear Competitions", "url": url}

    m = re.search(r"<title>(.*?)\s*\|\s*Bear Competitions</title>", html, re.S)
    d["prize"] = (m.group(1).strip() if m else "Unknown").replace("&amp;", "&")

    m = re.search(r"([\d,]+)\s*/\s*([\d,]+)", html)
    if not m: return None
    sold_n = int(m.group(1).replace(",", ""))
    maxn = int(m.group(2).replace(",", ""))
    if not maxn: return None
    d["maxTickets"] = maxn
    d["sold"] = round(sold_n / maxn * 100, 1)

    price = None
    m = re.search(r"text-\[28px\][^>]*>\s*(£[\d.,]+|\d+\s*p)", html)
    if m: price = money(m.group(1))
    if price is None:
        m = re.search(r"(£[\d.,]+|\d+\s*p)\s*per ticket", html, re.I)
        if m: price = money(m.group(1))
    d["price"] = price if price else 0

    # ===== UPDATED: use the "Cash Alternative" label first =====
    m = re.search(r"£?\s*([\d,]+(?:\.\d+)?)\s*Cash Alternative", html, re.I)
    if m:
        d["value"] = float(m.group(1).replace(",", ""))
    else:
        amts = [money("£" + a) for a in re.findall(r"£\s*([\d,]+(?:\.\d+)?)", d["prize"])]
        amts = [a for a in amts if a]
        d["value"] = max(amts) if amts else 0
    # ===========================================================

    m = re.search(r"draw the winner on\s*([A-Za-z]+ [A-Za-z]+ \d+)", html)
    d["drawDate"] = m.group(1) if m else ""
    return d

def main():
    html = fetch(LIST_URL)
    urls = sorted(set(re.findall(
        r'href="(https://bearcompetitions\.com/competition/[^"]+)"', html)))
    comps = []
    for u in urls:
        try:
            r = parse(u)
            if r and r.get("maxTickets"):
                comps.append(r)
        except Exception as e:
            print("skip", u, e)
    out = {"updated": str(date.today()), "competitions": comps}
    with open("data.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(comps)} competitions")

if __name__ == "__main__":
    main()
