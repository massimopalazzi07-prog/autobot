"""
MAIN — Orchestratore principale del bot Auto Lead Bergamo

Esegui con:
  python main.py             → ciclo completo
  python main.py --stats     → solo statistiche
  python main.py --top       → mostra top lead
  python main.py --demo      → test con dati finti
"""

import sys
import os
import time

# Fix encoding UTF-8 per Windows (emoji e caratteri speciali)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Aggiungi la cartella corrente al path
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, save_leads_batch, get_top_leads, print_stats, update_stato, salva_catalogo
import config as cfg
from ai_profiler import batch_profile, print_top_leads
from scrapers.autoscout24_scraper import scrape_autoscout24
from scrapers.subito_scraper import scrape_subito
from scrapers.facebook_scraper import scrape_facebook
from scrapers.ghinzani_scraper import scrapa_catalogo
from zone_bergamo import tag_lead as tag_zona


BANNER = """
╔══════════════════════════════════════════╗
║   🚗  AUTO LEAD BERGAMO — BOT v1.0       ║
║   Lead generation per concessionarie     ║
╚══════════════════════════════════════════╝
"""


def _deduplicate_leads(leads: list) -> list:
    """
    Rimuove duplicati cross-source.
    1° criterio: URL identico
    2° criterio: stessa auto (brand + anno + prezzo ± 500€) da fonti diverse
    """
    seen_urls = set()
    seen_cars = set()
    result = []
    for lead in leads:
        url = lead.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        brand = (lead.get("brand") or "").lower().strip()
        year = lead.get("year") or 0
        price = lead.get("price_value") or 0
        # Raggruppa prezzi in bucket da 500€ per tollerare variazioni minori
        price_bucket = (price // 500) * 500
        car_key = f"{brand}_{year}_{price_bucket}"
        if brand and year and price and car_key in seen_cars:
            continue
        if brand and year and price:
            seen_cars.add(car_key)

        result.append(lead)
    return result


def run_full_pipeline(demo=False):
    """Esegue il ciclo completo: scraping → profiling → salvataggio."""
    print(BANNER)

    # 1. Inizializza database
    init_db()

    # 2. Aggiorna catalogo concessionaria da autoghinzani.it
    print("\n[FASE 0] Aggiornamento catalogo Autoghinzani...")
    try:
        auto_catalogo = scrapa_catalogo()
        salva_catalogo(auto_catalogo)
        print(f"  → {len(auto_catalogo)} auto nel catalogo")
    except Exception as e:
        print(f"  [!] Impossibile aggiornare catalogo: {e}")

    all_raw_leads = []

    if demo:
        print("[!] MODALITÀ DEMO — uso dati di esempio\n")
        all_raw_leads = _get_demo_leads()
    else:
        # 2. Scraping AutoScout24.it
        print("\n[FASE 1] Scraping AutoScout24.it...")
        autoscout24_leads = scrape_autoscout24(max_items=cfg.get("max_items_autoscout", 30))
        all_raw_leads.extend(autoscout24_leads)
        print(f"  → {len(autoscout24_leads)} lead da AutoScout24.it")

        # 3. Scraping Subito.it (Jina + regex)
        print("\n[FASE 2] Scraping Subito.it via Jina...")
        subito_leads = scrape_subito(max_pages=cfg.get("max_pagine_subito", 6))
        all_raw_leads.extend(subito_leads)
        print(f"  → {len(subito_leads)} lead da Subito.it")

        # 4. Scraping Facebook Marketplace (Playwright)
        print("\n[FASE 3] Scraping Facebook Marketplace...")
        fb_leads = scrape_facebook(max_items=60)
        all_raw_leads.extend(fb_leads)
        print(f"  → {len(fb_leads)} lead da Facebook Marketplace")

    # 5. Deduplicazione cross-source
    before_dedup = len(all_raw_leads)
    all_raw_leads = _deduplicate_leads(all_raw_leads)
    print(f"\n[TOTALE] {len(all_raw_leads)} lead unici ({before_dedup - len(all_raw_leads)} duplicati rimossi)")

    if not all_raw_leads:
        print("[!] Nessun lead trovato. Controlla la connessione.")
        return

    # 6. Tagging geografico zona Bergamo
    all_raw_leads = [tag_zona(lead) for lead in all_raw_leads]
    zone_counts = {}
    for l in all_raw_leads:
        t = l.get("zona_tipo", "generico")
        zone_counts[t] = zone_counts.get(t, 0) + 1
    print(f"  Zone: { {k: v for k, v in sorted(zone_counts.items())} }")

    # Filtra solo lead nella provincia di Bergamo
    before_geo = len(all_raw_leads)
    all_raw_leads = [l for l in all_raw_leads if l.get("zona_tipo") != "fuori_bg"]
    removed_geo = before_geo - len(all_raw_leads)
    if removed_geo:
        print(f"  [geo] Rimossi {removed_geo} lead fuori provincia BG → {len(all_raw_leads)} rimasti")

    # 4. Profiling AI
    print("\n[FASE 3] Profilazione AI con Claude...")
    profiled_leads = batch_profile(all_raw_leads, max_leads=cfg.get("max_lead_profilare", 15))

    # 5. Salvataggio database
    print("\n[FASE 4] Salvataggio nel database...")
    save_leads_batch(profiled_leads)

    # 6. Mostra risultati
    print_stats()

    # 7. Top lead pronti per il contatto
    top = get_top_leads(limit=10, min_score=6)
    if top:
        print_top_leads_from_db(top)
    else:
        # Se il profiling AI non era disponibile, mostra comunque i lead
        print_top_leads(profiled_leads, top_n=5)

    print("\n[✓] Pipeline completata!\n")


def print_top_leads_from_db(leads):
    """Stampa i top lead salvati nel DB."""
    print(f"\n{'='*55}")
    print(f"  🎯 TOP LEAD PRONTI PER IL CONTATTO")
    print(f"{'='*55}\n")

    for i, lead in enumerate(leads[:8]):
        urgenza_emoji = {"ALTA": "🔴", "MEDIA": "🟡", "BASSA": "🟢"}.get(lead.get("ai_urgenza", ""), "⚪")
        print(f"#{i+1} ── SCORE {lead.get('ai_score', '?')}/10  {urgenza_emoji} {lead.get('ai_urgenza', '')}")
        print(f"  Titolo:  {lead.get('title', '')[:65]}")
        print(f"  Fonte:   {lead.get('fonte', '')}  |  {lead.get('url', '')[:60]}")
        print(f"  Auto:    {lead.get('brand', '')} {lead.get('year', '')}  |  {lead.get('km', '')}km")
        zona_tag = lead.get("zona_tipo", "")
        zona_str = f"  [{zona_tag}]" if zona_tag else ""
        print(f"  Zona:    {lead.get('location', '')}{zona_str}")
        print(f"  Budget:  €{lead.get('ai_budget_stimato', 0) or lead.get('budget', 0)}")
        print(f"  Intento: {lead.get('ai_intento', '')}")
        
        messaggio = lead.get("ai_messaggio", "")
        if messaggio:
            print(f"\n  📱 Messaggio pronto:")
            # Indenta il messaggio
            for line in messaggio.split(". "):
                if line:
                    print(f"     {line.strip()}.")
        
        print(f"\n  [ID: {lead.get('id')}] Per segnare come contattato: "
              f"update_stato({lead.get('id')}, 'contattato')")
        print(f"\n{'─'*55}\n")


def _get_demo_leads():
    """Lead dimostrativi per testare senza scraping reale."""
    from datetime import datetime
    return [
        {
            "fonte": "subito.it", "url": "https://subito.it/demo/1",
            "title": "Vendo Volkswagen Golf 2019 benzina 62000km Bergamo",
            "description": "Vendo Golf 7 benzina 1.0 TSI, 62.000km, unico proprietario. Motivo vendita: cambio lavoro e prendo qualcosa più grande. Prezzo fisso.",
            "price_raw": "13.800€", "price_value": 13800,
            "location": "Bergamo città", "phone": "",
            "brand": "Volkswagen", "year": 2019, "km": 62000, "budget": 0,
            "scraped_at": datetime.now().isoformat(), "published_date": "2025-03-20",
        },
        {
            "fonte": "bakeca.it", "url": "https://bakeca.it/demo/2",
            "title": "Fiat 500X 2021 km 38000 Dalmine - permuta valutata",
            "description": "Auto in ottime condizioni, sempre tagliandata. Valuto permuta con SUV più grande. Ho famiglia con bambini piccoli.",
            "price_raw": "17.500€", "price_value": 17500,
            "location": "Dalmine (BG)", "phone": "333xxxxxxx",
            "brand": "Fiat", "year": 2021, "km": 38000, "budget": 0,
            "scraped_at": datetime.now().isoformat(), "published_date": "2025-03-22",
        },
        {
            "fonte": "reddit", "url": "https://reddit.com/demo/3",
            "title": "Cerco SUV usato zona Seriate, budget 20000€ massimo",
            "description": "Sono di Seriate, cerco SUV compatto o medio usato, max 80.000km, benzina o ibrido. Budget massimo 20.000€. Qualche consiglio su dove guardare?",
            "price_raw": "", "price_value": 0,
            "location": "Seriate (BG)", "phone": "",
            "brand": "", "year": 0, "km": 0, "budget": 20000,
            "scraped_at": datetime.now().isoformat(), "published_date": "2025-03-25",
        },
        {
            "fonte": "bakeca.it", "url": "https://bakeca.it/demo/4",
            "title": "Alfa Romeo Giulia 2020 diesel Treviglio - vendo urgente",
            "description": "Vendo Giulia 2.2 diesel 160cv, 55.000km, navi, telecamera. Vendo urgente per trasferimento lavoro. Prezzo trattabile.",
            "price_raw": "22.000€", "price_value": 22000,
            "location": "Treviglio (BG)", "phone": "",
            "brand": "Alfa Romeo", "year": 2020, "km": 55000, "budget": 0,
            "scraped_at": datetime.now().isoformat(), "published_date": "2025-03-18",
        },
        {
            "fonte": "subito.it", "url": "https://subito.it/demo/5",
            "title": "Toyota Yaris 2022 hybrid km 25000 Calusco d'Adda",
            "description": "Yaris hybrid quasi nuova, 25.000km. Vendo perché ho cambiato esigenze. Ideale per chi cerca risparmio carburante.",
            "price_raw": "16.900€", "price_value": 16900,
            "location": "Calusco d'Adda (BG)", "phone": "",
            "brand": "Toyota", "year": 2022, "km": 25000, "budget": 0,
            "scraped_at": datetime.now().isoformat(), "published_date": "2025-03-24",
        },
    ]


def show_stats():
    init_db()
    print_stats()


def show_top():
    init_db()
    top = get_top_leads(limit=10, min_score=1)
    if top:
        print_top_leads_from_db(top)
    else:
        print("[!] Nessun lead nel database ancora. Esegui prima: python main.py --demo")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--stats" in args:
        show_stats()
    elif "--top" in args:
        show_top()
    elif "--demo" in args:
        run_full_pipeline(demo=True)
    else:
        run_full_pipeline(demo=False)
