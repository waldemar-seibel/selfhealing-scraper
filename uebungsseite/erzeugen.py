"""
Schritt 1: Erzeugt eine kleine, erfundene Jobbörse zum Üben.

    python uebungsseite/erzeugen.py                  (ursprüngliches Design)
    python uebungsseite/erzeugen.py --design neu     (Relaunch: Karten heißen "job" statt "stelle")

Weitere Designs zum Testen der Selbstheilung (die Daten bleiben bei allen gleich):
    --design teil      Teilbruch: NUR der Ort heißt jetzt "location"; Karten, Firma, Titel bleiben.
                       Ein Scraper, der nur "findet er Karten?" prüft, merkt nichts.
    --design felder    Alles umbenannt: job / company / position / location / date
    --design tausch    Firma und Titel haben die Klassen getauscht (.firma enthält jetzt den Jobtitel)
    --design leer      Gültige Seite ohne Treffer ("Keine Treffer"), kein Redesign, nichts zu reparieren

Ergebnis:
  uebungsseite/site/seite-1.html ... seite-10.html   die Übungs-Website
  uebungsseite/wahrheit.csv                         die "echten" Daten (zum späteren Vergleich)

Damit es realistisch ist, hat die Seite ein paar Stolperfallen, wie echte Jobportale auch:
  * Werbe-Kacheln zwischen den Stellen (dürfen nicht als Stelle gezählt werden)
  * manchmal fehlt der Ort
  * Firmennamen mit Sonderzeichen (&, Umlaute, "GmbH & Co. KG")
  * Zeitarbeitsfirmen mittendrin
  * "Weiter"-Knopf zum Blättern, auf der letzten Seite fehlt er
Alle Firmen sind ERFUNDEN.
"""
import argparse
import csv
import html
import random
import re
from pathlib import Path

HIER = Path(__file__).parent
SITE = HIER / "site"
SEITEN = 10
PRO_SEITE = 12

random.seed(42)  # immer dieselbe Seite, damit Ergebnisse vergleichbar bleiben

# Klassennamen je Design. Was fehlt, bleibt wie im ursprünglichen Design.
KLASSEN = {"stelle": "stelle", "firma": "firma", "titel": "titel", "ort": "ort", "datum": "datum"}
DESIGNS = {
    "alt": {},
    "neu": {"stelle": "job"},
    "teil": {"ort": "location"},
    "felder": {"stelle": "job", "firma": "company", "titel": "position", "ort": "location", "datum": "date"},
    "tausch": {"firma": "titel", "titel": "firma"},
    "leer": {},
}

TEIL1 = ["Brinkmann", "Hölscher", "Kemper", "Overbeck", "Schäfer", "Tiemann", "Wöstmann", "Lückemeyer",
         "Strothmann", "Düfelmeyer", "Kröger", "Nagel", "Pöppelmann", "Rehage", "Sundermann", "Vahle"]
TEIL2 = ["CNC-Technik", "Zerspanungstechnik", "Präzisionsteile", "Dreh- & Frästechnik", "Maschinenbau",
         "Feinmechanik", "Metallbearbeitung", "Werkzeugbau"]
FORM = ["GmbH", "GmbH & Co. KG", "KG", "e.K.", "AG"]
ZEITARBEIT = ["FlexPersonal Service GmbH", "JobWerk Personaldienste GmbH", "ProStaff Zeitarbeit GmbH"]
ORTE = ["Bielefeld", "Gütersloh", "Lemgo", "Detmold", "Herford", "Bad Salzuflen", "Paderborn", "Oerlinghausen",
        "Lage", "Verl", "Rheda-Wiedenbrück", "Bünde"]
TITEL = ["Zerspanungsmechaniker (m/w/d)", "CNC-Fräser (m/w/d)", "CNC-Dreher (m/w/d) Frühschicht",
         "Zerspanungsmechaniker Drehtechnik (m/w/d)", "Maschinenbediener CNC (m/w/d)",
         "Mitarbeiter Arbeitsvorbereitung (m/w/d)", "Kalkulator (m/w/d) Zerspanung", "CNC-Fachkraft (m/w/d)"]

CSS = """
body{font-family:Arial,sans-serif;max-width:900px;margin:20px auto;background:#f4f4f6;color:#222}
h1{font-size:22px}.karte{background:#fff;border-radius:8px;padding:14px 16px;margin:10px 0;
box-shadow:0 1px 3px rgba(0,0,0,.12)}.firma{color:#555;font-size:14px}.titel{font-size:17px;font-weight:bold;
margin:4px 0}.meta{font-size:13px;color:#777}.werbung{background:#fff6d6;border:1px dashed #d9b84a}
.nav{margin:20px 0;display:flex;gap:12px}.nav a{background:#1a5fb4;color:#fff;padding:8px 14px;
border-radius:6px;text-decoration:none}
"""


def firma_erfinden():
    if random.random() < 0.12:
        return random.choice(ZEITARBEIT)
    return f"{random.choice(TEIL1)} {random.choice(TEIL2)} {random.choice(FORM)}"


def css_fuer(k: dict) -> str:
    """Setzt die Klassennamen des Designs in das Stylesheet ein (in einem Durchgang, damit getauschte
    Namen nicht doppelt ersetzt werden). So sieht die Seite in jedem Design gleich aus."""
    return re.sub(r"\.(firma|titel)\b", lambda m: "." + k[m.group(1)], CSS)


def seite_schreiben(s: int, anzahl: int, inhalt: str, nav: str, k: dict):
    (SITE / f"seite-{s}.html").write_text(f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Übungs-Jobbörse – Seite {s}</title>
<style>{css_fuer(k)}</style></head>
<body>
<h1>Übungs-Jobbörse: Zerspanung im Raum OWL <small>(Seite {s} von {anzahl}, alle Firmen erfunden)</small></h1>
<main id="ergebnisse">{inhalt}
</main>
<nav class="nav">{nav}</nav>
</body></html>""", encoding="utf-8")


def main(design: str = "alt"):
    k = {**KLASSEN, **DESIGNS[design]}   # simuliert einen Relaunch der Website
    random.seed(42)
    SITE.mkdir(parents=True, exist_ok=True)
    for alt in SITE.glob("seite-*.html"):   # keine Reste eines früheren Designs stehen lassen
        alt.unlink()
    felder = ["id", "seite", "firma", "titel", "ort", "datum"]

    if design == "leer":
        seite_schreiben(1, 1, '\n  <p class="leer">Keine Treffer für deine Suche.</p>', "", k)
        with open(HIER / "wahrheit.csv", "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=felder, delimiter=";").writeheader()
        print(f"1 Seite ohne Treffer erzeugt in {SITE} (Design: leer)")
        return

    zeilen = []
    nr = 0
    for s in range(1, SEITEN + 1):
        karten = []
        for i in range(PRO_SEITE):
            nr += 1
            firma = firma_erfinden()
            titel = random.choice(TITEL)
            ort = random.choice(ORTE) if random.random() > 0.08 else ""   # manchmal fehlt der Ort
            tage = random.randint(0, 29)
            datum = "heute" if tage == 0 else f"vor {tage} Tagen"
            zeilen.append({"id": f"J{nr:04d}", "seite": s, "firma": firma, "titel": titel, "ort": ort, "datum": datum})
            ort_html = f'<span class="{k["ort"]}">{html.escape(ort)}</span> · ' if ort else ""
            # Bei "tausch" tragen die Elemente die jeweils andere Klasse (k["firma"] ist dann "titel").
            karten.append(f"""
  <article class="karte {k['stelle']}" data-id="J{nr:04d}">
    <div class="{k['firma']}">{html.escape(firma)}</div>
    <div class="{k['titel']}">{html.escape(titel)}</div>
    <div class="meta">{ort_html}<span class="{k['datum']}">{datum}</span></div>
  </article>""")
            if i == 4:  # Werbung mittendrin, sieht ähnlich aus, ist aber keine Stelle
                karten.append(f"""
  <article class="karte werbung">
    <div class="{k['firma']}">Anzeige</div>
    <div class="{k['titel']}">Jetzt Lebenslauf-Check gratis!</div>
    <div class="meta">Gesponsert</div>
  </article>""")
        nav = []
        if s > 1:
            nav.append(f'<a href="seite-{s-1}.html" class="zurueck">« Zurück</a>')
        if s < SEITEN:
            nav.append(f'<a href="seite-{s+1}.html" class="weiter" aria-label="Weiter">Weiter »</a>')
        seite_schreiben(s, SEITEN, "".join(karten), " ".join(nav), k)

    with open(HIER / "wahrheit.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=felder, delimiter=";")
        w.writeheader()
        w.writerows(zeilen)
    print(f"{SEITEN} Seiten mit {len(zeilen)} Stellen erzeugt in {SITE} (Design: {design}, Klasse '{k['stelle']}')")
    print(f"Wahrheit (zum Vergleich): {HIER / 'wahrheit.csv'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", choices=list(DESIGNS), default="alt")
    main(ap.parse_args().design)
