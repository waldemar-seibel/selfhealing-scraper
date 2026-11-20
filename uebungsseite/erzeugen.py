"""
Schritt 1: Erzeugt eine kleine, erfundene Jobbörse zum Üben.

    python uebungsseite/erzeugen.py                 (ursprüngliches Design)
    python uebungsseite/erzeugen.py --design neu    (geändertes Design: Karten heißen "job" statt "stelle")

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
from pathlib import Path

HIER = Path(__file__).parent
SITE = HIER / "site"
SEITEN = 10
PRO_SEITE = 12

random.seed(42)  # immer dieselbe Seite, damit Ergebnisse vergleichbar bleiben

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


def main(design: str = "alt"):
    klasse = "stelle" if design == "alt" else "job"   # simuliert einen Relaunch der Website
    random.seed(42)
    SITE.mkdir(parents=True, exist_ok=True)
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
            ort_html = f'<span class="ort">{html.escape(ort)}</span> · ' if ort else ""
            karten.append(f"""
  <article class="karte {klasse}" data-id="J{nr:04d}">
    <div class="firma">{html.escape(firma)}</div>
    <div class="titel">{html.escape(titel)}</div>
    <div class="meta">{ort_html}<span class="datum">{datum}</span></div>
  </article>""")
            if i == 4:  # Werbung mittendrin, sieht ähnlich aus, ist aber keine Stelle
                karten.append("""
  <article class="karte werbung">
    <div class="firma">Anzeige</div>
    <div class="titel">Jetzt Lebenslauf-Check gratis!</div>
    <div class="meta">Gesponsert</div>
  </article>""")
        nav = []
        if s > 1:
            nav.append(f'<a href="seite-{s-1}.html" class="zurueck">« Zurück</a>')
        if s < SEITEN:
            nav.append(f'<a href="seite-{s+1}.html" class="weiter" aria-label="Weiter">Weiter »</a>')
        (SITE / f"seite-{s}.html").write_text(f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Übungs-Jobbörse – Seite {s}</title>
<style>{CSS}</style></head>
<body>
<h1>Übungs-Jobbörse: Zerspanung im Raum OWL <small>(Seite {s} von {SEITEN}, alle Firmen erfunden)</small></h1>
<main id="ergebnisse">{''.join(karten)}
</main>
<nav class="nav">{' '.join(nav)}</nav>
</body></html>""", encoding="utf-8")

    with open(HIER / "wahrheit.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "seite", "firma", "titel", "ort", "datum"], delimiter=";")
        w.writeheader()
        w.writerows(zeilen)
    print(f"{SEITEN} Seiten mit {len(zeilen)} Stellen erzeugt in {SITE} (Design: {design}, Klasse '{klasse}')")
    print(f"Wahrheit (zum Vergleich): {HIER / 'wahrheit.csv'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", choices=["alt", "neu"], default="alt")
    main(ap.parse_args().design)
