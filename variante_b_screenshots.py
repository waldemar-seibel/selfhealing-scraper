"""
Variante B: Screenshots machen und von Claude lesen lassen.

    python variante_b_screenshots.py                  (Screenshots + Auswertung durch Claude)
    python variante_b_screenshots.py --nur-bilder     (nur Screenshots, keine KI, kostet nichts)

Ablauf:
  1. Chrome öffnet Seite 1 und macht einen Screenshot der GANZEN Seite (full_page=True)
  2. "Weiter" klicken, Pause, nächster Screenshot ... bis zur letzten Seite
  3. Jedes Bild geht an Claude mit der Bitte: "Gib mir alle Stellen als JSON"
  4. Ergebnis als ergebnis_b.csv, dazu Tokens und Kosten in messung_b.txt

Warum das interessant ist: Diese Variante braucht KEINE Selektoren. Ändert sich das Design,
liest Claude trotzdem, was ein Mensch sehen würde. Dafür ist sie langsamer, kostet Geld pro Bild
und kann sich verlesen. Genau das messen wir im Vergleich.

Fällt die API bei einem Bild aus (Netz, Überlastung), wird sie mehrfach wiederholt. Klappt es dann
immer noch, wird NUR diese Seite als "nicht gelesen" vermerkt, der Lauf geht weiter.

Braucht ANTHROPIC_API_KEY (Umgebungsvariable oder Datei .env in diesem Ordner:
    ANTHROPIC_API_KEY=sk-ant-...
"""
import argparse
import base64
import csv
import json
import random
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import llm
from llm import MODELL, PREIS_USD_PRO_MIO, USD_EUR, api_key  # noqa: F401  (von Variante C mitbenutzt)

HIER = Path(__file__).parent
BILDER = HIER / "bilder"
START_URL = "http://localhost:8000/seite-1.html"
PAUSE_SEKUNDEN = (1.0, 2.0)            # zufällige Pause zwischen Seiten

AUFTRAG = """Auf dem Bild ist eine Seite einer Jobbörse. Lies ALLE Stellenanzeigen ab.
Werbung/Anzeigen ("Gesponsert", "Anzeige") sind KEINE Stellen und werden weggelassen.
Gib für jede Stelle Firma, Titel, Ort und Datum genau so an, wie sie auf dem Bild stehen.
Fehlt der Ort, lass das Feld leer. Erfinde nichts.
Antworte NUR mit JSON in dieser Form:
[{"firma": "...", "titel": "...", "ort": "...", "datum": "..."}]"""


def screenshots_machen(url: str, unsichtbar: bool) -> list[Path]:
    BILDER.mkdir(exist_ok=True)
    pfade = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=unsichtbar)
        page = browser.new_page(viewport={"width": 1000, "height": 900})
        page.goto(url)
        for seite in range(1, 51):
            page.wait_for_load_state("networkidle")
            pfad = BILDER / f"seite-{seite}.png"
            page.screenshot(path=str(pfad), full_page=True)
            pfade.append(pfad)
            print(f"  Screenshot Seite {seite}: {pfad.name}")
            weiter = page.locator("text=Weiter")   # absichtlich nach sichtbarem Text, nicht nach Klasse
            if not weiter.count():
                break
            time.sleep(random.uniform(*PAUSE_SEKUNDEN))
            weiter.first.click()
        browser.close()
    return pfade


def bild_lesen(pfad: Path, key: str) -> tuple[list[dict], int, int]:
    """Liest ein Bild. Wirft llm.ApiFehler, wenn die API auch nach Wiederholungen nicht antwortet."""
    b64 = base64.b64encode(pfad.read_bytes()).decode()
    d = llm.api_post({"model": MODELL, "max_tokens": 4000,
                      "output_config": {"effort": "low"},
                      "messages": [{"role": "user", "content": [
                          {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                          {"type": "text", "text": AUFTRAG}]}]}, key)
    text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    u = d.get("usage", {})
    return antwort_parsen(text), u.get("input_tokens", 0), u.get("output_tokens", 0)


def antwort_parsen(text: str) -> list[dict]:
    """Holt die JSON-Liste aus Claudes Antwort (auch wenn sie in ```json ... ``` steht).
    Ungültiges JSON ergibt eine leere Liste statt eines Absturzes."""
    m = re.search(r"\[.*\]", text or "", re.S)
    try:
        stellen = json.loads(m.group(0)) if m else []
    except ValueError:
        print(f"    Antwort war kein gültiges JSON: {(text or '')[:120]!r}")
        return []
    return [s for s in stellen if isinstance(s, dict)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-bilder", action="store_true")
    ap.add_argument("--unsichtbar", action="store_true")
    ap.add_argument("--url", default=START_URL)
    args = ap.parse_args()

    start = time.time()
    pfade = screenshots_machen(args.url, args.unsichtbar)
    if args.nur_bilder:
        print(f"\n{len(pfade)} Screenshots in {BILDER}")
        return
    key = api_key()
    if not key:
        print("FEHLER: ANTHROPIC_API_KEY fehlt (Umgebungsvariable oder .env in diesem Ordner).")
        return

    alle, kosten, nicht_gelesen = [], llm.neue_kosten(), []
    for nr, pfad in enumerate(pfade, 1):
        try:
            stellen, i, o = bild_lesen(pfad, key)
        except llm.ApiFehler as e:
            print(f"  Seite {nr}: NICHT gelesen ({e})")
            nicht_gelesen.append(nr)
            continue
        llm.buche(kosten, i, o)
        for s in stellen:
            s["seite"] = nr
        alle += stellen
        print(f"  Claude liest Seite {nr}: {len(stellen)} Stellen ({i} Tokens rein, {o} raus)")

    with open(HIER / "ergebnis_b.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["seite", "firma", "titel", "ort", "datum"], delimiter=";",
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(alle)
    dauer = time.time() - start
    eur = llm.kosten_eur(kosten)
    (HIER / "messung_b.txt").write_text(
        f"dauer_sekunden={dauer:.1f}\nkosten_eur={eur:.4f}\ntokens_ein={kosten['ein']}\n"
        f"tokens_aus={kosten['aus']}\nseiten_nicht_gelesen={len(nicht_gelesen)}\n", encoding="utf-8")
    print(f"\n{len(alle)} Stellen in {dauer:.1f} s, Kosten ca. {eur:.3f} €: {HIER / 'ergebnis_b.csv'}")
    if nicht_gelesen:
        print(f"ACHTUNG: Seiten nicht gelesen: {nicht_gelesen}")


if __name__ == "__main__":
    main()
