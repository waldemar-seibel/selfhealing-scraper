"""
Gemeinsame Bausteine für Variante B und C: Modell, Preise, API-Schlüssel und der API-Aufruf.

Der Aufruf wiederholt sich bei vorübergehenden Fehlern (Netz-Hänger, 429, 5xx) mit wachsender
Pause und gibt danach einen klaren Fehler (ApiFehler) zurück. Ein einzelner Aussetzer reißt so
nicht mehr den ganzen Lauf ab; die aufrufende Stelle entscheidet, was mit der Seite passiert.
"""
import os
import time
from pathlib import Path

import requests

HIER = Path(__file__).parent
API_URL = "https://api.anthropic.com/v1/messages"
MODELL = "claude-haiku-5-5"
# Listenpreis in USD je 1 Mio. Tokens (Eingabe, Ausgabe), Stand Oktober 2026.
# Gilt für Anfragen bis 100.000 Eingabe-Tokens; darüber kostet alles das Fünffache.
PREIS_USD_PRO_MIO = (0.10, 0.50)
LANG_GRENZE = 100_000
LANG_FAKTOR = 5
USD_EUR = 0.92


class ApiFehler(Exception):
    """API nicht erreichbar oder Anfrage abgelehnt (nach allen Wiederholungen)."""


def api_key() -> str:
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    env = HIER / ".env"
    if not k and env.exists():
        for zeile in env.read_text(encoding="utf-8").splitlines():
            if zeile.startswith("ANTHROPIC_API_KEY="):
                k = zeile.split("=", 1)[1].strip().strip('"')
    return k


def api_post(payload: dict, key: str, versuche: int = 4) -> dict:
    """Schickt eine Anfrage an die Messages-API. Wiederholt bei Netzfehlern, 429 und 5xx.
    Andere Fehler (z. B. 400/401/404) sind endgültig und werden sofort gemeldet."""
    grund = ""
    for nr in range(1, versuche + 1):
        pause = 2.0 ** nr
        try:
            r = requests.post(API_URL, timeout=120, json=payload, headers={
                "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        except (requests.Timeout, requests.ConnectionError) as e:
            grund = f"Netzwerkfehler ({e.__class__.__name__})"
        else:
            if r.status_code == 200:
                return r.json()
            if r.status_code != 429 and r.status_code < 500:
                raise ApiFehler(f"HTTP {r.status_code}: {r.text[:200]}")
            grund = f"HTTP {r.status_code}"
            try:
                pause = min(float(r.headers.get("retry-after", pause)), 30.0)
            except ValueError:
                pass
        if nr < versuche:
            print(f"    API: {grund}, neuer Versuch {nr + 1}/{versuche} in {pause:.0f} s")
            time.sleep(pause)
    raise ApiFehler(f"{grund} nach {versuche} Versuchen")


def neue_kosten() -> dict:
    return {"ein": 0, "aus": 0, "usd": 0.0}


def buche(kosten: dict, ein: int, aus: int):
    """Bucht eine Anfrage. Der Preis wird je Anfrage bestimmt (lange Prompts sind teurer)."""
    faktor = LANG_FAKTOR if ein > LANG_GRENZE else 1
    kosten["ein"] += ein
    kosten["aus"] += aus
    kosten["usd"] += (ein * PREIS_USD_PRO_MIO[0] + aus * PREIS_USD_PRO_MIO[1]) / 1e6 * faktor


def kosten_eur(kosten: dict) -> float:
    return kosten["usd"] * USD_EUR
