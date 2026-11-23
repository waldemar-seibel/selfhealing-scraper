"""
Vergleich: Wie gut haben Variante A und B die Seite gelesen?

    python vergleich.py

Misst gegen uebungsseite/wahrheit.csv:
  * Gefunden:     wie viele echte Stellen wurden erkannt?
  * Zu viel:      wie viele "Stellen" gab es gar nicht (z. B. Werbung mitgezählt, erfunden)?
  * Feldgenauigkeit: bei den erkannten Stellen, wie oft stimmen Firma, Titel, Ort, Datum exakt?
  * Dauer und Kosten aus messung_a.txt / messung_b.txt

Zuordnung: Eine gelesene Stelle passt zu einer echten, wenn Seite + Firma + Titel übereinstimmen
(ohne Groß-/Kleinschreibung und Leerzeichen). Variante A hätte sogar die ID, B nicht. Damit beide
fair verglichen werden, nutzen wir für beide dieselbe Regel.
"""
import csv
from collections import Counter
from pathlib import Path

HIER = Path(__file__).parent
FELDER = ["firma", "titel", "ort", "datum"]


def lies(pfad: Path) -> list[dict]:
    if not pfad.exists():
        return []
    with open(pfad, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def norm(s) -> str:
    return " ".join(str(s if s is not None else "").lower().split())


def schluessel(z: dict) -> tuple:
    return (str(z.get("seite")), norm(z.get("firma")), norm(z.get("titel")))


def messung(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    return dict(z.split("=", 1) for z in pfad.read_text(encoding="utf-8").split() if "=" in z)


def bewerten(name: str, ergebnis: list[dict], wahr: list[dict], mess: dict):
    if not ergebnis:
        print(f"\n{name}: keine Ergebnisse (Skript schon gelaufen?)")
        return
    # Kandidaten je Schlüssel. Gibt es mehrere gleiche (gleiche Firma + Titel auf einer Seite),
    # nehmen wir den, bei dem die meisten übrigen Felder passen. Sonst würden wir Treffer vertauschen.
    kandidaten = {}
    for w in wahr:
        kandidaten.setdefault(schluessel(w), []).append(w)
    treffer, zu_viel = [], []
    for z in ergebnis:
        liste = kandidaten.get(schluessel(z), [])
        if not liste:
            zu_viel.append(z)
            continue
        bester = max(liste, key=lambda w: sum(norm(z.get(f)) == norm(w.get(f)) for f in FELDER))
        liste.remove(bester)
        treffer.append((z, bester))
    offen = Counter(schluessel(w) for liste in kandidaten.values() for w in liste)
    gefunden = len(treffer)
    print(f"\n=== {name} ===")
    print(f"  Gefunden:  {gefunden} von {len(wahr)} echten Stellen ({gefunden / len(wahr):.0%})")
    print(f"  Zu viel:   {len(zu_viel)}" + (f"  (z. B. {zu_viel[0].get('titel')!r})" if zu_viel else ""))
    for feld in ["ort", "datum"]:
        richtig = sum(1 for z, w in treffer if norm(z.get(feld)) == norm(w.get(feld)))
        print(f"  Feld {feld:6s} richtig: {richtig}/{gefunden}")
    print(f"  Dauer:     {mess.get('dauer_sekunden', '?')} s,  Kosten: {mess.get('kosten_eur', '?')} €")
    fehlend = [w for w in wahr if offen[schluessel(w)] > 0]
    if fehlend:
        print(f"  Beispiel nicht gefunden: {fehlend[0]['firma']} / {fehlend[0]['titel']} (Seite {fehlend[0]['seite']})")


def main():
    wahr = lies(HIER / "uebungsseite" / "wahrheit.csv")
    if not wahr:
        print("wahrheit.csv fehlt: zuerst  python uebungsseite/erzeugen.py")
        return
    bewerten("Variante A (Daten direkt)", lies(HIER / "ergebnis_a.csv"), wahr, messung(HIER / "messung_a.txt"))
    bewerten("Variante B (Screenshot + Claude)", lies(HIER / "ergebnis_b.csv"), wahr, messung(HIER / "messung_b.txt"))
    bewerten("Variante C (Kombi mit Selbstreparatur)", lies(HIER / "ergebnis_c.csv"), wahr, messung(HIER / "messung_c.txt"))


if __name__ == "__main__":
    main()
