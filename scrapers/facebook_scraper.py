"""
Facebook Marketplace Scraper — Auto Bergamo
Usa Playwright con sessione persistente.

Primo avvio:  apre browser visibile → attende login automatico → sessione salvata
Avvii dopo:   headless automatico, nessun intervento richiesto

Installazione (una sola volta):
    pip install playwright
    playwright install chromium
"""

import re
import sys
import time
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SESSION_DIR = Path(__file__).parent.parent / "data" / "fb_session"

# URL Marketplace veicoli — geolocalizzazione browser puntata su Bergamo
FB_URL = "https://www.facebook.com/marketplace/vehicles?sortBy=creation_time_descend"

_BRANDS = [
    "Alfa Romeo", "Audi", "BMW", "Citroen", "Citroën", "Dacia", "Fiat",
    "Ford", "Honda", "Hyundai", "Jeep", "Kia", "Land Rover", "Lancia",
    "Maserati", "Mazda", "Mercedes", "Mini", "Mitsubishi", "Nissan",
    "Opel", "Peugeot", "Porsche", "Range Rover", "Renault", "Seat",
    "Skoda", "Smart", "Suzuki", "Tesla", "Toyota", "Volkswagen", "Volvo",
    # alias corti
    "VW", "Alfa",
]

_DEALER_SIGNALS = [
    "srl", "s.r.l", "spa", "s.p.a", "snc", "concessionari",
    "autosalone", "dealer", "motors", "autoshop", "autocentro",
    "car center", "gruppo", "group", "motor", "automarket", "showroom",
]

_NON_AUTO_KW = [
    # Moto
    "tmax", "husqvarna", "cagiva", "aprilia", "triumph",
    "harley", "suzuki gsxr", "honda cbr", "kawasaki z",
    "ducati", "benelli", "ktm exc", "ktm duke", "mv agusta",
    "bmw gs", "bmw r ", "enduro", "motocross", "quad ",
    # Camper/furgoni
    "camper", "hymer", "furgone", "motorhome",
    # Barche
    "barca", "gommone", "natante",
    # Immobili
    "cascinale", "appartamento", "affitto", "terreno",
    # Elettronica e oggetti
    "televisore", "tv samsung", "tv lg", "tv sharp",
    "monopattino", "inmotion", "scarpiera", "armadio",
    "cerchi da ", "pneumatici", "ricambi auto",
    "iphone", "samsung galaxy", "playstation",
    # Casa/immobili
    "casa in vendita", "villa in vendita", "in oltrepo",
    # Moto (brand o modello)
    "sx-f", "exc ", " exc", "ktm sx",
]


def _parse_price(text: str) -> tuple:
    """Ritorna (prezzo_grezzo, valore_intero)."""
    m = re.search(r'[€$]\s*[\d\.,]+|[\d\.,]+\s*[€$]', text)
    if not m:
        return "", 0
    raw = m.group(0).strip()
    num = re.sub(r'[^\d]', '', raw)
    val = int(num) if num else 0
    # Sanity check: prezzi auto tra 200€ e 300.000€
    if val > 0 and not (200 <= val <= 300000):
        return raw, 0
    return raw, val


def _parse_year_km(text: str) -> tuple:
    """Ritorna (anno, km) dal testo libero."""
    year, km = 0, 0
    y = re.search(r'\b(20[0-2]\d|199\d)\b', text)
    if y:
        year = int(y.group())
    k = re.search(r'([\d\.]+)\s*km', text, re.IGNORECASE)
    if k:
        km = int(k.group(1).replace('.', '').replace(',', ''))
    return year, km


def _parse_brand(title: str) -> str:
    t = title.lower()
    for b in _BRANDS:
        if b.lower() in t:
            return "Volkswagen" if b == "VW" else ("Alfa Romeo" if b == "Alfa" else b)
    return ""


def _is_dealer(title: str) -> bool:
    t = title.lower()
    return any(s in t for s in _DEALER_SIGNALS)


def _close_overlays(page):
    """Chiude popup/modal di Facebook: cookie, login overlay, notifiche, ecc."""
    try:
        # 1. Cookie consent
        for sel in [
            'button[data-cookiebanner="accept_button"]',
            '[aria-label="Consenti tutti i cookie"]',
            'button:has-text("Consenti tutti i cookie")',
            'button:has-text("Accetta tutti")',
        ]:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(1)
                break

        # 2. Modal "Altro su Facebook" / login overlay — chiudi con X
        for sel in [
            '[aria-label="Chiudi"]',
            '[aria-label="Close"]',
            'div[role="dialog"] [aria-label="Chiudi"]',
        ]:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(1)
                print("  → Chiuso overlay Facebook")
                break

        # 3. Premi Escape per chiudere qualsiasi modal rimasto
        page.keyboard.press("Escape")
        time.sleep(0.5)

    except Exception:
        pass


def _check_logged_in(page) -> bool:
    """Verifica se la sessione è ancora valida."""
    url = page.url
    return "login" not in url and "checkpoint" not in url


def _set_location_bergamo(page) -> bool:
    """
    Imposta la posizione su Bergamo nell'interfaccia di Facebook Marketplace.
    Clicca sul bottone della città corrente (es. 'San Francisco · 65 km'),
    poi digita 'Bergamo' e seleziona Bergamo, Lombardia.
    """
    try:
        # Il bottone location ha il pattern "CittàCorrente\n · XX km"
        # Cerca tutti i div e trova quello con " · " e "km"
        loc_btn = None
        for el in page.query_selector_all("div"):
            try:
                txt = el.inner_text()
                if txt and " · " in txt and "km" in txt and len(txt) < 60:
                    loc_btn = el
                    break
            except Exception:
                continue

        if not loc_btn:
            print("  [!] Bottone posizione non trovato — uso location dell'account")
            return False

        print(f"  → Cambio posizione da: {loc_btn.inner_text()!r:.50}")
        loc_btn.click()
        time.sleep(2)

        # Dopo il click appare un input per la città
        location_input = None
        for sel in [
            'input[placeholder*="città"]',
            'input[placeholder*="city"]',
            'input[placeholder*="posizione"]',
            'input[placeholder*="location"]',
            'input[type="text"]',
        ]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                location_input = el
                break

        if not location_input:
            print("  [!] Input città non apparso dopo click")
            return False

        location_input.fill("")
        location_input.type("Bergamo", delay=80)
        time.sleep(2)

        # Seleziona "Bergamo, Lombardia" dai suggerimenti
        suggestions = page.query_selector_all('[role="option"], [role="listitem"]')
        for s in suggestions:
            txt = (s.inner_text() or "").lower()
            if "bergamo" in txt and ("lombardia" in txt or "italia" in txt or "bg" in txt):
                s.click()
                time.sleep(2)
                print("  [✓] Posizione impostata su Bergamo, Lombardia")
                return True

        # Fallback: primo risultato con "bergamo"
        for s in suggestions:
            if "bergamo" in (s.inner_text() or "").lower():
                s.click()
                time.sleep(2)
                print("  [✓] Posizione impostata su Bergamo")
                return True

        print("  [!] Nessun suggerimento Bergamo trovato")
        return False

    except Exception as e:
        print(f"  [!] Errore impostazione posizione: {e}")
        return False


def scrape_facebook(max_items: int = 60) -> list:
    """
    Scrapa Facebook Marketplace auto zona Bergamo.
    Ritorna lista di lead nel formato standard del progetto.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    except ImportError:
        print("  [!] Playwright non installato.")
        print("  [!] Esegui nel terminale:")
        print("      pip install playwright")
        print("      playwright install chromium")
        return []

    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSION_DIR / "state.json"
    first_run = not session_file.exists()

    leads = []

    with sync_playwright() as p:

        # ── Primo avvio: browser visibile per login manuale ──────────────────
        if first_run:
            print("\n  [!] PRIMO AVVIO FACEBOOK — si apre il browser Chrome")
            print("  [!]  → Fai login su Facebook nel browser")
            print("  [!]  → Il programma continua automaticamente dopo il login\n")
            ctx = p.chromium.launch_persistent_context(
                str(SESSION_DIR),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 800},
                locale="it-IT",
            )
            page = ctx.new_page()
            page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
            # Aspetta che appaia un elemento presente SOLO da loggato (max 5 minuti)
            print("  [!] In attesa del login (hai 5 minuti)...")
            page.wait_for_selector(
                '[aria-label="Il tuo profilo"], [aria-label="Your profile"], '
                '[aria-label="Messenger"], [aria-label="Account"], '
                '[data-testid="blue_bar_profile_link"], '
                'a[href*="/me/"], a[href*="profile.php"]',
                timeout=300000,
            )
            time.sleep(2)
            ctx.storage_state(path=str(session_file))
            print("  [✓] Login confermato — sessione salvata\n")

        # ── Avvii successivi: headless con sessione salvata ──────────────────
        else:
            ctx = p.chromium.launch_persistent_context(
                str(SESSION_DIR),
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
                locale="it-IT",
                # Spoof geolocation su Bergamo per forzare listing locali
                geolocation={"latitude": 45.6983, "longitude": 9.6773},
                permissions=["geolocation"],
            )
            page = ctx.new_page()

        # ── Naviga al Marketplace ────────────────────────────────────────────
        print("  → Caricamento Facebook Marketplace...")
        try:
            page.goto(FB_URL, wait_until="domcontentloaded", timeout=35000)
        except PwTimeout:
            print("  [!] Timeout caricamento pagina Facebook")
            ctx.close()
            return []

        _close_overlays(page)
        time.sleep(2)

        # Controlla se la sessione è scaduta
        if not _check_logged_in(page):
            print("  [!] Sessione Facebook scaduta — elimina data/fb_session/ e rilancia")
            session_file.unlink(missing_ok=True)
            ctx.close()
            return []

        # ── Imposta posizione Bergamo nell'interfaccia ───────────────────────
        _set_location_bergamo(page)
        time.sleep(3)

        # ── Scroll per caricare più annunci ──────────────────────────────────
        print("  → Scroll pagina per caricare annunci...")
        for i in range(12):
            page.evaluate("window.scrollBy(0, 1800)")
            time.sleep(0.9)

        # ── Estrazione listing ───────────────────────────────────────────────
        listing_els = page.query_selector_all('a[href*="/marketplace/item/"]')
        print(f"  → Trovati {len(listing_els)} annunci")

        seen_urls = set()
        scrape_timestamp = datetime.now().isoformat()

        for el in listing_els:
            if len(leads) >= max_items:
                break
            try:
                href = el.get_attribute("href") or ""
                if not href:
                    continue

                url = (
                    f"https://www.facebook.com{href}"
                    if href.startswith("/")
                    else href
                )
                # Pulisci parametri query e normalizza
                url = url.split("?")[0].rstrip("/") + "/"

                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Testo grezzo del link (contiene titolo, prezzo, location)
                raw_text = (el.inner_text() or "").strip()
                if not raw_text or len(raw_text) < 5:
                    continue

                lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

                # ── Parsing titolo / prezzo / location ───────────────────────
                # Struttura tipica FB Marketplace:
                #   "€ 12.500\nGolf 2019 1.6 TDI\nBergamo" oppure
                #   "Golf 2019\n€12.500\nDalmine"
                price_raw, price_value = "", 0
                title = ""
                location = ""

                for line in lines:
                    has_price = bool(re.search(r'[€$]|^\d{3,6}$', line))
                    if has_price and not price_raw:
                        price_raw, price_value = _parse_price(line)
                        if not price_raw:
                            price_raw = line
                    elif not title and len(line) > 3 and not has_price:
                        title = line
                    elif title and not location and len(line) > 1:
                        location = line

                if not title:
                    continue

                # Salta annunci del partner / pubblicità
                if "annuncio del partner" in title.lower():
                    continue

                full_text = " ".join(lines)
                full_text_check = full_text.lower()

                if any(kw in full_text_check for kw in _NON_AUTO_KW):
                    continue

                year, km = _parse_year_km(full_text)
                brand = _parse_brand(title)
                seller_type = "dealer" if _is_dealer(title) else "privato"

                # Filtro positivo: deve avere almeno un segnale auto
                has_brand = bool(brand)
                has_year = year >= 1980
                has_car_price = 500 <= price_value <= 150000
                if not (has_brand or has_year or has_car_price):
                    continue

                lead = {
                    "fonte": "facebook.com",
                    "url": url,
                    "title": title[:200],
                    "description": " | ".join(lines[:5]),
                    "price_raw": price_raw,
                    "price_value": price_value,
                    "location": location or "Bergamo area",
                    "phone": "",
                    "brand": brand,
                    "year": year,
                    "km": km,
                    "budget": 0,
                    "seller_type": seller_type,
                    "scraped_at": scrape_timestamp,
                    "published_date": "",
                }
                leads.append(lead)

            except Exception:
                continue

        ctx.close()

    privati = sum(1 for l in leads if l["seller_type"] == "privato")
    print(f"  [OK] Facebook Marketplace: {len(leads)} lead ({privati} privati, {len(leads)-privati} dealer)")
    return leads


if __name__ == "__main__":
    results = scrape_facebook(max_items=30)
    print(f"\n--- RIEPILOGO ({len(results)} lead) ---")
    for l in results[:15]:
        print(f"  [{l['seller_type']:8}] {l['brand']:15} {l['year']}  {l['km']:>6}km  {l['price_raw']:>10}  {l['location']}")
        print(f"           {l['title'][:70]}")
