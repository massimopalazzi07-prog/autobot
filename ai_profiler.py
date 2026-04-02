"""
AI Profiler — Analizza ogni lead con Claude API e genera:
1. Score qualità del lead (1-10)
2. Profilo cliente
3. Messaggio di contatto personalizzato
"""

import json
import re
import sys
import time
import requests
from datetime import datetime

# Importa la funzione che legge le offerte direttamente dal DB locale.
# Questo sostituisce la stringa OFFERTE_CONCESSIONARIA hardcoded:
# ora le offerte si gestiscono dalla dashboard → API → DB.
from database import build_offerte_testo, build_catalogo_testo
import config as cfg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

# API key letta da config.json (impostabile dalla dashboard)
def _get_api_key():
    return cfg.get("groq_api_key") or "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"

# ── OFFERTE FALLBACK ──────────────────────────────────────────────────────────
# Questo testo viene usato SOLO se il DB non contiene ancora offerte configurate.
# Serve a evitare che l'AI riceva un prompt vuoto durante il primo avvio.
# Una volta configurate le offerte dalla dashboard, questo fallback non viene più usato.
OFFERTE_FALLBACK = """
OFFERTE AUTOGHINZANI BERGAMO (Via Zanica 58/H):
- Citroën Nuova C3 2026 da €14.990 (benzina, economica, ideale città)
- Citroën C5 Aircross da €26.900 con rottamazione (SUV familiare)
- Peugeot 308 nuova da €22.500 (berlina moderna)
- EMC 6 SUV da €16.950 con finanziamento Full Drive
- Auto usate certificate Spoticar: vasta gamma multimarca
- Valutazione gratuita dell'usato
- Finanziamento e noleggio a lungo termine disponibili
"""


def get_offerte_testo() -> str:
    """
    Recupera il testo delle offerte da iniettare nel prompt AI.

    Strategia:
    1. Chiama build_offerte_testo() che legge direttamente dal DB locale.
    2. Se il DB ha offerte → usa quelle (sempre aggiornate dalla dashboard).
    3. Se il DB è vuoto (primo avvio, nessuna offerta configurata) → usa il
       testo OFFERTE_FALLBACK hardcoded per non bloccare l'AI.

    Questo design permette alla concessionaria di aggiornare le offerte
    dalla dashboard senza toccare il codice sorgente.
    """
    testo_db = build_offerte_testo()
    if testo_db:
        return testo_db  # Offerte configurate nel DB → usa quelle
    # Nessuna offerta nel DB → fallback al testo statico
    return OFFERTE_FALLBACK.strip()


def _fix_json_newlines(s):
    """Sostituisce newline letterali dentro i valori stringa JSON con uno spazio."""
    result = []
    in_string = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == '"' and (i == 0 or s[i - 1] != "\\"):
            in_string = not in_string
        if in_string and c in ("\n", "\r"):
            result.append(" ")
        else:
            result.append(c)
        i += 1
    return "".join(result)


def call_claude(prompt, max_tokens=800, _retry=0):
    """Chiama Groq API (compatibile OpenAI). Ritenta automaticamente se rate limited."""
    API_KEY = _get_api_key()
    if not API_KEY:
        print("  [!] API key Groq non configurata.")
        return ""

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            },
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        data = response.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]

        # Rate limit → aspetta il tempo suggerito e riprova (max 3 volte)
        error = data.get("error", {})
        if error.get("code") == "rate_limit_exceeded" and _retry < 3:
            msg = error.get("message", "")
            wait = 5.0
            match = re.search(r"try again in ([\d.]+)s", msg)
            if match:
                wait = float(match.group(1)) + 0.5
            print(f"  [~] Rate limit Groq — attendo {wait:.1f}s e riprovo...")
            time.sleep(wait)
            return call_claude(prompt, max_tokens, _retry + 1)

        print(f"  [!] Risposta Groq inattesa: {data}")
        return ""
    except Exception as e:
        print(f"  [!] Errore API Groq: {e}")
        return ""


def profile_lead(lead):
    """
    Analizza un lead con AI e restituisce profilo completo.
    """
    title = lead.get("title", "")
    description = lead.get("description", "")
    price = lead.get("price_raw", "") or str(lead.get("budget", ""))
    location = lead.get("location", "zona Bergamo")
    brand = lead.get("brand", "")
    year = lead.get("year", "")
    km = lead.get("km", "")
    fonte = lead.get("fonte", "annuncio web")
    seller_type = lead.get("seller_type", "privato")

    # Contesto zona geografica (da zone_bergamo.py + data_fetcher.py)
    zona_tipo    = lead.get("zona_tipo", "generico")
    zona_profilo = lead.get("zona_profilo", "provincia Bergamo")
    zona_reddito = lead.get("zona_reddito", 0)
    zona_eta_auto = lead.get("zona_eta_auto", 0)

    # Istruzioni score calibrate su tipo venditore + zona
    if seller_type == "dealer":
        score_rules = (
            "IMPORTANTE — questo annuncio proviene da un CONCESSIONARIO o rivenditore professionale, "
            "NON da un privato. Assegna score 3-5: il lead ha valore commerciale basso perché "
            "non è un privato che ha bisogno di assistenza. Sii onesto nel punteggio."
        )
    else:
        zona_bonus = {
            "industriale":  "zona industriale = +1 al punteggio (alta usura auto, cambio frequente)",
            "residenziale": "zona residenziale benestante = +1 al punteggio (budget elevato, cerca qualità)",
            "pendolare":    "zona pendolare = +1 al punteggio (alta mobilità, cambio regolare)",
            "montagna":     "zona montana = -1 al punteggio (distante dalla concessionaria, cambio raro)",
        }.get(zona_tipo, "")
        score_rules = f"""Questo annuncio proviene da un PRIVATO. Parti da un base di 5 e applica questi modificatori:

BONUS (alzano lo score):
+2 se intento chiaro di vendita o acquisto
+2 se menziona "urgente", "trasferimento", "cambio lavoro", "mi trasferisco"
+2 se menziona permuta ("valuto permuta", "cerco scambio")
+2 se menziona "rata", "finanziamento", "leasing"
+2 se sembra neopatentato o prima auto ("neopatentato", "prima macchina", "appena presa la patente")
+1 se budget esplicito presente
+1 se auto recente con km bassi rispetto all'anno (meno di 10.000 km/anno)
+1 se budget superiore a 15.000 euro
+1 se menziona famiglia, bambini, "ci vuole più spazio", "siamo in tre"
+1 se il telefono è presente nell'annuncio
+1 se auto aziendale in vendita
+1 se menziona altri familiari che cercano auto
+1 se donna che vende auto sportiva o di grossa cilindrata (cambio stile di vita)
+1 se annuncio pubblicato di recente (lunedì o martedì)
{zona_bonus}

PENALITÀ (abbassano lo score):
-2 se auto ha più di 150.000 km
-2 se prezzo inferiore a 4.000 euro (fuori target concessionaria)
-2 se annuncio online da più di 30 giorni (lead freddo)
-2 se auto con problemi dichiarati ("da riparare", "non marciante", "motore fuso", "incidentata")
-1 se auto ha più di 10 anni
-1 se descrizione vaga o titolo generico senza dettagli
-1 se zona montagna o generica lontana da Bergamo
-1 se prezzo molto sopra mercato (venditore irrealistico)
-1 se solo foto esterne e descrizione minima
-3 se scrive esplicitamente "no concessionarie", "no privati", "solo permuta", "no rivenditori"

Score finale deve essere tra 1 e 10. Sii preciso e differenzia: non tutti i privati valgono 8."""

    # Abbinamento catalogo: filtra le auto in base al budget grezzo del lead
    budget_lead = lead.get("budget", 0) or lead.get("price_value", 0)
    catalogo_testo = build_catalogo_testo(
        budget_max=budget_lead if budget_lead > 0 else None
    )
    # Fallback: se nessuna auto rientra nel budget, mostra tutto il catalogo
    if not catalogo_testo:
        catalogo_testo = build_catalogo_testo()

    prompt = f"""Sei un esperto di marketing automobilistico per una concessionaria a Bergamo (Autoghinzani, Via Zanica 58/H).

Analizza questo annuncio/post e restituisci SOLO un JSON valido con questa struttura:

{{
  "score": <numero 1-10>,
  "motivo_score": "<spiegazione breve del punteggio>",
  "profilo_cliente": "<descrizione del cliente in 2 righe>",
  "intento": "<VENDE | COMPRA | ENTRAMBI>",
  "urgenza": "<ALTA | MEDIA | BASSA>",
  "budget_stimato": <numero in euro, 0 se non stimabile>,
  "auto_attuale": "<marca modello anno se presente, altrimenti vuoto>",
  "interesse_probabile": "<tipo di auto che potrebbe interessargli>",
  "auto_proposta": "<marca modello e prezzo dell'auto del catalogo più adatta al lead>",
  "auto_proposta_url": "<URL esatto copiato dalla lista AUTO DISPONIBILI, dell'auto che hai scelto come proposta>",
  "messaggio_contatto": "<messaggio WhatsApp/DM personalizzato, max 2 frasi, tono amichevole, cita l'auto proposta per nome e prezzo ma NON includere URL nel testo>"
}}

ANNUNCIO DA ANALIZZARE:
Fonte: {fonte}
Tipo venditore: {seller_type.upper()}
Titolo: {title}
Descrizione: {description}
Prezzo/Budget: {price}
Zona: {location}
Tipo zona: {zona_tipo} — {zona_profilo}{f" | reddito medio zona: {zona_reddito:,}EUR" if zona_reddito else ""}{f" | eta media auto zona: {zona_eta_auto}anni" if zona_eta_auto else ""}
Auto: {brand} {year} {km}km

{score_rules}

OFFERTE DISPONIBILI IN CONCESSIONARIA:
{get_offerte_testo()}

{catalogo_testo}

Il messaggio_contatto deve:
- Essere naturale e umano, max 2 frasi, nessun emoji
- Citare la situazione specifica del lead (auto che vende o cerca)
- Menzionare l'auto proposta per nome e prezzo (es. "abbiamo una Fiat Panda 2024 a 11.900€")
- NON includere URL nel testo — il link verrà aggiunto automaticamente dopo
- Terminare con una domanda aperta
- NON menzionare mai che usi un sistema automatico

Per auto_proposta_url: copia l'URL ESATTO dalla lista AUTO DISPONIBILI dell'auto che hai scelto, senza modificarlo.

Rispondi SOLO con il JSON, nessun testo prima o dopo."""

    raw = call_claude(prompt)

    # Parsing JSON robusto
    try:
        cleaned = re.sub(r"```json|```", "", raw).strip()
        # Corregge newline letterali dentro i valori stringa JSON
        cleaned = _fix_json_newlines(cleaned)
        profile = json.loads(cleaned)
        profile["profiled_at"] = datetime.now().isoformat()
        # Applica moltiplicatore zona allo score AI (cap a 10)
        zona_peso = lead.get("zona_peso", 1.0)
        if zona_peso != 1.0:
            raw_score = profile.get("score", 5)
            profile["score"] = min(10, round(raw_score * zona_peso))
        # Appende l'URL dell'auto proposta al messaggio in modo controllato
        url_proposta = profile.get("auto_proposta_url", "").strip()
        if url_proposta and url_proposta.startswith("http"):
            profile["messaggio_contatto"] = (
                profile.get("messaggio_contatto", "").rstrip() +
                f"\n{url_proposta}"
            )
        return profile
    except Exception as e:
        print(f"  [!] Errore parsing JSON profilo: {e}")
        print(f"      Raw: {raw[:200]}")
        # Fallback base
        return {
            "score": lead.get("lead_score", 3),
            "motivo_score": "Profiling AI non disponibile",
            "profilo_cliente": title[:100],
            "intento": "VENDE",
            "urgenza": "MEDIA",
            "budget_stimato": lead.get("budget", 0),
            "auto_attuale": f"{brand} {year}".strip(),
            "interesse_probabile": "auto usata",
            "messaggio_contatto": f"Ciao! Ho visto il tuo annuncio. Posso aiutarti con la tua auto?",
            "profiled_at": datetime.now().isoformat(),
        }


def batch_profile(leads, max_leads=10):
    """
    Profila una lista di lead con AI.
    max_leads: limite per non consumare troppi token in una volta
    """
    print(f"\n{'='*50}")
    print("  AI PROFILER — Analisi lead con Claude")
    print(f"{'='*50}\n")

    profiled = []
    leads_to_process = leads[:max_leads]

    for i, lead in enumerate(leads_to_process):
        if i > 0:
            time.sleep(5)
        print(f"[>] Profilo {i+1}/{len(leads_to_process)}: {lead.get('title', '')[:50]}...")

        profile = profile_lead(lead)
        
        # Merge lead originale + profilo AI
        enriched = {**lead, "ai_profile": profile}
        profiled.append(enriched)
        
        print(f"    Score AI: {profile.get('score', '?')}/10 | "
              f"Intento: {profile.get('intento', '?')} | "
              f"Urgenza: {profile.get('urgenza', '?')}")
        print(f"    Budget stimato: €{profile.get('budget_stimato', 0)}")

    # Ordina per score AI decrescente
    profiled.sort(key=lambda x: x["ai_profile"].get("score", 0), reverse=True)

    print(f"\n[✓] Profilati {len(profiled)} lead")
    return profiled


def print_top_leads(profiled_leads, top_n=5):
    """Stampa i migliori lead con messaggio di contatto."""
    print(f"\n{'='*50}")
    print(f"  TOP {top_n} LEAD — Pronti per il contatto")
    print(f"{'='*50}\n")

    for i, lead in enumerate(profiled_leads[:top_n]):
        p = lead.get("ai_profile", {})
        print(f"#{i+1} ── SCORE {p.get('score', '?')}/10 ({'⭐'*int(p.get('score',0)//2)})")
        print(f"  Titolo:   {lead.get('title', '')[:70]}")
        print(f"  Fonte:    {lead.get('fonte', '')} | {lead.get('url', '')}")
        print(f"  Cliente:  {p.get('profilo_cliente', '')}")
        print(f"  Intento:  {p.get('intento', '')} | Urgenza: {p.get('urgenza', '')}")
        print(f"  Budget:   €{p.get('budget_stimato', 0)}")
        print(f"  Auto:     {p.get('auto_attuale', 'N/D')}")
        print(f"\n  📱 MESSAGGIO CONTATTO:")
        print(f"  {p.get('messaggio_contatto', '')}")
        print(f"\n{'-'*50}\n")


if __name__ == "__main__":
    # Test con lead demo
    demo_leads = [
        {
            "title": "Vendo Peugeot 308 2020 45000km zona Dalmine",
            "description": "Vendo la mia 308 perché devo prendere qualcosa di più grande per la famiglia. Prezzo trattabile.",
            "price_raw": "14.500€",
            "location": "Dalmine (BG)",
            "brand": "Peugeot",
            "year": 2020,
            "km": 45000,
            "fonte": "subito.it",
            "url": "https://subito.it/demo",
        },
        {
            "title": "Cerco auto usata max 15000€ zona Bergamo",
            "description": "Cerco berlina o SUV compatto, massimo 15.000€, diesel o ibrida, massimo 80.000km. Sono di Seriate.",
            "price_raw": "15.000€",
            "location": "Seriate (BG)",
            "brand": "",
            "year": 0,
            "km": 0,
            "fonte": "reddit",
            "url": "https://reddit.com/demo",
        }
    ]

    profiled = batch_profile(demo_leads)
    print_top_leads(profiled)
