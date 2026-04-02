import requests
import json
from bs4 import BeautifulSoup

PAGINE = [
    ("https://autoghinzani.it/auto/usate/", "usata"),
    ("https://autoghinzani.it/auto/nuove-pronta-consegna/", "nuova"),
    ("https://autoghinzani.it/auto/km0/", "km0"),
]

def scrapa_catalogo():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    auto_list = []

    for url, tipo in PAGINE:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            try:
                data = json.loads(script.string)
            except:
                continue

            # I dati sono dentro un array @graph
            graph = data.get("@graph", [])
            if not graph:
                graph = [data]

            for node in graph:
                if node.get("@type") != "ItemList":
                    continue
                for item in node.get("itemListElement", []):
                    veicolo = item.get("item", item)
                    auto = {
                        "tipo": tipo,
                        "marca": veicolo.get("brand", {}).get("name", ""),
                        "modello": veicolo.get("name", ""),
                        "anno": veicolo.get("vehicleModelDate", ""),
                        "km": veicolo.get("mileageFromOdometer", {}).get("value", 0),
                        "alimentazione": veicolo.get("fuelType", ""),
                        "cambio": veicolo.get("vehicleTransmission", ""),
                        "prezzo": veicolo.get("offers", {}).get("price", 0),
                        "url": veicolo.get("url", ""),
                    }
                    auto_list.append(auto)

    return auto_list


# TEST — eseguilo direttamente per vedere se funziona
if __name__ == "__main__":
    auto = scrapa_catalogo()
    print(f"Auto trovate: {len(auto)}")
    for a in auto[:3]:
        print(a)
