"""
Zone Bergamo — Targeting geografico per lead auto

Ogni comune BG è classificato per:
- tipo: industriale | residenziale | pendolare | montagna
- peso: moltiplicatore priorità (0.8 – 1.3)
- note: caratteristiche del cliente-tipo in quella zona

Fonti di riferimento:
  - ACI: età media parco auto per provincia
  - ISTAT: reddito medio e struttura demografica
  - Camera di Commercio BG: densità imprese e zone industriali
  - Conoscenza locale mercato bergamasco
"""

# ─────────────────────────────────────────────────────────────────────────────
# MAPPA COMUNI → ZONA
# peso > 1.0 = zona ad alta priorità commerciale
# peso < 1.0 = zona a bassa priorità (montagna, periferia lontana)
# ─────────────────────────────────────────────────────────────────────────────

ZONE_MAP = {

    # ── ZONE INDUSTRIALI ─────────────────────────────────────────────────────
    # Operai e impiegati, uso auto quotidiano intensivo, auto >8 anni frequente
    # → cambio auto frequente, budget 8.000–18.000€, sensibili al km/usura
    "dalmine": {
        "tipo": "industriale",
        "peso": 1.30,
        "profilo": "zona industriale Tenaris + poli logistici, pendolari giornalieri, "
                   "alta usura auto, cambio ogni 5-7 anni, budget 8k-15k€"
    },
    "seriate": {
        "tipo": "industriale",
        "peso": 1.25,
        "profilo": "polo industriale + residenziale, pendolari verso BG città, "
                   "buona capacità di spesa, auto da 10k-20k€"
    },
    "stezzano": {
        "tipo": "industriale",
        "peso": 1.25,
        "profilo": "zona logistica e industriale, vicinanza autostrada A4, "
                   "clienti pratici che cercano affidabilità, budget 8k-16k€"
    },
    "zingonia": {
        "tipo": "industriale",
        "peso": 1.20,
        "profilo": "distretto industriale storico, operai e artigiani, "
                   "alta usura auto, budget contenuto 6k-12k€"
    },
    "ciserano": {
        "tipo": "industriale",
        "peso": 1.20,
        "profilo": "area Zingonia, manifattura e logistica, clienti pratici"
    },
    "osio sotto": {
        "tipo": "industriale",
        "peso": 1.20,
        "profilo": "zona Zingonia, operai, auto molto utilizzate, cambio frequente"
    },
    "verdellino": {
        "tipo": "industriale",
        "peso": 1.15,
        "profilo": "area Zingonia, manifattura, budget 7k-13k€"
    },
    "boltiere": {
        "tipo": "industriale",
        "peso": 1.15,
        "profilo": "area Zingonia, piccole industrie"
    },
    "lallio": {
        "tipo": "industriale",
        "peso": 1.15,
        "profilo": "zona industriale vicino BG, pendolari, budget medio"
    },
    "spirano": {
        "tipo": "industriale",
        "peso": 1.15,
        "profilo": "logistica e industria, pendolari"
    },
    "curno": {
        "tipo": "industriale",
        "peso": 1.20,
        "profilo": "polo commerciale + industriale nord BG, ottima accessibilità, "
                   "clienti abituati a offerte competitive, budget 10k-20k€"
    },
    "treviolo": {
        "tipo": "industriale",
        "peso": 1.20,
        "profilo": "zona industriale-residenziale, buona capacità di spesa"
    },
    "romano di lombardia": {
        "tipo": "industriale",
        "peso": 1.20,
        "profilo": "hub est-bergamasco, polo produttivo, pendolari lungo SS11, "
                   "auto molto usate, cambio ogni 6-8 anni, budget 8k-15k€"
    },

    # ── ZONE RESIDENZIALI BENESTANTI ──────────────────────────────────────────
    # Famiglie con doppio reddito, auto recente, cambio per upgrade
    # → budget 15.000–35.000€, cercano qualità/affidabilità, permuta frequente
    "bergamo": {
        "tipo": "residenziale",
        "peso": 1.20,
        "profilo": "capoluogo, mix ceti, professionisti e famiglie, "
                   "cercano auto recenti anche usate, budget 12k-30k€, "
                   "vicinanza concessionaria = vantaggio"
    },
    "ponteranica": {
        "tipo": "residenziale",
        "peso": 1.25,
        "profilo": "zona residenziale collinare benestante, famiglie con buon reddito, "
                   "auto di qualità, SUV e berlina premium, budget 18k-40k€"
    },
    "sorisole": {
        "tipo": "residenziale",
        "peso": 1.25,
        "profilo": "residenziale benestante, professionisti, amano auto recenti, "
                   "SUV familiare o berlina di fascia media-alta, budget 20k-40k€"
    },
    "mozzo": {
        "tipo": "residenziale",
        "peso": 1.25,
        "profilo": "area residenziale pregiata nord BG, professionisti e manager, "
                   "auto premium, budget 20k-45k€"
    },
    "gorle": {
        "tipo": "residenziale",
        "peso": 1.20,
        "profilo": "residenziale benestante est BG, famiglie, SUV e station wagon"
    },
    "pedrengo": {
        "tipo": "residenziale",
        "peso": 1.20,
        "profilo": "zona residenziale collinare, buona capacità di spesa"
    },
    "villa d'almè": {
        "tipo": "residenziale",
        "peso": 1.20,
        "profilo": "residenziale Valle Brembana, professionisti, auto recenti"
    },
    "almè": {
        "tipo": "residenziale",
        "peso": 1.15,
        "profilo": "Valle Brembana, residenziale, famiglie"
    },
    "scanzorosciate": {
        "tipo": "residenziale",
        "peso": 1.20,
        "profilo": "zona vitivinicola benestante, professionisti, auto di qualità"
    },

    # ── ZONE PENDOLARI ────────────────────────────────────────────────────────
    # Alta mobilità quotidiana, auto strumento di lavoro
    # → cambio ogni 5-8 anni, sensibili al km e ai consumi, budget 9k-18k€
    "treviglio": {
        "tipo": "pendolare",
        "peso": 1.20,
        "profilo": "hub est-bergamasco, treno Milano + auto, pendolari, famiglie, "
                   "auto affidabili e capienti, budget 10k-20k€"
    },
    "caravaggio": {
        "tipo": "pendolare",
        "peso": 1.15,
        "profilo": "pendolari verso Milano e BG, famiglie, uso auto intenso, "
                   "cambio ogni 6-8 anni, budget 8k-16k€"
    },
    "calusco d'adda": {
        "tipo": "pendolare",
        "peso": 1.15,
        "profilo": "pendolari Valle Adda, uso auto giornaliero intenso"
    },
    "alzano lombardo": {
        "tipo": "pendolare",
        "peso": 1.15,
        "profilo": "Valle Seriana, pendolari BG città, operai e artigiani"
    },
    "nembro": {
        "tipo": "pendolare",
        "peso": 1.10,
        "profilo": "Valle Seriana, pendolari, auto da lavoro"
    },
    "albino": {
        "tipo": "pendolare",
        "peso": 1.10,
        "profilo": "Valle Seriana media, tessile e manifattura, pendolari"
    },
    "sarnico": {
        "tipo": "pendolare",
        "peso": 1.10,
        "profilo": "Lago d'Iseo, turismo e pendolari, auto utilitarie e SUV"
    },
    "grumello del monte": {
        "tipo": "pendolare",
        "peso": 1.10,
        "profilo": "zona collinare, pendolari verso BG e BS"
    },
    "chiuduno": {
        "tipo": "pendolare",
        "peso": 1.10,
        "profilo": "pendolari BG-BS, auto utilitarie affidabili"
    },

    # ── ZONA MONTAGNA / BASSA PRIORITÀ ───────────────────────────────────────
    # Auto usate più a lungo, cambio meno frequente, distanza dalla concessionaria
    # → peso ridotto ma non zero: quando vendono, cercano 4x4 o SUV
    "clusone": {
        "tipo": "montagna",
        "peso": 0.85,
        "profilo": "Valle Seriana alta, auto usate a lungo, quando cambiano cercano 4x4 o SUV"
    },
    "lovere": {
        "tipo": "montagna",
        "peso": 0.85,
        "profilo": "Alto Lago d'Iseo, turismo e residenti, distanza da BG"
    },
    "san pellegrino terme": {
        "tipo": "montagna",
        "peso": 0.80,
        "profilo": "Valle Brembana alta, turismo, distante dalla concessionaria"
    },
    "zogno": {
        "tipo": "montagna",
        "peso": 0.85,
        "profilo": "Valle Brembana, pendolari ma distanti"
    },
    "schilpario": {
        "tipo": "montagna",
        "peso": 0.75,
        "profilo": "zona montana remota, bassa priorità"
    },
    "castione della presolana": {
        "tipo": "montagna",
        "peso": 0.75,
        "profilo": "località turistica montana, bassa priorità commerciale"
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# PROFILO CLIENTE-TIPO PER ZONA (usato nel prompt AI)
# ─────────────────────────────────────────────────────────────────────────────

TIPO_DESCRIZIONE = {
    "industriale":   "zona industriale/logistica: operaio o artigiano, uso auto intenso, budget medio, cambia frequentemente",
    "residenziale":  "zona residenziale: professionista o famiglia benestante, cerca qualità e affidabilità, budget medio-alto",
    "pendolare":     "zona pendolare: alta mobilità quotidiana, cerca auto affidabile ed economica nei consumi, budget medio",
    "montagna":      "zona montana: usa l'auto a lungo prima di cambiare, quando compra cerca robustezza/4x4, distante dalla concessionaria",
    "generico":      "provincia di Bergamo, profilo standard",
}


def _load_stats_cache() -> dict:
    """Carica zone_stats.json generato da data_fetcher.py (se esiste)."""
    try:
        from data_fetcher import load_zone_stats
        return load_zone_stats()
    except Exception:
        return {}


# Cache caricata una volta al primo import del modulo
_STATS_CACHE: dict = _load_stats_cache()


def tag_lead(lead: dict) -> dict:
    """
    Arricchisce il lead con dati zona:
      - zona_tipo:    industriale | residenziale | pendolare | montagna | generico
      - zona_peso:    float calcolato da dati reali (se disponibili) o hardcoded
      - zona_profilo: descrizione cliente-tipo + dati socioeconomici
    """
    location = (lead.get("location") or "").lower()

    for comune, data in ZONE_MAP.items():
        if comune in location:
            # Usa peso calcolato da dati reali se disponibile
            stats = _STATS_CACHE.get(comune, {})
            peso_reale = stats.get("peso")
            reddito    = stats.get("reddito_medio")
            eta_auto   = stats.get("eta_media_auto")

            peso = peso_reale if peso_reale else data["peso"]

            # Profilo arricchito con dati reali se presenti
            profilo = data["profilo"]
            if reddito and eta_auto:
                profilo += (
                    f" | reddito medio ~{reddito:,}EUR"
                    f" | eta media auto {eta_auto}anni"
                )

            lead["zona_tipo"]        = data["tipo"]
            lead["zona_peso"]        = peso
            lead["zona_profilo"]     = profilo
            lead["zona_reddito"]     = reddito or 0
            lead["zona_eta_auto"]    = eta_auto or 0
            return lead

    # Fallback: qualsiasi luogo con "bg" o "bergamo" → generico
    if "bg" in location or "bergamo" in location:
        lead["zona_tipo"]     = "generico"
        lead["zona_peso"]     = 1.0
        lead["zona_profilo"]  = TIPO_DESCRIZIONE["generico"]
        lead["zona_reddito"]  = 0
        lead["zona_eta_auto"] = 0
    else:
        # Fuori provincia? abbassa leggermente priorità
        lead["zona_tipo"]     = "fuori_bg"
        lead["zona_peso"]     = 0.90
        lead["zona_profilo"]  = "fuori provincia Bergamo, verifica se vale contattarlo"
        lead["zona_reddito"]  = 0
        lead["zona_eta_auto"] = 0

    return lead


def get_zone_summary() -> str:
    """Stampa un riepilogo delle zone configurate."""
    from collections import defaultdict
    by_type = defaultdict(list)
    for comune, data in ZONE_MAP.items():
        by_type[data["tipo"]].append(f"{comune.title()} (×{data['peso']})")

    lines = ["Zone Bergamo configurate:"]
    for tipo, comuni in sorted(by_type.items()):
        lines.append(f"  {tipo.upper()}: {', '.join(comuni)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_zone_summary())
    # Test
    test_leads = [
        {"location": "Dalmine (BG)", "title": "Test"},
        {"location": "Seriate (BG)", "title": "Test"},
        {"location": "Ponteranica (BG)", "title": "Test"},
        {"location": "Clusone (BG)", "title": "Test"},
        {"location": "Milano", "title": "Test"},
    ]
    print("\nTest tag_lead:")
    for lead in test_leads:
        tagged = tag_lead(lead)
        print(f"  {tagged['location']:25} → {tagged['zona_tipo']:15} peso={tagged['zona_peso']}")
