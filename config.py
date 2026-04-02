"""
Gestione configurazione centralizzata.
Le impostazioni vengono lette/scritte da config.json nella stessa cartella.
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
    "groq_api_key": "",
    "cap_ricerca": "24100",
    "raggio_km": 30,
    "max_lead_profilare": 15,
    "max_pagine_subito": 6,
    "max_items_autoscout": 30,
}


def load() -> dict:
    """Legge config.json e lo unisce ai default (i default coprono chiavi mancanti)."""
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return {**DEFAULTS, **saved}
    except Exception:
        return dict(DEFAULTS)


def save(data: dict):
    """Salva il dizionario in config.json."""
    current = load()
    current.update(data)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)


def get(key: str, fallback=None):
    """Legge un singolo valore dalla config."""
    return load().get(key, fallback if fallback is not None else DEFAULTS.get(key))
