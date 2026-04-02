"""
Scraper per AutoScout24.it - Annunci auto usate Bergamo
Estrae i dati dal JSON embedded nella pagina (Next.js __NEXT_DATA__)
Nessuna autenticazione necessaria.
"""

import requests
import re
import json
import time
import random
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config as cfg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Ricerca: auto usate zona Bergamo — CAP e raggio letti da config.json
def _build_base_url():
    cap = cfg.get("cap_ricerca", "24100")
    raggio = cfg.get("raggio_km", 30)
    return (
        f"https://www.autoscout24.it/lst/"
        f"?atype=C&cy=I&zipc={cap}&zipr={raggio}&ustate=N%2CU"
        f"&sort=age&desc=1&size=20&page={{page}}"
    )

BASE_URL = _build_base_url()

BRANDS = [
    "Fiat", "Volkswagen", "BMW", "Mercedes", "Audi", "Alfa Romeo", "Lancia",
    "Ford", "Opel", "Renault", "Peugeot", "Citroen", "Toyota", "Hyundai",
    "Kia", "Nissan", "Seat", "Skoda", "Volvo", "Jeep", "Dacia", "Tesla",
    "Porsche", "Maserati", "Honda", "Mazda", "Suzuki", "Mitsubishi",
]


def get_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.text
        print(f"  [!] HTTP {resp.status_code}")
        return None
    except Exception as e:
        print(f"  [!] Errore richiesta: {e}")
        return None


DEALER_SIGNALS = [
    "concessionaria", "autosalone", "codice veicolo", "dek:[", "iva al 22%",
    "prezzo + iva", "iva esclusa", "iva esposta", "finanziamenti personalizzati",
    "leasing personalizzati", "valutazione gratuita", "prenota un test drive",
    "contattaci", "vieni a trovarci", "sede", "showroom", "stock",
]

def _detect_seller_type(api_type, description):
    """Restituisce 'privato' o 'dealer' in base ai segnali nel testo."""
    if api_type and "private" in api_type.lower():
        return "privato"
    if api_type and any(w in api_type.lower() for w in ("dealer", "professional", "business")):
        return "dealer"
    desc_lower = (description or "").lower()
    if any(sig in desc_lower for sig in DEALER_SIGNALS):
        return "dealer"
    return "privato"


def fetch_description(url):
    """Visita la pagina dettaglio annuncio e restituisce descrizione + telefono."""
    try:
        html = get_page(url)
        if not html:
            return "", ""

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html, re.DOTALL
        )
        if not match:
            return "", ""

        data = json.loads(match.group(1))
        detail = data.get("props", {}).get("pageProps", {}).get("listingDetails", {})

        # Descrizione — rimuove tag HTML e decodifica entità
        raw_desc = detail.get("description", "") or ""
        description = re.sub(r"<[^>]+>", " ", raw_desc)
        description = re.sub(r"\s+", " ", description).strip()
        # Decodifica entità HTML comuni
        description = (description
            .replace("&#x27;", "'").replace("&#39;", "'")
            .replace("&amp;", "&").replace("&quot;", '"')
            .replace("&lt;", "<").replace("&gt;", ">")
            .replace("&nbsp;", " "))
        description = description[:600]

        # Telefono e tipo venditore
        seller = detail.get("seller", {}) or {}
        phone = seller.get("phone", "") or ""
        seller_type = seller.get("type", "") or seller.get("accountType", "") or ""

        return description, phone, seller_type
    except Exception:
        return "", "", ""


def extract_listings_from_html(html):
    """Estrae gli annunci dal JSON __NEXT_DATA__ embedded nella pagina."""
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL
    )
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    # Naviga nella struttura Next.js fino agli annunci
    props = data.get("props", {}).get("pageProps", {})

    # AutoScout24 può usare strutture diverse — proviamo le chiavi comuni
    listings_raw = (
        props.get("listings") or
        props.get("initialData", {}).get("listings") or
        props.get("searchResponse", {}).get("listings") or
        []
    )

    # Fallback: cerca ricorsivamente una lista di dizionari con "id" e "vehicle"
    if not listings_raw:
        text = json.dumps(props)
        # Estrai direttamente i blocchi listing dal JSON grezzo
        blocks = re.findall(r'\{"id":"[0-9]+","vehicle":\{.*?\}(?:,"prices":\{.*?\})?', text)
        if blocks:
            listings_raw = []
            for b in blocks:
                try:
                    listings_raw.append(json.loads(b + "}"))
                except Exception:
                    pass

    return listings_raw


def parse_listing(item):
    """Converte un annuncio AutoScout24 nel formato lead standard."""
    try:
        # URL
        url_path = item.get("url", "") or ""
        url = f"https://www.autoscout24.it{url_path}" if url_path else ""

        # Dati veicolo
        vehicle = item.get("vehicle", {}) or {}
        make = vehicle.get("make", "") or ""
        model = vehicle.get("model", "") or ""
        variant = vehicle.get("modelVersionInput", "") or vehicle.get("subtitle", "") or ""
        fuel = vehicle.get("fuel", "") or ""
        transmission = vehicle.get("transmission", "") or ""

        # Anno: da vehicleDetails (es. "07/2019") oppure regex sul testo
        year = 0
        for detail in (item.get("vehicleDetails") or []):
            if detail.get("ariaLabel") == "Anno":
                y_match = re.search(r"\b(20[0-2][0-9]|199[0-9])\b", detail.get("data", ""))
                if y_match:
                    year = int(y_match.group())
                    break
        if not year:
            y_match = re.search(r"\b(20[0-2][0-9]|199[0-9])\b", url_path + " " + variant)
            year = int(y_match.group()) if y_match else 0

        # Chilometri: "95.000 km" → 95000
        km_raw = vehicle.get("mileageInKm", "") or ""
        km_match = re.search(r"([\d\.]+)", km_raw)
        km = int(km_match.group(1).replace(".", "")) if km_match else 0

        # Titolo
        title = f"{make} {model}".strip()
        if variant:
            title += f" — {variant[:50]}"

        # Prezzo
        price_data = item.get("price", {}) or {}
        price_raw = price_data.get("priceFormatted", "") or ""
        price_clean = re.sub(r"[^\d]", "", price_raw)
        price_value = int(price_clean) if price_clean else 0

        # Zona
        location_data = item.get("location", {}) or {}
        city = location_data.get("city", "") or ""
        location = city if city else "Bergamo area"

        if not make or not url:
            return None

        return {
            "fonte": "autoscout24.it",
            "url": url,
            "title": title,
            "description": f"{fuel} | {transmission} | {km_raw}".strip(" |"),
            "price_raw": price_raw,
            "price_value": price_value,
            "location": location,
            "phone": "",
            "brand": make,
            "year": year,
            "km": km,
            "budget": 0,
            "scraped_at": datetime.now().isoformat(),
            "published_date": "",
        }
    except Exception:
        return None


def _enrich_lead(lead):
    """Scarica la pagina dettaglio e arricchisce il lead (thread-safe)."""
    description, phone, seller_type = fetch_description(lead["url"])
    if description:
        lead["description"] = description
    if phone:
        lead["phone"] = phone
    lead["seller_type"] = _detect_seller_type(seller_type, description)
    return lead


def scrape_autoscout24(max_items=None):
    """Scrapa AutoScout24.it zona Bergamo."""
    if max_items is None:
        max_items = cfg.get("max_items_autoscout", 30)
    BASE_URL = _build_base_url()  # rilegge cap/raggio aggiornati
    print(f"\n{'='*50}")
    print("  BOT AUTO BERGAMO — Scraper AutoScout24.it")
    print(f"{'='*50}\n")

    all_leads = []
    page_num = 1

    while len(all_leads) < max_items:
        url = BASE_URL.format(page=page_num)
        print(f"[>] Pagina {page_num}: {url[:80]}")

        html = get_page(url)
        if not html:
            break

        listings_raw = extract_listings_from_html(html)
        if not listings_raw:
            print("  [!] Nessun annuncio estratto dal JSON — stop.")
            break

        count_before = len(all_leads)

        # Parse listing di base (senza dettagli)
        page_leads = [lead for item in listings_raw if (lead := parse_listing(item))]
        print(f"  → {len(page_leads)} annunci trovati, scarico dettagli in parallelo...")

        # Fetch dettagli in parallelo (3 worker = ~4x più veloce, rispetta rate limit)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(_enrich_lead, lead): lead for lead in page_leads}
            for future in as_completed(futures):
                lead = future.result()
                all_leads.append(lead)
                print(f"  [+] {lead['brand']} {lead['year']} | {lead['price_raw']} | {lead['location']}")
                if lead.get("description"):
                    print(f"      {lead['description'][:80]}")

        added = len(all_leads) - count_before
        print(f"  -> {added} lead aggiunti (totale: {len(all_leads)})")

        if added == 0:
            break

        page_num += 1
        time.sleep(random.uniform(2, 4))

    print(f"\n[OK] AutoScout24: {len(all_leads)} lead raccolti")
    return all_leads


if __name__ == "__main__":
    leads = scrape_autoscout24(max_items=20)
    print("\n--- RIEPILOGO ---")
    for l in leads[:10]:
        print(f"  * {l['brand']} {l['year']} {l['km']}km | {l['price_raw']} | {l['location']}")
        print(f"    {l['title']}")
