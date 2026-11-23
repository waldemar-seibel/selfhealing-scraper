# Scraping-Übung mit Playwright

Ein Übungsprojekt: eine erfundene Jobbörse automatisch auslesen, auf zwei Arten, und die
Ergebnisse vergleichen. Alles läuft lokal auf deinem Rechner, keine echte Website wird belastet.

| Datei | Wofür |
|---|---|
| `uebungsseite/erzeugen.py` | baut die Übungs-Jobbörse (10 Seiten, 120 erfundene Stellen) und `wahrheit.csv` |
| `variante_a_daten.py` | **Variante A:** liest die Daten direkt aus der Seite (Selektoren) |
| `variante_b_screenshots.py` | **Variante B:** macht Screenshots, Claude liest die Bilder |
| `variante_c_kombi.py` | **Variante C:** erst A; bricht A wegen neuem Design, schlägt Claude neue Selektoren vor, das Programm prüft sie per Screenshot und übernimmt sie nur dann |
| `vergleich.py` | misst, wie gut A, B und C waren (gefunden, zu viel, Felder, Dauer, Kosten) |

## 1. Einrichten (einmal)

Doppelklick auf **`einrichten.bat`**. Das legt eine eigene Python-Umgebung an, installiert
Playwright und den Chrome-Browser dafür (ca. 150 MB) und erzeugt die Übungsseite.

## 2. Übungsseite starten

Doppelklick auf **`seite_starten.bat`**. Es geht ein schwarzes Fenster auf (das ist der kleine
Webserver, offen lassen) und dein Browser zeigt die Übungs-Jobbörse.

## 3. Ausprobieren

Zweites PowerShell-Fenster öffnen:
```
cd <Pfad zu deinem Projektordner>
.venv\Scripts\activate
python variante_a_daten.py
```
Du siehst einen Chrome, der selbst durch die Seiten blättert. Danach:
```
python variante_b_screenshots.py --nur-bilder      (nur Screenshots, kostenlos)
python variante_b_screenshots.py                   (mit Claude, ein paar Cent)
python vergleich.py
```
Für Variante B mit Claude: Datei `.env` in diesem Ordner anlegen mit
`ANTHROPIC_API_KEY=dein-schlüssel`.

## 4. Aufgaben zum Lernen

1. **Selektoren finden:** Auf der Übungsseite F12 drücken, mit dem Pfeil-Symbol auf eine
   Stellen-Karte klicken. Woran erkennst du Stelle vs. Werbung? (Vergleich mit `SELEKTOREN`
   in `variante_a_daten.py`)
2. **Design ändern:** `python uebungsseite/erzeugen.py --design neu` (Karten heißen dann "job"
   statt "stelle"), beide Varianten laufen lassen. Welche bricht, welche nicht? Warum?
   Zurück zum alten Design: `python uebungsseite/erzeugen.py`
3. **Feld ergänzen:** Ein Gehalt in die Karten einbauen und in beiden Varianten mit auslesen.
4. **Fehlerfall:** Webserver während Variante A schließen. Was passiert, was macht `mit_wiederholung`?
5. **Unsichtbar:** `--unsichtbar` testen. Wie viel schneller ist es ohne sichtbaren Browser?

## 5. Variante C: Selbstreparatur

```
python uebungsseite/erzeugen.py --design neu
python variante_c_kombi.py
python vergleich.py
```
Die Selektoren stehen in `selektoren.json`. Ändert sich das Design, holt sich das Programm bei
Claude einen Vorschlag, prüft ihn gegen einen Screenshot und speichert ihn nur, wenn Anzahl UND
Inhalt (Firma/Titel-Paare, Ort, Datum) übereinstimmen. Was passiert ist, steht in `reparatur_log.txt`.

Vor jeder Reparatur macht C einen kostenlosen Gesundheitscheck: Wie viele Stellen haben noch einen
Ort, ein Datum, eine Firma? Das wird mit dem Normalzustand in `baseline.json` verglichen. So fällt
auch ein Teilbruch auf, bei dem die Karten noch gefunden werden, aber ein Feld leer ist.

Weitere Designs zum Ausprobieren (immer erst `erzeugen.py --design ...`, dann C):

| Design | Was passiert | Was C tun soll |
|---|---|---|
| `neu` | Karten heißen "job" | reparieren |
| `teil` | nur der Ort heißt "location" | Teilbruch erkennen, reparieren |
| `felder` | alle Klassen umbenannt | reparieren |
| `tausch` | Firma und Titel vertauscht | erkennen, reparieren |
| `leer` | gültige Seite "Keine Treffer" | NICHT reparieren |

Tipp für `teil`: Erst `--design alt` und C laufen lassen (das legt die Baseline an), dann
`--design teil` und C noch einmal.

## 6. Tests

```
pip install -r requirements-dev.txt
pytest
```
Die Tests simulieren Claude (kein Schlüssel nötig, keine Kosten).

## Wichtig für echte Websites

Was du hier lernst, funktioniert technisch auch auf echten Seiten. Erlaubt ist es dort nur, wenn
die Nutzungsbedingungen es zulassen oder der Betreiber zustimmt. Jobportale wie StepStone,
Indeed, LinkedIn und XING verbieten automatisiertes Auslesen. Zum Üben an öffentlichen Seiten
gibt es extra Übungsseiten wie `books.toscrape.com` und `quotes.toscrape.com`.
