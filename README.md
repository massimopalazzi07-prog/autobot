# AUTO LEAD BERGAMO — Bot v1.0

Sistema automatico di lead generation per concessionarie auto.
Trova persone che vogliono vendere/comprare auto nella zona di Bergamo,
le profila con AI e genera messaggi di contatto personalizzati.

---

## STATO ATTUALE (marzo 2026)

Il bot è funzionante end-to-end. Il flusso completo — scraping, profilazione AI,
salvataggio e visualizzazione top lead — è operativo.

**Cosa funziona:**
- Scraping AutoScout24.it (annunci auto usate zona Bergamo, raggio 30km)
- Scraping Reddit (post di acquisto/vendita in subreddit italiani)
- Profilazione AI con Groq/llama: score 1-10, intento, urgenza, budget stimato
- Generazione messaggio WhatsApp personalizzato per ogni lead
- Database SQLite con tracciamento stato contatti
- Modalità demo (--demo) per testare senza rete

**Cosa manca ancora:**
- Scraper Facebook Marketplace (richiede Playwright + autenticazione)
- Invio automatico messaggi WhatsApp Business

---

## STRUTTURA FILE

```
autobot/
├── main.py                        ← PUNTO DI PARTENZA — esegui questo
├── dashboard.py                   ← Dashboard web (Flask, porta 5000)
├── dashboard.html                 ← Interfaccia visuale lead
├── database.py                    ← Gestione SQLite (leads.db)
├── ai_profiler.py                 ← Profilazione con Groq AI (llama-3.3-70b)
├── scrapers/
│   ├── autoscout24_scraper.py     ← Scraper AutoScout24.it (JSON embedded Next.js)
│   └── reddit_scraper.py          ← Scraper Reddit (API JSON pubblica)
└── leads.db                       ← Database SQLite (si crea automaticamente)
```

---

## INSTALLAZIONE

```bash
pip install requests flask
```

Nessun'altra dipendenza richiesta.

---

## CONFIGURAZIONE

### 1. Groq API Key (LLM gratuito per il profiler AI)

Apri `ai_profiler.py` e inserisci la tua API key in `API_KEY`.

Ottienila gratis su: https://console.groq.com → API Keys → Create

Il bot usa il modello **llama-3.3-70b-versatile** (gratuito, 14.400 req/giorno).

### 2. Nessuna credenziale per gli scraper

- **AutoScout24.it** — legge il JSON embedded `__NEXT_DATA__` nella pagina, nessun account richiesto
- **Reddit** — usa le API JSON pubbliche (`/search.json`), nessun account richiesto

---

## UTILIZZO

```bash
# Ciclo completo (scraping reale da AutoScout24.it + Reddit)
python main.py

# Test con dati dimostrativi (senza rete)
python main.py --demo

# Solo statistiche database
python main.py --stats

# Mostra top lead salvati
python main.py --top

# Dashboard web visuale (apri http://localhost:5000)
python dashboard.py
```

---

## FLUSSO DEL BOT

```
1. SCRAPING
   AutoScout24.it  → annunci auto usate zona Bergamo (JSON embedded Next.js)
   Reddit          → post di persone che cercano/vendono auto

2. PROFILING AI
   Groq/llama analizza ogni lead → score 1-10, intento, urgenza, budget

3. DATABASE
   Tutto salvato in leads.db → tracciamento completo

4. OUTREACH
   Messaggi WhatsApp personalizzati pronti per ogni lead
```

---

## FONTI DATI

| Fonte | Tipo | Metodo |
|-------|------|--------|
| AutoScout24.it | Annunci vendita auto | JSON embedded nella pagina (Next.js) |
| Reddit | Post acquisto/vendita | API JSON pubblica |

### Perché AutoScout24.it e non Bakeca.it?
Bakeca.it utilizza Cloudflare con protezione aggressiva che blocca qualsiasi
client Python, incluse sessioni con cookie. AutoScout24.it espone i dati
come JSON embedded nella pagina (Next.js `__NEXT_DATA__`) senza autenticazione.

---

## STATI DEI LEAD

| Stato | Significato |
|-------|-------------|
| nuovo | Appena trovato, da contattare |
| contattato | Messaggio inviato |
| risposto | Ha risposto al contatto |
| appuntamento | Ha fissato appuntamento |
| venduto | Auto venduta |
| non_interessato | Ha rifiutato |

Per aggiornare lo stato di un lead:
```python
from database import update_stato
update_stato(lead_id=5, stato="contattato", note="Messaggio WhatsApp inviato")
```

---

## AGGIUNGERE NUOVE FONTI

Crea un nuovo file in `scrapers/` che restituisce una lista di dizionari con:

```python
{
    "fonte": "nome_fonte",
    "url": "...",
    "title": "...",
    "description": "...",
    "price_raw": "...",
    "price_value": 0,
    "location": "...",
    "brand": "...",
    "year": 0,
    "km": 0,
    "budget": 0,
}
```

---

## PROSSIMI SVILUPPI

- [ ] Scraper Facebook Marketplace (richiede Playwright)
- [ ] Invio automatico messaggi WhatsApp Business

---

## MODULO CATALOGO CONCESSIONARIA (in sviluppo)

Questo modulo aggiunge al bot la capacità di proporre ai lead auto **realmente disponibili** in concessionaria, rendendo i messaggi WhatsApp molto più efficaci e concreti.

### Obiettivo

Invece di un generico *"abbiamo auto disponibili"*, il bot genera messaggi come:

> *"Ciao Marco, ho visto che cerchi un SUV ibrido sotto i 20k — abbiamo una Jeep Renegade 2022 a 18.900€, 45.000km. Ti interessa vederla?"*

I dati vengono presi direttamente dal sito [autoghinzani.it](https://autoghinzani.it/auto/usate/) e salvati nel DB locale.

---

### STEP DA COMPLETARE

#### STEP 1 — Scraper catalogo (`scrapers/ghinzani_scraper.py`)

**Cosa fa:** scarica la pagina `/auto/usate/` di autoghinzani.it, estrae il JSON embedded nell'HTML e restituisce la lista delle auto disponibili.

**Da implementare:**
- Usa `requests` per scaricare la pagina
- Usa `BeautifulSoup` o `re` per trovare il blocco JSON embedded nell'HTML
- Ogni auto deve avere questi campi:

```python
{
    "marca": "FIAT",
    "modello": "Panda Cross 1.0 Hybrid",
    "prezzo": 14500,
    "km": 37841,
    "anno": "05/2024",
    "alimentazione": "Ibrida",
    "cambio": "Manuale",
    "carrozzeria": "Berlina",
    "url": "https://autoghinzani.it/auto/...",
}
```

**Comandi utili per testare:**
```bash
python scrapers/ghinzani_scraper.py
```

---

#### STEP 2 — Tabella DB (`database.py`)

**Cosa fa:** crea la tabella `catalogo_concessionaria` nel database SQLite esistente (`leads.db`) e fornisce funzioni per salvare e leggere le auto.

**Da aggiungere in `database.py`:**
- Tabella `catalogo_concessionaria` con colonne: `id`, `marca`, `modello`, `prezzo`, `km`, `anno`, `alimentazione`, `cambio`, `carrozzeria`, `url`, `aggiornato_il`
- Funzione `salva_catalogo(lista_auto)` — svuota e riscrive il catalogo
- Funzione `get_catalogo(budget_max=None, alimentazione=None)` — legge con filtri opzionali

---

#### STEP 3 — Endpoint API (`dashboard.py`)

**Cosa fa:** espone il catalogo tramite endpoint REST usabili dall'AI profiler.

**Endpoint da aggiungere:**
- `GET /api/catalogo` — restituisce tutte le auto (JSON)
- `GET /api/catalogo?budget_max=20000&alimentazione=Ibrida` — con filtri
- `POST /api/catalogo/aggiorna` — rilancia lo scraper e aggiorna il DB

---

#### STEP 4 — Integrazione AI profiler (`ai_profiler.py`)

**Cosa fa:** quando il profiler genera il messaggio WhatsApp per un lead, interroga il catalogo e abbina l'auto più adatta al profilo del lead.

**Logica di abbinamento:**
- Se il lead ha budget stimato → filtra `prezzo <= budget`
- Se il lead cerca un tipo specifico → filtra per `alimentazione` o `carrozzeria`
- Passa le prime 2-3 auto candidate nel prompt all'AI
- L'AI sceglie quella più pertinente e la inserisce nel messaggio

---

### STRUTTURA FILE AGGIORNATA

```
autobot/
├── main.py
├── dashboard.py                   ← + endpoint /api/catalogo
├── database.py                    ← + tabella catalogo_concessionaria
├── ai_profiler.py                 ← + abbinamento auto dal catalogo
├── scrapers/
│   ├── autoscout24_scraper.py
│   ├── reddit_scraper.py
│   └── ghinzani_scraper.py        ← NUOVO — scraper catalogo concessionaria
└── leads.db
```

---

### DIPENDENZE AGGIUNTIVE

```bash
pip install beautifulsoup4
```

(`requests` è già installato)
