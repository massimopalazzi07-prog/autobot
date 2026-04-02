"""
AVVIA — Punto di ingresso unico per AutoLead Bergamo
Esegui con: python avvia.py
"""

import os
import sys
import subprocess
import threading
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))

BANNER = """
╔══════════════════════════════════════════╗
║   🚗  AUTO LEAD BERGAMO — Avvio rapido   ║
╚══════════════════════════════════════════╝
"""

MENU = """
Cosa vuoi fare?

  [1] Avvio completo  — scraping reale + AI + dashboard
  [2] Demo            — test con dati finti + dashboard
  [3] Solo dashboard  — apri la dashboard senza scraping
  [4] Solo scraping   — esegui il bot senza aprire la dashboard
  [5] Statistiche     — mostra i dati nel database
  [0] Esci

Scelta: """


def run_in_thread(cmd, cwd=BASE):
    """Lancia un comando in un thread separato (non bloccante)."""
    def _run():
        subprocess.run(cmd, cwd=cwd)
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def apri_browser():
    """Aspetta 2 secondi e apre il browser sulla dashboard."""
    time.sleep(2)
    import webbrowser
    webbrowser.open("http://localhost:5000")


def avvia_dashboard():
    print("\n[→] Avvio dashboard su http://localhost:5000 ...")
    threading.Thread(target=apri_browser, daemon=True).start()
    subprocess.run([sys.executable, os.path.join(BASE, "dashboard.py")], cwd=BASE)


def avvia_scraping(demo=False):
    args = [sys.executable, os.path.join(BASE, "main.py")]
    if demo:
        args.append("--demo")
    subprocess.run(args, cwd=BASE)


def avvia_completo(demo=False):
    """Esegue scraping e poi avvia la dashboard."""
    print("\n[→] Avvio scraping...")
    avvia_scraping(demo=demo)
    print("\n[→] Scraping completato. Avvio dashboard...")
    avvia_dashboard()


def main():
    print(BANNER)

    while True:
        try:
            scelta = input(MENU).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nArrivederci!")
            break

        if scelta == "1":
            print("\n[!] Avvio completo — scraping reale. Ci vorrà qualche minuto.")
            avvia_completo(demo=False)

        elif scelta == "2":
            print("\n[!] Modalità demo — dati di esempio, nessuna connessione necessaria.")
            avvia_completo(demo=True)

        elif scelta == "3":
            avvia_dashboard()

        elif scelta == "4":
            print("\nModalità:")
            print("  [r] Reale")
            print("  [d] Demo")
            m = input("Scelta: ").strip().lower()
            avvia_scraping(demo=(m == "d"))

        elif scelta == "5":
            subprocess.run([sys.executable, os.path.join(BASE, "main.py"), "--stats"], cwd=BASE)

        elif scelta == "0":
            print("\nArrivederci!")
            break

        else:
            print("\n[!] Scelta non valida, riprova.")


HELP = """
USO: python avvia.py [opzione]

Senza argomenti apre il menu interattivo.

OPZIONI:
  --completo    Scraping reale da internet + profilazione AI + dashboard
  --demo        Test con 5 lead di esempio (no internet) + dashboard
  --dashboard   Apre solo la dashboard web (http://localhost:5000)
  --scraping    Esegue solo lo scraping reale senza aprire la dashboard
  --stats       Mostra le statistiche del database (totale lead, score, ecc.)
  --help        Mostra questo messaggio

ESEMPI:
  python avvia.py               → menu interattivo
  python avvia.py --completo    → ciclo completo automatico
  python avvia.py --demo        → test rapido senza internet
  python avvia.py --dashboard   → solo dashboard (se hai già i lead)
"""

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(HELP)
    elif "--completo" in args:
        avvia_completo(demo=False)
    elif "--demo" in args:
        avvia_completo(demo=True)
    elif "--dashboard" in args:
        avvia_dashboard()
    elif "--scraping" in args:
        avvia_scraping(demo=False)
    elif "--stats" in args:
        subprocess.run([sys.executable, os.path.join(BASE, "main.py"), "--stats"], cwd=BASE)
    else:
        main()
