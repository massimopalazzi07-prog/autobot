"""
Dashboard Web — Visualizzazione lead in tempo reale
Avvia con: python dashboard.py
Poi apri:  http://localhost:5000
"""

import os
import sys
import csv
import io
import sqlite3
import subprocess
from flask import Flask, jsonify, request, render_template, Response
from datetime import datetime

# Importa le funzioni helper del database per la gestione
# del profilo concessionaria e delle offerte
import database as db
import config as cfg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")
_run_process = None


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── ROUTES ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    conn = get_connection()
    stats = {
        "totale":       conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        "nuovi":        conn.execute("SELECT COUNT(*) FROM leads WHERE stato='nuovo'").fetchone()[0],
        "contattati":   conn.execute("SELECT COUNT(*) FROM leads WHERE stato='contattato'").fetchone()[0],
        "risposti":     conn.execute("SELECT COUNT(*) FROM leads WHERE stato='risposto'").fetchone()[0],
        "appuntamenti": conn.execute("SELECT COUNT(*) FROM leads WHERE stato='appuntamento'").fetchone()[0],
        "venduti":      conn.execute("SELECT COUNT(*) FROM leads WHERE stato='venduto'").fetchone()[0],
        "score_medio":  conn.execute(
            "SELECT ROUND(AVG(ai_score),1) FROM leads WHERE ai_score > 0"
        ).fetchone()[0] or 0,
    }
    rows = conn.execute("SELECT DISTINCT fonte FROM leads WHERE fonte != '' ORDER BY fonte").fetchall()
    stats["fonti"] = [r["fonte"] for r in rows]
    rows = conn.execute("SELECT DISTINCT brand FROM leads WHERE brand != '' ORDER BY brand").fetchall()
    stats["brands"] = [r["brand"] for r in rows]
    conn.close()
    return jsonify(stats)


@app.route("/api/leads")
def api_leads():
    stato     = request.args.get("stato", "")
    fonte     = request.args.get("fonte", "")
    brand     = request.args.get("brand", "")
    min_score = int(request.args.get("min_score", 0))
    q         = request.args.get("q", "").strip()

    query  = "SELECT * FROM leads WHERE ai_score >= ?"
    params = [min_score]

    if stato: query += " AND stato = ?";  params.append(stato)
    if fonte: query += " AND fonte = ?";  params.append(fonte)
    if brand: query += " AND brand = ?";  params.append(brand)
    if q:
        query += " AND (title LIKE ? OR description LIKE ? OR location LIKE ? OR brand LIKE ? OR ai_profilo LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like, like])

    query += " ORDER BY ai_score DESC, created_at DESC LIMIT 200"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/export")
def api_export():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM leads ORDER BY ai_score DESC, created_at DESC").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    if rows:
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow(list(row))

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=leads_bergamo.csv"},
    )


@app.route("/api/lead/<int:lead_id>/stato", methods=["POST"])
def update_stato(lead_id):
    data = request.get_json(force=True)
    nuovo_stato = data.get("stato", "")
    valid = {"nuovo", "contattato", "risposto", "appuntamento", "venduto", "non_interessato"}
    if nuovo_stato not in valid:
        return jsonify({"error": "stato non valido"}), 400

    ts     = datetime.now().isoformat()
    conn   = get_connection()
    sql    = "UPDATE leads SET stato = ?"
    params = [nuovo_stato]

    if nuovo_stato == "contattato":
        sql += ", contattato_at = ?"; params.append(ts)
    elif nuovo_stato == "risposto":
        sql += ", risposto_at = ?";   params.append(ts)

    sql += " WHERE id = ?"; params.append(lead_id)
    conn.execute(sql, params)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/lead/<int:lead_id>/note", methods=["POST"])
def update_note(lead_id):
    data = request.get_json(force=True)
    note = data.get("note", "")
    conn = get_connection()
    conn.execute("UPDATE leads SET note = ? WHERE id = ?", (note, lead_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/run", methods=["POST"])
def run_pipeline():
    global _run_process
    if _run_process and _run_process.poll() is None:
        return jsonify({"running": True, "message": "Scraping già in corso"})
    script = os.path.join(os.path.dirname(__file__), "main.py")
    _run_process = subprocess.Popen(
        ["python", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return jsonify({"started": True})


@app.route("/api/run/status")
def run_status():
    global _run_process
    if _run_process is None:
        return jsonify({"running": False})
    if _run_process.poll() is None:
        return jsonify({"running": True})
    _run_process = None
    return jsonify({"running": False, "just_finished": True})


# ── API CONCESSIONARIA ────────────────────────────────────────────────────────
#
# Questi endpoint espongono il profilo della concessionaria e il catalogo
# delle offerte. Sono usati sia dalla dashboard (impostazioni) che
# dall'AI profiler (ai_profiler.py) per costruire prompt personalizzati.
#
# Endpoint disponibili:
#   GET  /api/concessionaria            → legge il profilo
#   POST /api/concessionaria            → crea/aggiorna il profilo
#   GET  /api/concessionaria/offerte    → lista offerte (solo attive di default)
#   POST /api/concessionaria/offerte    → crea una nuova offerta
#   DELETE /api/concessionaria/offerte/<id> → elimina un'offerta


@app.route("/api/concessionaria", methods=["GET"])
def get_concessionaria():
    """
    GET /api/concessionaria
    Restituisce il profilo della concessionaria salvato nel DB.
    Se non è ancora stato configurato, restituisce un oggetto vuoto {}.
    """
    return jsonify(db.get_concessionaria())


@app.route("/api/concessionaria", methods=["POST"])
def update_concessionaria():
    """
    POST /api/concessionaria
    Body JSON: { nome, indirizzo, telefono, email, note }
    Crea o sovrascrive il profilo della concessionaria (singleton, id=1).
    Tutti i campi sono opzionali tranne 'nome'.
    """
    data = request.get_json(force=True)

    # Validazione minima: il nome è obbligatorio
    if not data.get("nome", "").strip():
        return jsonify({"error": "Il campo 'nome' è obbligatorio"}), 400

    db.upsert_concessionaria(data)
    return jsonify({"ok": True, "updated": db.get_concessionaria()})


@app.route("/api/concessionaria/offerte", methods=["GET"])
def get_offerte():
    """
    GET /api/concessionaria/offerte
    Restituisce la lista delle offerte.
    Query param: ?tutte=1 → include anche le offerte disattivate (attiva=0).
    Default: solo offerte attive.
    """
    solo_attive = request.args.get("tutte", "0") != "1"
    offerte = db.get_offerte(solo_attive=solo_attive)
    return jsonify(offerte)


@app.route("/api/concessionaria/offerte", methods=["POST"])
def create_offerta():
    """
    POST /api/concessionaria/offerte
    Body JSON: { titolo, descrizione, prezzo, tipo, attiva }
    Crea una nuova offerta nel catalogo.
    - titolo: obbligatorio (es. "Citroën C3 2026")
    - prezzo: stringa libera (es. "da €14.990")
    - tipo: 'nuovo' | 'usato' | 'servizio'  (default: 'nuovo')
    - attiva: true/false  (default: true)
    Restituisce l'id della riga creata.
    """
    data = request.get_json(force=True)

    # Validazione: titolo obbligatorio
    if not data.get("titolo", "").strip():
        return jsonify({"error": "Il campo 'titolo' è obbligatorio"}), 400

    # Tipo valido
    tipo = data.get("tipo", "nuovo")
    if tipo not in {"nuovo", "usato", "servizio"}:
        return jsonify({"error": "tipo deve essere 'nuovo', 'usato' o 'servizio'"}), 400

    offerta_id = db.create_offerta(data)
    return jsonify({"ok": True, "id": offerta_id}), 201


@app.route("/api/concessionaria/offerte/<int:offerta_id>", methods=["DELETE"])
def delete_offerta(offerta_id):
    """
    DELETE /api/concessionaria/offerte/<id>
    Elimina definitivamente un'offerta per id.
    Restituisce 404 se l'id non esiste.
    """
    deleted = db.delete_offerta(offerta_id)
    if not deleted:
        return jsonify({"error": f"Offerta {offerta_id} non trovata"}), 404
    return jsonify({"ok": True, "deleted_id": offerta_id})


# ── API IMPOSTAZIONI ──────────────────────────────────────────────────────────

@app.route("/api/config", methods=["GET"])
def get_config():
    data = cfg.load()
    # Maschera parzialmente la API key per sicurezza
    key = data.get("groq_api_key", "")
    if key:
        data["groq_api_key_preview"] = key[:8] + "..." + key[-4:]
    return jsonify(data)


@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.get_json(force=True)
    # Accetta solo i campi validi
    allowed = {"groq_api_key", "cap_ricerca", "raggio_km", "max_lead_profilare", "max_pagine_subito", "max_items_autoscout"}
    filtered = {k: v for k, v in data.items() if k in allowed}
    if not filtered:
        return jsonify({"error": "Nessun campo valido"}), 400
    cfg.save(filtered)
    return jsonify({"ok": True})


# ── API CATALOGO CONCESSIONARIA ───────────────────────────────────────────────
#
# Endpoint disponibili:
#   GET  /api/catalogo                   → lista auto (filtri opzionali)
#   POST /api/catalogo/aggiorna          → rilancia lo scraper e aggiorna il DB


@app.route("/api/catalogo", methods=["GET"])
def get_catalogo():
    """
    GET /api/catalogo
    Restituisce le auto disponibili in concessionaria.
    Query params opzionali:
      ?budget_max=20000
      ?alimentazione=Ibrida
      ?tipo=usata  (usata | nuova | km0)
    """
    budget_max    = request.args.get("budget_max", type=float)
    alimentazione = request.args.get("alimentazione")
    tipo          = request.args.get("tipo")
    auto = db.get_catalogo(budget_max=budget_max, alimentazione=alimentazione, tipo=tipo)
    return jsonify({"totale": len(auto), "auto": auto})


@app.route("/api/catalogo/aggiorna", methods=["POST"])
def aggiorna_catalogo():
    """
    POST /api/catalogo/aggiorna
    Rilancia lo scraper di autoghinzani.it e aggiorna il DB.
    """
    try:
        from scrapers.ghinzani_scraper import scrapa_catalogo
        auto = scrapa_catalogo()
        db.salva_catalogo(auto)
        return jsonify({"ok": True, "auto_salvate": len(auto)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── MAIN ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("[!] Database non trovato. Esegui prima: python main.py")
        sys.exit(1)

    print("\n╔═══════════════════════════════════════╗")
    print("║  🚗  AUTO LEAD — Dashboard Web         ║")
    print("╠═══════════════════════════════════════╣")
    print("║  → http://localhost:5000               ║")
    print("╚═══════════════════════════════════════╝\n")
    app.run(debug=False, port=5000)
