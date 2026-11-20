"""
Variante A: Daten direkt aus der Seite lesen (Playwright).

    python variante_a_daten.py                 (Browser sichtbar, du kannst zuschauen)
    python variante_a_daten.py --unsichtbar    (Browser im Hintergrund, "headless")
    python variante_a_daten.py --zuschauen     (langsam: scrollt zu jeder Karte und rahmt sie ein)

Warum sieht man ohne --zuschauen kein Scrollen? Variante A liest nicht den Bildschirm, sondern
den Aufbau der Seite (HTML). Darin stehen alle Stellen auf einmal, auch die unten noch nicht
sichtbaren. Scrollen ist dafür nicht nötig. --zuschauen macht es nur sichtbar, zum Verstehen.

Ablauf:
  1. Chrome öffnen und Seite 1 laden
  2. Warten, bis die Stellen da sind
  3. Jede Stellen-Karte lesen: Firma, Titel, Ort, Datum (Werbung überspringen)
  4. "Weiter" klicken, kurze Pause, wiederholen bis es kein "Weiter" mehr gibt
  5. Alles als ergebnis_a.csv speichern

Wichtige Begriffe:
  * Selektor: eine Adresse für ein Element auf der Seite, z. B. "article.stelle" = alle <article>
    mit der Klasse "stelle". Mit F12 im Browser (Element untersuchen) findest du sie selbst.
  * Warten: Seiten laden nicht sofort. Playwright wartet automatisch, bis ein Element da ist.
  * Pause: Zwischen zwei Seiten bewusst warten. Bei echten Seiten ist das Höflichkeit gegenüber
    dem Server; hier üben wir es nur.
"""
import argparse
import csv
import random
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

HIER = Path(__file__).parent
START_URL = "http://localhost:8000/seite-1.html"

# Alle Selektoren an einer Stelle. Ändert sich das Design der Seite, muss man nur hier ran.
SELEKTOREN = {
    "stelle": "article.stelle",        # eine Stellen-Karte (Werbung hat die Klasse "werbung", nicht "stelle")
    "firma": ".firma",
    "titel": ".titel",
    "ort": ".ort",
    "datum": ".datum",
    "weiter": "a.weiter",
}
PAUSE_SEKUNDEN = (1.0, 2.0)            # zufällige Pause zwischen Seiten
MAX_SEITEN = 50                        # Notbremse, falls "Weiter" nie verschwindet


def text_oder_leer(karte, selektor: str) -> str:
    """Liest den Text eines Unterelements. Fehlt es (z. B. kein Ort), kommt "" zurück statt eines Fehlers."""
    el = karte.locator(selektor)
    return el.first.inner_text().strip() if el.count() else ""


def seite_lesen(page, zuschauen: bool = False) -> list[dict]:
    page.wait_for_selector(SELEKTOREN["stelle"], timeout=10_000)
    if zuschauen:
        # Werbung sichtbar als "übersprungen" markieren
        for w in page.locator("article.werbung").all():
            w.evaluate("el => { el.style.opacity = '0.4'; el.style.textDecoration = 'line-through'; }")
    zeilen = []
    for karte in page.locator(SELEKTOREN["stelle"]).all():
        if zuschauen:
            karte.scroll_into_view_if_needed()
            karte.evaluate("el => { el.scrollIntoView({behavior: 'smooth', block: 'center'});"
                           " el.style.outline = '3px solid #e01b24'; }")
            time.sleep(0.5)
        zeilen.append({
            "id": karte.get_attribute("data-id") or "",
            "firma": text_oder_leer(karte, SELEKTOREN["firma"]),
            "titel": text_oder_leer(karte, SELEKTOREN["titel"]),
            "ort": text_oder_leer(karte, SELEKTOREN["ort"]),
            "datum": text_oder_leer(karte, SELEKTOREN["datum"]),
        })
    return zeilen


def mit_wiederholung(funktion, versuche: int = 3):
    """Führt eine Funktion aus und versucht es bei einem Timeout bis zu 3-mal (Netz wackelt mal)."""
    for nr in range(1, versuche + 1):
        try:
            return funktion()
        except PlaywrightTimeout:
            print(f"    Zeitüberschreitung, Versuch {nr}/{versuche}")
            if nr == versuche:
                raise
            time.sleep(2 * nr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unsichtbar", action="store_true", help="Browser im Hintergrund laufen lassen")
    ap.add_argument("--url", default=START_URL)
    ap.add_argument("--zuschauen", action="store_true", help="langsam scrollen und gelesene Karten einrahmen")
    args = ap.parse_args()

    start = time.time()
    alle = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.unsichtbar, slow_mo=0 if args.unsichtbar else 150)
        page = browser.new_page()
        mit_wiederholung(lambda: page.goto(args.url))
        for seite in range(1, MAX_SEITEN + 1):
            zeilen = mit_wiederholung(lambda: seite_lesen(page, args.zuschauen))
            for z in zeilen:
                z["seite"] = seite
            alle += zeilen
            print(f"  Seite {seite}: {len(zeilen)} Stellen gelesen")
            weiter = page.locator(SELEKTOREN["weiter"])
            if not weiter.count():
                print("  Kein 'Weiter' mehr, fertig.")
                break
            if args.zuschauen:
                weiter.first.scroll_into_view_if_needed()
                weiter.first.evaluate("el => el.style.outline = '4px solid #26a269'")
                time.sleep(1.5)
            time.sleep(random.uniform(*PAUSE_SEKUNDEN))
            mit_wiederholung(lambda: weiter.first.click())
            page.wait_for_load_state("domcontentloaded")
        browser.close()

    ziel = HIER / "ergebnis_a.csv"
    with open(ziel, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "seite", "firma", "titel", "ort", "datum"], delimiter=";")
        w.writeheader()
        w.writerows(alle)
    dauer = time.time() - start
    (HIER / "messung_a.txt").write_text(f"dauer_sekunden={dauer:.1f}\nkosten_eur=0\n", encoding="utf-8")
    print(f"\n{len(alle)} Stellen in {dauer:.1f} s gespeichert: {ziel}")


if __name__ == "__main__":
    main()
