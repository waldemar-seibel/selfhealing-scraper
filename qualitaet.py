"""
Prüfregeln ohne Browser und ohne API: Ist das, was ein Scraper gelesen hat, noch gesund?

Zwei Fragen, zwei Werkzeuge:

1. extraktion_gesund(): Passt das Ergebnis zu dem, was bisher normal war? (kostenlos, bei jeder Seite)
   Findet auch Teilbrüche: Karten werden noch gefunden, aber ein Feld (z. B. der Ort) ist plötzlich
   leer oder Firma und Titel sind vertauscht. Dafür merkt sich der Scraper eine "Baseline":
   Ausfüllquoten und Wortschatz je Feld aus früheren, gesunden Seiten.
   Ein fehlender Ort ist nicht automatisch ein Fehler. Verglichen wird mit der bisherigen Quote.

2. vergleichen(): Stimmen zwei Lesungen derselben Seite inhaltlich überein? (DOM gegen Screenshot)
   Es werden Firma/Titel-Paare zugeordnet (mit Toleranz für Lesefehler wie "Gützersloh"), nicht nur
   Anzahlen verglichen. So fällt auf, wenn ein Selektor zwar 12 Elemente trifft, aber die falschen.
"""
import re
from difflib import SequenceMatcher

FELDER = ("firma", "titel", "ort", "datum")
PFLICHT = ("firma", "titel")
MAX_WORTSCHATZ = 400          # Obergrenze je Feld, damit die Baseline klein bleibt
MAX_GEWICHT = 20              # so viele Seiten zählen höchstens in den gleitenden Mittelwert
QUOTE_EINBRUCH = 0.35         # Quote darf höchstens so weit unter die Baseline fallen
PAAR_SCHWELLE = 0.85          # ab so viel Ähnlichkeit gelten zwei Texte als "dasselbe"


def norm(s) -> str:
    return " ".join(str(s if s is not None else "").lower().split())


def aehnlichkeit(a, b) -> float:
    a, b = norm(a), norm(b)
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def woerter(wert) -> set:
    return set(re.findall(r"\w+", norm(wert)))


# --------------------------------------------------------------------------- Baseline
def quoten(zeilen: list[dict]) -> dict:
    n = len(zeilen) or 1
    return {f: sum(1 for z in zeilen if str(z.get(f) or "").strip()) / n for f in FELDER}


def wortschatz(zeilen: list[dict]) -> dict:
    return {f: set().union(*[woerter(z.get(f)) for z in zeilen]) if zeilen else set() for f in FELDER}


def baseline_neu(zeilen: list[dict]) -> dict:
    return {"n": 1, "quoten": quoten(zeilen),
            "woerter": {f: sorted(w)[:MAX_WORTSCHATZ] for f, w in wortschatz(zeilen).items()}}


def baseline_erweitern(baseline: dict | None, zeilen: list[dict]) -> dict:
    """Nimmt eine gesunde Seite in die Baseline auf (gleitender Mittelwert, Wortschatz vereinigt)."""
    if not baseline or not zeilen:
        return baseline or baseline_neu(zeilen)
    n = min(baseline.get("n", 1), MAX_GEWICHT)
    neu_q = quoten(zeilen)
    neu_w = wortschatz(zeilen)
    return {"n": n + 1,
            "quoten": {f: (baseline["quoten"].get(f, 0) * n + neu_q[f]) / (n + 1) for f in FELDER},
            "woerter": {f: sorted(set(baseline["woerter"].get(f, [])) | neu_w[f])[:MAX_WORTSCHATZ] for f in FELDER}}


def _ueberlappung(zeilen: list[dict], feld: str, vokabular: set) -> float:
    anteile = []
    for z in zeilen:
        w = woerter(z.get(feld))
        if w:
            anteile.append(len(w & vokabular) / len(w))
    return sum(anteile) / len(anteile) if anteile else 0.0


def extraktion_gesund(zeilen: list[dict], baseline: dict | None = None) -> tuple[bool, list[str]]:
    """Gibt (gesund, Probleme) zurück. Ohne Baseline gelten nur die absoluten Regeln."""
    if not zeilen:
        return False, ["keine Stellen gefunden"]
    probleme = []
    q = quoten(zeilen)
    for f in PFLICHT:
        if q[f] < 0.9:
            probleme.append(f"{f} nur bei {q[f]:.0%} der Stellen gefüllt")
    gleich = sum(1 for z in zeilen if norm(z.get("firma")) and norm(z.get("firma")) == norm(z.get("titel")))
    if gleich / len(zeilen) > 0.2:
        probleme.append("Firma und Titel sind oft identisch")
    if baseline:
        for f in FELDER:
            frueher = baseline["quoten"].get(f, 0)
            if frueher >= 0.5 and q[f] < frueher - QUOTE_EINBRUCH:
                probleme.append(f"{f} nur noch bei {q[f]:.0%} gefüllt (bisher {frueher:.0%})")
        vok = {f: set(baseline["woerter"].get(f, [])) for f in FELDER}
        for f in FELDER:
            if not vok[f]:
                continue
            eigen = _ueberlappung(zeilen, f, vok[f])
            for g in FELDER:
                if g != f and vok[g] and _ueberlappung(zeilen, f, vok[g]) > eigen + 0.3:
                    probleme.append(f"{f} enthält Werte, die sonst in {g} stehen (Felder vertauscht?)")
                    break
    return not probleme, probleme


# --------------------------------------------------------------------------- DOM gegen Screenshot
def vergleichen(test: list[dict], gegenprobe: list[dict]) -> dict:
    """Ordnet jede Zeile der Gegenprobe der ähnlichsten Test-Zeile zu (Firma + Titel).
    Rückgabe: Anteil gepaarter Zeilen sowie Übereinstimmung von Ort und Datum bei den Paaren."""
    frei = list(range(len(test)))
    paare = []
    for g in gegenprobe:
        beste, bester_wert = None, 0.0
        for i in frei:
            wert = (aehnlichkeit(test[i].get("firma"), g.get("firma"))
                    + aehnlichkeit(test[i].get("titel"), g.get("titel"))) / 2
            if wert > bester_wert:
                beste, bester_wert = i, wert
        if beste is not None and bester_wert >= PAAR_SCHWELLE:
            paare.append((test[beste], g))
            frei.remove(beste)
    ergebnis = {"paare": len(paare) / (max(len(test), len(gegenprobe)) or 1)}
    for f in ("ort", "datum"):
        ergebnis[f] = (sum(aehnlichkeit(t.get(f), g.get(f)) >= PAAR_SCHWELLE for t, g in paare) / len(paare)
                       if paare else 0.0)
    return ergebnis
