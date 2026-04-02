"""
Database Manager — Salva e gestisce tutti i lead raccolti
Usa SQLite: nessuna installazione necessaria, tutto in un file locale
"""

import sqlite3
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Risultati come dizionari
    return conn


def init_db():
    """Crea le tabelle se non esistono."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fonte           TEXT NOT NULL,
            url             TEXT UNIQUE,
            title           TEXT,
            description     TEXT,
            price_raw       TEXT,
            price_value     REAL DEFAULT 0,
            location        TEXT,
            phone           TEXT,
            brand           TEXT,
            year            INTEGER DEFAULT 0,
            km              INTEGER DEFAULT 0,
            budget          INTEGER DEFAULT 0,
            scraped_at      TEXT,
            published_date  TEXT,

            -- Profilo AI
            ai_score        INTEGER DEFAULT 0,
            ai_intento      TEXT,
            ai_urgenza      TEXT,
            ai_budget_stimato INTEGER DEFAULT 0,
            ai_auto_attuale TEXT,
            ai_profilo      TEXT,
            ai_messaggio    TEXT,
            ai_profiled_at  TEXT,

            -- Tipo venditore
            seller_type     TEXT DEFAULT 'privato',  -- privato | dealer
            zona_tipo       TEXT DEFAULT '',

            -- Stato contatto
            stato           TEXT DEFAULT 'nuovo',
            -- nuovo | contattato | risposto | appuntamento | venduto | non_interessato
            note            TEXT,
            contattato_at   TEXT,
            risposto_at     TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contatti (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id     INTEGER REFERENCES leads(id),
            canale      TEXT,   -- whatsapp | dm_subito | dm_fb | email
            messaggio   TEXT,
            inviato_at  TEXT DEFAULT (datetime('now')),
            risposta    TEXT,
            risposta_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_leads_fonte   ON leads(fonte);
        CREATE INDEX IF NOT EXISTS idx_leads_stato   ON leads(stato);
        CREATE INDEX IF NOT EXISTS idx_leads_score   ON leads(ai_score);
        CREATE INDEX IF NOT EXISTS idx_leads_brand   ON leads(brand);

        -- ── TABELLA CONCESSIONARIA ────────────────────────────────────
        -- Profilo unico della concessionaria (singleton: al massimo 1 riga).
        -- Contiene nome, indirizzo e dati di contatto da mostrare nell'AI prompt.
        CREATE TABLE IF NOT EXISTS concessionaria (
            id          INTEGER PRIMARY KEY CHECK (id = 1),  -- id fisso = 1 → singleton
            nome        TEXT NOT NULL DEFAULT '',
            indirizzo   TEXT DEFAULT '',
            telefono    TEXT DEFAULT '',
            email       TEXT DEFAULT '',
            note        TEXT DEFAULT '',          -- info extra da passare all'AI
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        -- ── TABELLA OFFERTE ───────────────────────────────────────────
        -- Catalogo delle offerte correnti della concessionaria.
        -- Ogni riga è un'offerta che l'AI usa per personalizzare i messaggi.
        CREATE TABLE IF NOT EXISTS offerte (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titolo      TEXT NOT NULL,            -- es. "Citroën C3 2026 da €14.990"
            descrizione TEXT DEFAULT '',          -- dettagli aggiuntivi, optional
            prezzo      TEXT DEFAULT '',          -- es. "€14.990" o "da €299/mese"
            tipo        TEXT DEFAULT 'nuovo',     -- 'nuovo' | 'usato' | 'servizio'
            attiva      INTEGER DEFAULT 1,        -- 1 = visibile all'AI, 0 = archiviata
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_offerte_attiva ON offerte(attiva);

        -- ── TABELLA CATALOGO CONCESSIONARIA ──────────────────────────
        -- Auto reali disponibili in concessionaria, scrapeate da autoghinzani.it
        CREATE TABLE IF NOT EXISTS catalogo_concessionaria (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo         TEXT DEFAULT 'usata',   -- usata | nuova | km0
            marca        TEXT DEFAULT '',
            modello      TEXT DEFAULT '',
            anno         TEXT DEFAULT '',
            km           INTEGER DEFAULT 0,
            alimentazione TEXT DEFAULT '',
            cambio       TEXT DEFAULT '',
            prezzo       REAL DEFAULT 0,
            url          TEXT DEFAULT '',
            aggiornato_il TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()

    # Migrazioni — aggiunge colonne su DB esistenti senza distruggere dati
    for col_sql in [
        "ALTER TABLE leads ADD COLUMN zona_tipo TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(col_sql)
            conn.commit()
        except Exception:
            # Colonna già presente → ignora l'errore silenziosamente
            pass

    conn.close()
    print(f"[✓] Database inizializzato: {DB_PATH}")


def save_lead(lead):
    """
    Salva un lead nel database.
    Se esiste già (stesso URL), aggiorna i dati.
    Restituisce l'ID del lead.
    """
    conn = get_connection()
    cursor = conn.cursor()

    profile = lead.get("ai_profile", {})

    try:
        cursor.execute("""
            INSERT INTO leads (
                fonte, url, title, description, price_raw, price_value,
                location, phone, brand, year, km, budget, scraped_at, published_date,
                seller_type, zona_tipo,
                ai_score, ai_intento, ai_urgenza, ai_budget_stimato,
                ai_auto_attuale, ai_profilo, ai_messaggio, ai_profiled_at
            ) VALUES (
                :fonte, :url, :title, :description, :price_raw, :price_value,
                :location, :phone, :brand, :year, :km, :budget, :scraped_at, :published_date,
                :seller_type, :zona_tipo,
                :ai_score, :ai_intento, :ai_urgenza, :ai_budget_stimato,
                :ai_auto_attuale, :ai_profilo, :ai_messaggio, :ai_profiled_at
            )
            ON CONFLICT(url) DO UPDATE SET
                seller_type       = excluded.seller_type,
                zona_tipo         = excluded.zona_tipo,
                ai_score          = excluded.ai_score,
                ai_intento        = excluded.ai_intento,
                ai_urgenza        = excluded.ai_urgenza,
                ai_budget_stimato = excluded.ai_budget_stimato,
                ai_auto_attuale   = excluded.ai_auto_attuale,
                ai_profilo        = excluded.ai_profilo,
                ai_messaggio      = excluded.ai_messaggio,
                ai_profiled_at    = excluded.ai_profiled_at
        """, {
            "fonte":            lead.get("fonte", ""),
            "url":              lead.get("url", f"no_url_{datetime.now().timestamp()}"),
            "title":            lead.get("title", ""),
            "description":      lead.get("description", "")[:500],
            "price_raw":        lead.get("price_raw", ""),
            "price_value":      lead.get("price_value", 0),
            "location":         lead.get("location", ""),
            "phone":            lead.get("phone", ""),
            "brand":            lead.get("brand", ""),
            "year":             lead.get("year", 0),
            "km":               lead.get("km", 0),
            "budget":           lead.get("budget", 0),
            "scraped_at":       lead.get("scraped_at", datetime.now().isoformat()),
            "published_date":   lead.get("published_date", ""),
            "seller_type":      lead.get("seller_type", "privato"),
            "zona_tipo":        lead.get("zona_tipo", ""),
            "ai_score":         profile.get("score", 0),
            "ai_intento":       profile.get("intento", ""),
            "ai_urgenza":       profile.get("urgenza", ""),
            "ai_budget_stimato":profile.get("budget_stimato", 0),
            "ai_auto_attuale":  profile.get("auto_attuale", ""),
            "ai_profilo":       profile.get("profilo_cliente", ""),
            "ai_messaggio":     profile.get("messaggio_contatto", ""),
            "ai_profiled_at":   profile.get("profiled_at", ""),
        })

        lead_id = cursor.lastrowid or get_lead_id_by_url(cursor, lead.get("url", ""))
        conn.commit()
        return lead_id

    except Exception as e:
        print(f"  [!] Errore salvataggio lead: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_lead_id_by_url(cursor, url):
    row = cursor.execute("SELECT id FROM leads WHERE url = ?", (url,)).fetchone()
    return row["id"] if row else None


def save_leads_batch(leads):
    """Salva una lista di lead e restituisce quanti ne ha salvati."""
    saved = 0
    for lead in leads:
        if save_lead(lead):
            saved += 1
    print(f"[✓] Salvati {saved}/{len(leads)} lead nel database")
    return saved


def update_stato(lead_id, stato, note=None):
    """Aggiorna lo stato di un lead."""
    conn = get_connection()
    ts = datetime.now().isoformat()
    
    updates = {"stato": stato, "lead_id": lead_id}
    sql = "UPDATE leads SET stato = :stato"
    
    if note:
        sql += ", note = :note"
        updates["note"] = note
    if stato == "contattato":
        sql += ", contattato_at = :ts"
        updates["ts"] = ts
    elif stato == "risposto":
        sql += ", risposto_at = :ts"
        updates["ts"] = ts
    
    sql += " WHERE id = :lead_id"
    conn.execute(sql, updates)
    conn.commit()
    conn.close()


def get_top_leads(limit=20, min_score=5, stato="nuovo"):
    """Restituisce i migliori lead non ancora contattati."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM leads
        WHERE ai_score >= ? AND stato = ?
        ORDER BY ai_score DESC, created_at DESC
        LIMIT ?
    """, (min_score, stato, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    """Statistiche generali del database."""
    conn = get_connection()
    stats = {}

    stats["totale"]       = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    stats["nuovi"]        = conn.execute("SELECT COUNT(*) FROM leads WHERE stato='nuovo'").fetchone()[0]
    stats["contattati"]   = conn.execute("SELECT COUNT(*) FROM leads WHERE stato='contattato'").fetchone()[0]
    stats["risposti"]     = conn.execute("SELECT COUNT(*) FROM leads WHERE stato='risposto'").fetchone()[0]
    stats["venduti"]      = conn.execute("SELECT COUNT(*) FROM leads WHERE stato='venduto'").fetchone()[0]
    stats["score_medio"]  = conn.execute("SELECT ROUND(AVG(ai_score),1) FROM leads WHERE ai_score > 0").fetchone()[0] or 0

    # Per fonte
    rows = conn.execute("SELECT fonte, COUNT(*) as n FROM leads GROUP BY fonte").fetchall()
    stats["per_fonte"] = {r["fonte"]: r["n"] for r in rows}

    # Top brand
    rows = conn.execute("""
        SELECT brand, COUNT(*) as n FROM leads
        WHERE brand != '' GROUP BY brand ORDER BY n DESC LIMIT 5
    """).fetchall()
    stats["top_brand"] = [(r["brand"], r["n"]) for r in rows]

    conn.close()
    return stats


def print_stats():
    """Stampa statistiche leggibili."""
    s = get_stats()
    print(f"\n{'='*40}")
    print("  📊 STATISTICHE DATABASE LEAD")
    print(f"{'='*40}")
    print(f"  Totale lead:      {s['totale']}")
    print(f"  Nuovi:            {s['nuovi']}")
    print(f"  Contattati:       {s['contattati']}")
    print(f"  Hanno risposto:   {s['risposti']}")
    print(f"  Venduti:          {s['venduti']}")
    print(f"  Score medio AI:   {s['score_medio']}/10")
    print(f"\n  Per fonte:")
    for fonte, n in s.get("per_fonte", {}).items():
        print(f"    • {fonte}: {n}")
    print(f"\n  Top brand:")
    for brand, n in s.get("top_brand", []):
        print(f"    • {brand}: {n}")
    print(f"{'='*40}\n")


# ── CONCESSIONARIA API HELPERS ────────────────────────────────────────────────

def get_concessionaria():
    """
    Restituisce il profilo della concessionaria (dizionario).
    Se la riga non esiste ancora, restituisce un dizionario vuoto.
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM concessionaria WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}


def upsert_concessionaria(data: dict):
    """
    Crea o sovrascrive il profilo della concessionaria.
    Usa INSERT OR REPLACE con id=1 per garantire il singleton.
    `data` deve contenere: nome, indirizzo, telefono, email, note (tutti opzionali tranne nome).
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO concessionaria (id, nome, indirizzo, telefono, email, note, updated_at)
        VALUES (1, :nome, :indirizzo, :telefono, :email, :note, :updated_at)
        ON CONFLICT(id) DO UPDATE SET
            nome       = excluded.nome,
            indirizzo  = excluded.indirizzo,
            telefono   = excluded.telefono,
            email      = excluded.email,
            note       = excluded.note,
            updated_at = excluded.updated_at
    """, {
        "nome":       data.get("nome", ""),
        "indirizzo":  data.get("indirizzo", ""),
        "telefono":   data.get("telefono", ""),
        "email":      data.get("email", ""),
        "note":       data.get("note", ""),
        "updated_at": datetime.now().isoformat(),
    })
    conn.commit()
    conn.close()


def get_offerte(solo_attive: bool = True):
    """
    Restituisce la lista delle offerte.
    `solo_attive=True` filtra solo quelle con attiva=1 (default).
    Usato dall'AI profiler per costruire il contesto delle offerte disponibili.
    """
    conn = get_connection()
    sql = "SELECT * FROM offerte"
    if solo_attive:
        sql += " WHERE attiva = 1"
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_offerta(data: dict) -> int:
    """
    Inserisce una nuova offerta.
    Restituisce l'id della riga creata.
    """
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO offerte (titolo, descrizione, prezzo, tipo, attiva)
        VALUES (:titolo, :descrizione, :prezzo, :tipo, :attiva)
    """, {
        "titolo":      data.get("titolo", ""),
        "descrizione": data.get("descrizione", ""),
        "prezzo":      data.get("prezzo", ""),
        "tipo":        data.get("tipo", "nuovo"),
        "attiva":      1 if data.get("attiva", True) else 0,
    })
    conn.commit()
    offerta_id = cur.lastrowid
    conn.close()
    return offerta_id


def delete_offerta(offerta_id: int) -> bool:
    """
    Elimina un'offerta per id.
    Restituisce True se la riga esisteva ed è stata eliminata.
    """
    conn = get_connection()
    cur = conn.execute("DELETE FROM offerte WHERE id = ?", (offerta_id,))
    conn.commit()
    deleted = cur.rowcount > 0  # rowcount = 0 se l'id non esiste
    conn.close()
    return deleted


def build_offerte_testo() -> str:
    """
    Costruisce il blocco di testo delle offerte da iniettare nel prompt AI.
    Formato leggibile per il modello LLM.
    Se non ci sono offerte nel DB, restituisce stringa vuota.
    """
    concessionaria = get_concessionaria()
    offerte = get_offerte(solo_attive=True)

    if not offerte:
        return ""  # L'ai_profiler userà il fallback hardcoded

    # Intestazione con nome e indirizzo se disponibili
    nome = concessionaria.get("nome", "Concessionaria")
    indirizzo = concessionaria.get("indirizzo", "")
    header = f"OFFERTE {nome.upper()}"
    if indirizzo:
        header += f" ({indirizzo})"
    header += ":"

    righe = [header]
    for o in offerte:
        riga = f"- {o['titolo']}"
        if o.get("prezzo"):
            riga += f" — {o['prezzo']}"
        if o.get("descrizione"):
            riga += f" ({o['descrizione']})"
        righe.append(riga)

    # Aggiungi note extra della concessionaria in fondo
    note = concessionaria.get("note", "").strip()
    if note:
        righe.append(note)

    return "\n".join(righe)


# ── CATALOGO CONCESSIONARIA ───────────────────────────────────────────────────

def salva_catalogo(lista_auto: list):
    """
    Svuota il catalogo e lo riscrive con i dati freschi dello scraper.
    Deduplica per URL prima di salvare.
    """
    # Rimuove duplicati per URL — tiene il primo occorrenza
    seen_urls = set()
    unique = []
    for a in lista_auto:
        url = a.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(a)
    lista_auto = unique

    conn = get_connection()
    conn.execute("DELETE FROM catalogo_concessionaria")
    ts = datetime.now().isoformat()
    for auto in lista_auto:
        conn.execute("""
            INSERT INTO catalogo_concessionaria
                (tipo, marca, modello, anno, km, alimentazione, cambio, prezzo, url, aggiornato_il)
            VALUES
                (:tipo, :marca, :modello, :anno, :km, :alimentazione, :cambio, :prezzo, :url, :ts)
        """, {
            "tipo":         auto.get("tipo", "usata"),
            "marca":        auto.get("marca", ""),
            "modello":      auto.get("modello", ""),
            "anno":         auto.get("anno", ""),
            "km":           auto.get("km", 0),
            "alimentazione":auto.get("alimentazione", ""),
            "cambio":       auto.get("cambio", ""),
            "prezzo":       auto.get("prezzo", 0),
            "url":          auto.get("url", ""),
            "ts":           ts,
        })
    conn.commit()
    conn.close()
    print(f"[✓] Catalogo aggiornato: {len(lista_auto)} auto salvate")


def get_catalogo(budget_max=None, alimentazione=None, tipo=None):
    """
    Legge il catalogo con filtri opzionali.
    Usato dall'AI profiler per abbinare l'auto giusta al lead.
    """
    conn = get_connection()
    sql = "SELECT * FROM catalogo_concessionaria WHERE 1=1"
    params = []

    if budget_max:
        sql += " AND prezzo <= ?"
        params.append(budget_max)
    if alimentazione:
        sql += " AND alimentazione LIKE ?"
        params.append(f"%{alimentazione}%")
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)

    sql += " ORDER BY prezzo ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_catalogo_testo(budget_max=None, alimentazione=None) -> str:
    """
    Costruisce il blocco di testo del catalogo auto da iniettare nel prompt AI.
    Filtra per budget e alimentazione se forniti, mostra max 5 auto.
    Se il catalogo è vuoto restituisce stringa vuota.
    """
    auto = get_catalogo(budget_max=budget_max, alimentazione=alimentazione)
    if not auto:
        return ""

    # Mostra massimo 2 auto per tipo (usata/nuova/km0) per dare varietà all'AI
    per_tipo = {}
    for a in auto:
        t = a.get("tipo", "usata")
        if t not in per_tipo:
            per_tipo[t] = []
        if len(per_tipo[t]) < 2:
            per_tipo[t].append(a)

    selezione = [a for lista in per_tipo.values() for a in lista]

    righe = ["AUTO DISPONIBILI IN CONCESSIONARIA (autoghinzani.it):"]
    for a in selezione:
        riga = f"- {a['marca']} {a['modello']}"
        if a.get("anno"):
            riga += f" ({a['anno']})"
        if a.get("km"):
            riga += f", {a['km']:,} km"
        if a.get("prezzo"):
            riga += f", €{int(a['prezzo']):,}"
        if a.get("alimentazione"):
            riga += f", {a['alimentazione']}"
        if a.get("tipo"):
            riga += f" [{a['tipo']}]"
        if a.get("url"):
            riga += f" → {a['url']}"
        righe.append(riga)

    return "\n".join(righe)


if __name__ == "__main__":
    init_db()
    print_stats()
