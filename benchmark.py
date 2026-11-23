"""
Benchmark: Wie gut heilt sich Variante C bei verschiedenen Fehlerbildern, und richtet sie dabei Schaden an?

    python benchmark.py                      simuliertes Claude: kostenlos, ohne API-Schlüssel, wiederholbar
    python benchmark.py --lesefehler         dasselbe, aber der "Screenshot" enthält Lesefehler (Tippfehler im Ort)
    python benchmark.py --echt               ECHTES Claude (braucht ANTHROPIC_API_KEY, kostet ca. 1 ct pro Durchgang)
    python benchmark.py --echt --wiederholungen 3    Claude ist nicht deterministisch: mehrmals messen
    python benchmark.py --nur teil           nur Szenarien, deren Name "teil" enthält

Jedes Szenario baut die Übungsseite in einem Temp-Ordner (Design aus uebungsseite/erzeugen.py),
lässt Variante C darauf laufen und vergleicht mit den echten Daten (wahrheit.csv). Gemessen wird:

  * Entscheidung: Hat C getan, was richtig ist? (reparieren / nichts tun / einen schlechten Vorschlag ablehnen)
  * Schaden:      Wurde ein falscher oder unnötiger Vorschlag dauerhaft übernommen? (sollte immer 0 sein)
  * Daten:        Wie viele Felder (Firma, Titel, Ort, Datum) stimmen am Ende mit der Wahrheit überein?
  * Aufwand:      Bild-Lesungen, Textanfragen, Kosten, Zeit

Die Tabelle landet auch in benchmark_ergebnis.md (nicht im Git).

Aussagekraft: Im simulierten Modus liest der "Screenshot" immer perfekt und die Vorschläge sind fest
vorgegeben. Das misst die PRÜFLOGIK von C, nicht die Qualität von Claude. Die Qualität misst nur --echt,
dort schwankt das Ergebnis von Lauf zu Lauf. Die Szenarien mit absichtlich schlechten Vorschlägen gibt es
nur im simulierten Modus.
"""
import argparse
import contextlib
import csv
import functools
import http.server
import io
import json
import re
import socketserver
import sys
import tempfile
import threading
import time
from pathlib import Path

HIER = Path(__file__).parent
sys.path.insert(0, str(HIER / "uebungsseite"))

import erzeugen  # noqa: E402
import llm  # noqa: E402
import qualitaet  # noqa: E402
import variante_b_screenshots as vb  # noqa: E402
import variante_c_kombi as vc  # noqa: E402

ALT = {"stelle": "article.stelle", "firma": ".firma", "titel": ".titel", "ort": ".ort",
       "datum": ".datum", "weiter": "a.weiter"}

# erwartung: "reparieren" = Vorschlag muss übernommen werden, "nichts" = C darf nichts ändern,
#            "ablehnen"   = C muss es versuchen, den (absichtlich falschen) Vorschlag aber verwerfen
SZENARIEN = [
    dict(name="gesund (Kontrolle)", design="alt", baseline=True, erwartung="nichts"),
    dict(name="gesund, Kaltstart ohne Baseline", design="alt", baseline=False, erwartung="nichts"),
    dict(name="leere Seite (kein Redesign)", design="leer", baseline=True, erwartung="nichts"),
    dict(name="Relaunch: Karten umbenannt", design="neu", baseline=True, erwartung="reparieren",
         vorschlag={**ALT, "stelle": "article.job"}),
    dict(name="Teilbruch: nur Ort umbenannt", design="teil", baseline=True, erwartung="reparieren",
         vorschlag={**ALT, "ort": ".location"}),
    dict(name="Alle Klassen umbenannt", design="felder", baseline=True, erwartung="reparieren",
         vorschlag={"stelle": "article.job", "firma": ".company", "titel": ".position", "ort": ".location",
                    "datum": ".date", "weiter": "a.weiter"}),
    dict(name="Firma/Titel vertauscht", design="tausch", baseline=True, erwartung="reparieren",
         vorschlag={**ALT, "firma": ".titel", "titel": ".firma"}),
    dict(name="Firma/Titel vertauscht, Kaltstart", design="tausch", baseline=False, erwartung="reparieren",
         vorschlag={**ALT, "firma": ".titel", "titel": ".firma"}),
    dict(name="Falscher Vorschlag: Werbung mitgezählt", design="neu", baseline=True, erwartung="ablehnen",
         nur_simuliert=True, vorschlag={**ALT, "stelle": "article.karte"}),
    dict(name="Falscher Vorschlag: Firma/Titel verdreht", design="neu", baseline=True, erwartung="ablehnen",
         nur_simuliert=True, vorschlag={**ALT, "stelle": "article.job", "firma": ".titel", "titel": ".firma"}),
]


# --------------------------------------------------------------------------- Hilfen
@contextlib.contextmanager
def ersetzt(*aenderungen):
    """Setzt Attribute (objekt, name, wert) und stellt sie am Ende wieder her."""
    alt = [(o, n, getattr(o, n)) for o, n, _ in aenderungen]
    for o, n, w in aenderungen:
        setattr(o, n, w)
    try:
        yield
    finally:
        for o, n, w in reversed(alt):
            setattr(o, n, w)


def _server(verzeichnis: Path):
    class Leise(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Leise, directory=str(verzeichnis)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _lies(pfad: Path) -> list[dict]:
    with open(pfad, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _mit_lesefehler(zeilen: list[dict]) -> list[dict]:
    """Simuliert, dass das Bild-Lesen sich verliest: in einer Zeile pro Seite ein Zeichen im Ort."""
    zeilen = [dict(z) for z in zeilen]
    for z in zeilen:
        if len(z.get("ort", "")) >= 4:
            z["ort"] = z["ort"].replace("ü", "u") if "ü" in z["ort"] else z["ort"][:-1] + "x"
            break
    return zeilen


def _zaehlen(funktion, zaehler: dict, name: str):
    @functools.wraps(funktion)
    def verpackt(*a, **k):
        zaehler[name] += 1
        return funktion(*a, **k)
    return verpackt


def felder_messen(gelesen: list[dict], wahr: list[dict]) -> dict:
    felder = ("firma", "titel", "ort", "datum")
    richtig = sum(qualitaet.norm(z.get(f)) == qualitaet.norm(w.get(f))
                  for z, w in zip(gelesen, wahr) for f in felder)
    return {"gefunden": len(gelesen), "erwartet": len(wahr), "richtig": richtig, "gesamt": 4 * len(wahr)}


# --------------------------------------------------------------------------- ein Szenario
def szenario_laufen(sz: dict, echt: bool = False, lesefehler: bool = False) -> dict:
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        stumm = io.StringIO()
        with ersetzt((erzeugen, "HIER", tmp), (erzeugen, "SITE", tmp / "site")), contextlib.redirect_stdout(stumm):
            erzeugen.main("alt")
            alt_daten = _lies(tmp / "wahrheit.csv")        # "frühere gesunde Läufe" für die Baseline
            if sz["design"] != "alt":
                erzeugen.main(sz["design"])
            wahr = _lies(tmp / "wahrheit.csv")

        (tmp / "selektoren.json").write_text(json.dumps(ALT), encoding="utf-8")
        if sz["baseline"]:
            seite1 = [{k: z[k] for k in qualitaet.FELDER} for z in alt_daten if z["seite"] == "1"]
            (tmp / "baseline.json").write_text(json.dumps(qualitaet.baseline_neu(seite1)), encoding="utf-8")

        zaehler = {"bild": 0, "claude": 0}
        bild_fn, claude_fn = vb.bild_lesen, vc.claude_fragen
        if not echt:
            def bild_fn(pfad, key):
                nr = int(re.search(r"seite-(\d+)", pfad.name).group(1))
                zeilen = [r for r in wahr if int(r["seite"]) == nr]
                return (_mit_lesefehler(zeilen) if lesefehler else zeilen), 2000, 900

            def claude_fn(prompt, key):
                llm.buche(vc.kosten, 3000, 150)
                return json.dumps(sz["vorschlag"])
        key = vb.api_key() if echt else "simuliert"
        if echt and not key:
            raise SystemExit("FEHLER: --echt braucht ANTHROPIC_API_KEY (Umgebungsvariable oder .env).")

        srv = _server(tmp / "site")
        url = f"http://127.0.0.1:{srv.server_address[1]}/seite-1.html"
        start = time.time()
        try:
            with ersetzt((vc, "HIER", tmp), (vc, "SEL_DATEI", tmp / "selektoren.json"),
                         (vc, "BASE_DATEI", tmp / "baseline.json"), (vc, "LOG", tmp / "log.txt"),
                         (vc, "WARTE_MS", 3000 if echt else 1500), (vc, "PAUSE_SEKUNDEN", (0, 0)),
                         (vb, "BILDER", tmp / "bilder"), (vb, "api_key", lambda: key),
                         (vb, "bild_lesen", _zaehlen(bild_fn, zaehler, "bild")),
                         (vc, "claude_fragen", _zaehlen(claude_fn, zaehler, "claude")),
                         (sys, "argv", ["benchmark", "--unsichtbar", "--url", url])), \
                    contextlib.redirect_stdout(stumm):
                vc.main()
                kosten = llm.kosten_eur(vc.kosten)
        finally:
            srv.shutdown()
            srv.server_close()
        dauer = time.time() - start

        gelesen = _lies(tmp / "ergebnis_c.csv")
        uebernommen = json.loads((tmp / "selektoren.json").read_text(encoding="utf-8")) != ALT

    daten = felder_messen(gelesen, wahr)
    versucht = zaehler["claude"] > 0
    ergebnis_ok = {"reparieren": versucht and uebernommen, "nichts": not versucht and not uebernommen,
                   "ablehnen": versucht and not uebernommen}[sz["erwartung"]]
    daten_ok = daten["richtig"] == daten["gesamt"] and daten["gefunden"] == daten["erwartet"]
    return {"name": sz["name"], "erwartung": sz["erwartung"], "versucht": versucht, "uebernommen": uebernommen,
            "entscheidung_ok": ergebnis_ok, "daten_ok": daten_ok, "daten": daten,
            "schaden": uebernommen and (sz["erwartung"] != "reparieren" or not daten_ok),
            "unnoetig": versucht and sz["erwartung"] == "nichts",
            "bild": zaehler["bild"], "claude": zaehler["claude"], "kosten": kosten, "dauer": dauer}


# --------------------------------------------------------------------------- Ausgabe
def _passiert(r: dict) -> str:
    if not r["versucht"]:
        return "nichts getan"
    return "repariert" if r["uebernommen"] else "Vorschlag abgelehnt"


def _erwartet(e: str) -> str:
    return {"reparieren": "reparieren", "nichts": "nichts tun", "ablehnen": "ablehnen"}[e]


def tabelle(ergebnisse: list[dict], echt: bool, lesefehler: bool, wiederholungen: int) -> str:
    modus = "ECHTES Claude" if echt else "simuliertes Claude" + (" mit Lesefehlern im Screenshot" if lesefehler else "")
    zeilen = [f"Modus: {modus}" + (f", {wiederholungen} Durchgänge" if wiederholungen > 1 else ""), "",
              "| Szenario | Soll | Ist | Entscheidung | Schaden | Felder richtig | Bilder | Textanfragen | Kosten | Zeit |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in ergebnisse:
        d = r["daten"]
        felder = f"{d['richtig']}/{d['gesamt']}" if d["gesamt"] else "n/a (keine Stellen erwartet)"
        if d["gefunden"] != d["erwartet"]:
            felder += f" ({d['gefunden']} statt {d['erwartet']} Stellen)"
        zeilen.append(f"| {r['name']} | {_erwartet(r['erwartung'])} | {_passiert(r)} | "
                      f"{'ok' if r['entscheidung_ok'] else 'FALSCH'} | {'JA' if r['schaden'] else 'nein'} | {felder} | "
                      f"{r['bild']} | {r['claude']} | {r['kosten'] * 100:.2f} ct | {r['dauer']:.0f} s |")
    n = len(ergebnisse)
    zeilen += ["", f"* Richtige Entscheidungen: {sum(r['entscheidung_ok'] for r in ergebnisse)} von {n}",
               f"* Schäden (falscher oder unnötiger Vorschlag übernommen): {sum(r['schaden'] for r in ergebnisse)}",
               f"* Unnötige Reparaturversuche bei gesunden Seiten: {sum(r['unnoetig'] for r in ergebnisse)}",
               f"* Daten am Ende vollständig und richtig: {sum(r['daten_ok'] for r in ergebnisse)} von {n}",
               f"* Gesamtkosten: {sum(r['kosten'] for r in ergebnisse) * 100:.2f} ct"
               + ("" if echt else " (Modellrechnung: 2000/900 Tokens je Bild, 3000/150 je Textanfrage)")]
    return "\n".join(zeilen)


def main():
    ap = argparse.ArgumentParser(description="Benchmark für die Selbstheilung von Variante C")
    ap.add_argument("--echt", action="store_true", help="echtes Claude statt Simulation (kostet Geld)")
    ap.add_argument("--lesefehler", action="store_true", help="simuliertes Bild-Lesen mit Tippfehlern")
    ap.add_argument("--wiederholungen", type=int, default=1, help="Durchgänge je Szenario (sinnvoll mit --echt)")
    ap.add_argument("--nur", default="", help="nur Szenarien, deren Name diesen Text enthält")
    args = ap.parse_args()

    auswahl = [s for s in SZENARIEN if args.nur.lower() in s["name"].lower() and not (args.echt and s.get("nur_simuliert"))]
    if not auswahl:
        raise SystemExit("Kein Szenario gewählt.")
    ergebnisse = []
    for durchgang in range(args.wiederholungen):
        for sz in auswahl:
            print(f"  läuft: {sz['name']}" + (f" (Durchgang {durchgang + 1})" if args.wiederholungen > 1 else ""), flush=True)
            ergebnisse.append(szenario_laufen(sz, args.echt, args.lesefehler))
    text = tabelle(ergebnisse, args.echt, args.lesefehler, args.wiederholungen)
    print("\n" + text)
    (HIER / "benchmark_ergebnis.md").write_text(text + "\n", encoding="utf-8")
    print(f"\nGespeichert: {HIER / 'benchmark_ergebnis.md'}")


if __name__ == "__main__":
    main()
