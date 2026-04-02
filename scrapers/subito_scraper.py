"""
Scraper Subito.it — usa Jina Reader + LLM per bypassare Cloudflare

Flusso:
  1. Jina Reader (r.jina.ai) fetcha la pagina e la converte in markdown pulito
  2. Groq/llama estrae i dati strutturati dal markdown
  3. Restituisce lista lead nel formato standard del progetto

Nessuna dipendenza extra: solo requests (già installato).
"""

import requests
import json
import re
import time
import random
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config as cfg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── CONFIG ────────────────────────────────────────────────────────────────────

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"

def _get_api_key():
    return cfg.get("groq_api_key") or "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"

JINA_BASE    = "https://r.jina.ai/"

SUBITO_BASE_URL = "https://www.subito.it/annunci-lombardia/vendita/auto/bergamo/"

def _build_pages(max_pages: int) -> list:
    """Genera le URL delle pagine Subito (paginazione ?o=N, 1-indexed)."""
    pages = [SUBITO_BASE_URL]
    for i in range(2, max_pages + 1):
        pages.append(f"{SUBITO_BASE_URL}?o={i}")
    return pages

JINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AutoLeadBot/1.0)",
    "Accept": "text/plain, text/markdown",
    "X-Return-Format": "markdown",
}


# ── JINA FETCH ────────────────────────────────────────────────────────────────

def fetch_via_jina(url: str) -> str:
    """
    Fetcha una pagina tramite Jina Reader e restituisce il contenuto markdown.
    Bypassa Cloudflare perché è Jina a fare la richiesta, non il nostro client.
    """
    jina_url = JINA_BASE + url
    try:
        resp = requests.get(jina_url, headers=JINA_HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.text
        print(f"  [!] Jina HTTP {resp.status_code} per {url[:60]}")
        return ""
    except Exception as e:
        print(f"  [!] Errore Jina: {e}")
        return ""


# ── REGEX PARSER ─────────────────────────────────────────────────────────────
# Struttura Subito nel markdown Jina:
#   [](https://www.subito.it/auto/titolo-slug-bergamo-123456789.htm)
#   ### Titolo annuncio
#   4.500€
#   Bergamo (BG)
#   Usato 03/2011 114500 Km Diesel Manuale Euro 5

BRANDS_LIST = [
    "Abarth","Alfa Romeo","Audi","BMW","Citroën","Citroen","Dacia","Fiat","Ford",
    "Honda","Hyundai","Jeep","Kia","Lancia","Land Rover","Mazda","Mercedes",
    "Mini","Mitsubishi","Nissan","Opel","Peugeot","Porsche","Renault","Seat",
    "Skoda","Smart","Suzuki","Tesla","Toyota","Volkswagen","Volvo",
]

# Alias e abbreviazioni comuni nei titoli Subito.it
BRAND_ALIASES = {
    "vw": "Volkswagen",
    "golf": "Volkswagen",
    "polo": "Volkswagen",
    "passat": "Volkswagen",
    "tiguan": "Volkswagen",
    "merc": "Mercedes",
    "alfa": "Alfa Romeo",
    "giulia": "Alfa Romeo",
    "stelvio": "Alfa Romeo",
    "benz": "Mercedes",
    "bmw": "BMW",
    "land rover": "Land Rover",
    "range rover": "Land Rover",
}

def _detect_brand(title: str) -> str:
    title_lower = title.lower()
    for b in BRANDS_LIST:
        if b.lower() in title_lower:
            return b
    for alias, brand in BRAND_ALIASES.items():
        if alias in title_lower:
            return brand
    return ""

DEALER_NAME_SIGNALS = [
    "srl", "s.r.l", "spa", "s.p.a", "snc", "s.n.c",
    "concessionari", "autosalone", "dealer", "motors",
    "autoshop", "autocentro", "autofficina", "car center",
    "group", "gruppo auto", "auto group", "motor",
    "import", "export", "automarket", "showroom",
]

def _detect_seller(title: str, details: str, km: int, year: int) -> str:
    """
    Classifica privato vs dealer con più segnali:
    - "Nuovo" nei dettagli  → dealer (auto nuova)
    - km == 0               → quasi certamente dealer
    - anno corrente/futuro con km bassi → dealer (stock nuovo)
    - nome società nel titolo → dealer
    """
    import datetime
    current_year = datetime.date.today().year

    # Auto nuova da stock → dealer
    if "Nuovo" in details:
        return "dealer"

    # 0 km → dealer (auto nuova o km non inseriti da concessionario)
    if km == 0 and year >= current_year - 1:
        return "dealer"

    # Anno corrente/futuro con km bassissimi → dealer
    if year >= current_year and km < 500:
        return "dealer"

    # Segnali nome società nel titolo
    t = title.lower()
    if any(s in t for s in DEALER_NAME_SIGNALS):
        return "dealer"

    return "privato"

def parse_markdown_listings(markdown: str) -> list:
    """
    Parser regex per gli annunci Subito.it nel formato Jina markdown.
    Formato blocco:
      [](url_annuncio)
      ### Titolo
      Prezzo€
      Città (BG)
      Usato MM/YYYY KM Km Carburante ...
    """
    items = []

    # Pattern: cattura ogni blocco annuncio
    # URL -> Titolo (###) -> Prezzo -> Località -> Dettagli
    pattern = re.compile(
        r'\[(?:[^\]]*)\]\((https://www\.subito\.it/auto/[^\)]+)\)\s*'  # URL
        r'###\s+(.+?)\n'                                                # Titolo
        r'\s*([\d\.,]+\s*€)\s*\n'                                       # Prezzo
        r'\s*(.+?\([A-Z]{2}\))\s*\n'                                    # Città
        r'\s*((?:Usato|Nuovo).+?)(?:\n|$)',                             # Dettagli
        re.MULTILINE
    )

    for m in pattern.finditer(markdown):
        url      = m.group(1).strip()
        title    = m.group(2).strip()
        price_r  = m.group(3).strip()
        location = m.group(4).strip()
        details  = m.group(5).strip()

        # Prezzo → intero
        price_v = int(re.sub(r"[^\d]", "", price_r)) if re.search(r"\d", price_r) else 0

        # Anno da dettagli "Usato 03/2011"
        year = 0
        ym = re.search(r"\b(20[0-2]\d|199\d)\b", details)
        if ym:
            year = int(ym.group(1))

        # KM da dettagli "114500 Km"
        km = 0
        km_m = re.search(r"(\d[\d\.]+)\s*[Kk]m", details)
        if km_m:
            km = int(km_m.group(1).replace(".", ""))

        items.append({
            "url":         url,
            "title":       title,
            "price_raw":   price_r,
            "price_value": price_v,
            "location":    location,
            "description": details,
            "brand":       _detect_brand(title),
            "year":        year,
            "km":          km,
            "seller_type": _detect_seller(title, details, km, year),
        })

    return items


def extract_leads_from_markdown(markdown_content: str) -> list:
    """
    Prima prova il parser regex (veloce, preciso).
    Se trova < 3 risultati, cade su LLM come fallback.
    """
    items = parse_markdown_listings(markdown_content)
    if items:
        return items

    # Fallback LLM: invia la sezione con gli annunci (salta header navigazione)
    # Cerca il primo blocco annuncio nel testo
    listing_start = markdown_content.find("https://www.subito.it/auto/")
    if listing_start == -1:
        listing_start = 0
    else:
        listing_start = max(0, listing_start - 50)

    content_slice = markdown_content[listing_start:listing_start + 8000]
    return _llm_extract(content_slice)


EXTRACT_PROMPT = """Estrai gli annunci auto da questo testo di una pagina Subito.it e restituisci SOLO un JSON array.

Per ogni annuncio:
{{"title":"...","price_raw":"4.500 €","price_value":4500,"location":"Bergamo (BG)","url":"https://...","description":"dettagli tecnici","brand":"Fiat","year":2019,"km":65000,"seller_type":"privato"}}

Usa "" e 0 per campi mancanti. Solo auto (non moto). Solo JSON array, niente altro.

TESTO:
{content}"""

def _llm_extract(content: str) -> list:
    API_KEY = _get_api_key()
    if not API_KEY or not content:
        return []
    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={"Content-Type":"application/json","Authorization":f"Bearer {API_KEY}"},
            json={"model":GROQ_MODEL,"max_tokens":2000,"temperature":0.1,
                  "messages":[{"role":"user","content":EXTRACT_PROMPT.format(content=content)}]},
            timeout=40,
        )
        raw = resp.json().get("choices",[{}])[0].get("message",{}).get("content","")
        cleaned = re.sub(r"```json|```","",raw).strip()
        s, e = cleaned.find("["), cleaned.rfind("]")
        if s == -1: return []
        items = json.loads(cleaned[s:e+1])
        return items if isinstance(items, list) else []
    except Exception as ex:
        print(f"  [!] LLM fallback error: {ex}")
        return []


# ── NORMALIZZA LEAD ───────────────────────────────────────────────────────────

def normalise(item: dict, source_url: str) -> dict | None:
    """
    Converte un item estratto dall'LLM nel formato standard del progetto.
    """
    title = str(item.get("title", "")).strip()
    if not title or len(title) < 5:
        return None

    # URL: usa quello estratto oppure la pagina sorgente
    url = str(item.get("url", "")).strip()
    if url and not url.startswith("http"):
        url = "https://www.subito.it" + url
    if not url:
        # Genera URL fittizio unico per evitare duplicati nel DB
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40]
        url  = f"https://www.subito.it/annuncio/{slug}-{int(time.time()*1000) % 999999}"

    # Prezzo
    price_raw   = str(item.get("price_raw", "")).strip()
    price_value = int(item.get("price_value", 0) or 0)
    if not price_value and price_raw:
        digits = re.sub(r"[^\d]", "", price_raw)
        price_value = int(digits) if digits else 0

    return {
        "fonte":          "subito.it",
        "url":            url,
        "title":          title,
        "description":    str(item.get("description", ""))[:500],
        "price_raw":      price_raw,
        "price_value":    price_value,
        "location":       str(item.get("location", "")).strip(),
        "phone":          "",
        "brand":          str(item.get("brand", "")).strip(),
        "year":           int(item.get("year", 0) or 0),
        "km":             int(item.get("km", 0) or 0),
        "budget":         0,
        "seller_type":    item.get("seller_type", "privato"),
        "scraped_at":     datetime.now().isoformat(),
        "published_date": "",
    }


# ── MAIN ──────────────────────────────────────────────────────────────────────

def scrape_subito(max_pages: int = 8) -> list:
    """
    Funzione principale: fetcha le pagine Subito.it via Jina,
    estrae annunci con regex, restituisce lista lead normalizzati.
    max_pages: numero di pagine da scrapare (~30 lead/pagina)
    """
    print(f"\n{'='*50}")
    print("  BOT AUTO BERGAMO — Scraper Subito.it (Jina+regex)")
    print(f"{'='*50}\n")

    all_leads  = []
    seen_titles = set()
    pages_to_scrape = _build_pages(max_pages)

    for i, page_url in enumerate(pages_to_scrape):
        print(f"[>] Pagina {i+1}/{len(pages_to_scrape)}: {page_url[40:]}")

        # 1. Fetch via Jina
        print("    → fetch Jina Reader...")
        markdown = fetch_via_jina(page_url)
        if not markdown:
            print("    [!] Nessun contenuto — skip")
            continue
        print(f"    → {len(markdown)} caratteri ricevuti")

        # 2. Estrai con regex (+ LLM fallback)
        print("    → parsing annunci...")
        items = extract_leads_from_markdown(markdown)
        print(f"    → {len(items)} annunci estratti")

        # 3. Normalizza e deduplica
        added = 0
        for item in items:
            lead = normalise(item, page_url)
            if not lead:
                continue
            # Deduplicazione per titolo
            key = lead["title"].lower()[:50]
            if key in seen_titles:
                continue
            seen_titles.add(key)
            all_leads.append(lead)
            added += 1
            print(f"    [+] {lead['brand'] or '?'} {lead['year'] or '?'} | "
                  f"{lead['price_raw'] or '—'} | {lead['location'] or '—'}")

        print(f"    → {added} lead nuovi aggiunti")

        # Pausa tra pagine
        if i < len(pages_to_scrape) - 1:
            sleep_s = random.uniform(2, 4)
            print(f"    → pausa {sleep_s:.1f}s")
            time.sleep(sleep_s)

    print(f"\n[OK] Subito.it: {len(all_leads)} lead raccolti")
    return all_leads


# ── TEST DIRETTO ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    leads = scrape_subito(max_pages=4)
    privati  = [l for l in leads if l["seller_type"] == "privato"]
    dealer   = [l for l in leads if l["seller_type"] == "dealer"]
    print(f"\n--- RIEPILOGO ({len(leads)} totali | {len(privati)} privati | {len(dealer)} dealer) ---")
    print("\n[PRIVATI]")
    for l in privati[:15]:
        print(f"  * {l['brand']} {l['year']} {l['km']}km | {l['price_raw']} | {l['location']}")
        print(f"    {l['title'][:70]}")
    print(f"\n[DEALER — esclusi dal pipeline] ({len(dealer)})")
    for l in dealer[:5]:
        print(f"  * {l['brand']} {l['year']} {l['km']}km | {l['price_raw']} | dealer")
