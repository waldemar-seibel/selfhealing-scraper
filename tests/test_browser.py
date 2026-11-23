"""Ende-zu-Ende-Tests mit echtem (unsichtbarem) Browser gegen die lokale Übungsseite.
Claude wird simuliert: kein API-Schlüssel nötig, keine Kosten, immer gleiches Ergebnis.

Jedes Design aus uebungsseite/erzeugen.py hat hier sein Szenario:
  neu      Relaunch, Karten heißen anders           -> C repariert sich
  teil     nur der Ort wurde umbenannt              -> C erkennt den Teilbruch und repariert
  felder   alle Klassen umbenannt                   -> C repariert sich
  tausch   Firma/Titel vertauscht                   -> C erkennt es (mit und ohne Baseline)
  leer     gültige Seite ohne Treffer               -> C repariert NICHT
Dazu: falsche Vorschläge, API-Ausfälle, "gesunder Lauf kostet nichts", Variante B komplett."""
import csv
import json
import re
import sys

import pytest

import llm
import qualitaet
import variante_a_daten as va
import variante_b_screenshots as vb
import variante_c_kombi as vc

ALT = {"stelle": "article.stelle", "firma": ".firma", "titel": ".titel", "ort": ".ort",
       "datum": ".datum", "weiter": "a.weiter"}
NEU = {**ALT, "stelle": "article.job"}
TEIL = {**ALT, "ort": ".location"}
FELDER = {"stelle": "article.job", "firma": ".company", "titel": ".position", "ort": ".location",
          "datum": ".date", "weiter": "a.weiter"}
TAUSCH = {**ALT, "firma": ".titel", "titel": ".firma"}


# --------------------------------------------------------------------------- Hilfen
def _lauf(modul, monkeypatch, tmp_path, url, *extra):
    monkeypatch.setattr(modul, "HIER", tmp_path)
    for m in (va, vb, vc):
        monkeypatch.setattr(m, "PAUSE_SEKUNDEN", (0, 0))       # Tests müssen nicht höflich warten
    monkeypatch.setattr(sys, "argv", ["x", "--unsichtbar", "--url", url, *extra])
    modul.main()


def _lies(pfad):
    with open(pfad, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _log(tmp):
    return (tmp / "log.txt").read_text(encoding="utf-8")


def _c_einrichten(monkeypatch, tmp):
    monkeypatch.setattr(vc, "SEL_DATEI", tmp / "selektoren.json")
    monkeypatch.setattr(vc, "BASE_DATEI", tmp / "baseline.json")
    monkeypatch.setattr(vc, "LOG", tmp / "log.txt")
    monkeypatch.setattr(vc, "WARTE_MS", 1500)                   # Test-Seite ist sofort da
    monkeypatch.setattr(vb, "BILDER", tmp / "bilder")


def _baseline_schreiben(tmp, wahr):
    """Simuliert 'frühere gesunde Läufe': Baseline aus den Daten der ersten Seite."""
    seite1 = [{k: z[k] for k in qualitaet.FELDER} for z in wahr if int(z["seite"]) == 1]
    (tmp / "baseline.json").write_text(json.dumps(qualitaet.baseline_neu(seite1)), encoding="utf-8")


def _fake_claude(monkeypatch, wahr, vorschlag=None, key="test", bild_fehler_seite=None, claude_fehler=False):
    """Ersetzt die beiden API-Aufrufe. Gibt einen Zähler zurück (wie oft wurde was gefragt)."""
    zaehler = {"bild": 0, "claude": 0}

    def bild(pfad, key_):
        zaehler["bild"] += 1
        nr = int(re.search(r"seite-(\d+)", pfad.name).group(1))
        if nr == bild_fehler_seite:
            raise llm.ApiFehler("HTTP 529 nach 4 Versuchen")
        return [r for r in wahr if int(r["seite"]) == nr], 2000, 900

    def claude(prompt, key_):
        zaehler["claude"] += 1
        if claude_fehler:
            raise llm.ApiFehler("HTTP 503 nach 4 Versuchen")
        return json.dumps(vorschlag)

    monkeypatch.setattr(vb, "bild_lesen", bild)
    monkeypatch.setattr(vb, "api_key", lambda: key)
    monkeypatch.setattr(vc, "claude_fragen", claude)
    return zaehler


def _spalte(zeilen, feld):
    return [z[feld] for z in zeilen]


# --------------------------------------------------------------------------- Variante A und B
def test_variante_a_liest_alles_und_ueberspringt_werbung(seite, monkeypatch):
    url, wahr, tmp = seite
    _lauf(va, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_a.csv")
    assert len(gelesen) == len(wahr) == 120
    assert not any("Lebenslauf" in z["titel"] for z in gelesen)


def test_variante_b_end_to_end_liest_alle_seiten_und_misst_kosten(seite, monkeypatch):
    url, wahr, tmp = seite
    monkeypatch.setattr(vb, "BILDER", tmp / "bilder")
    zaehler = _fake_claude(monkeypatch, wahr)
    _lauf(vb, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_b.csv")
    assert len(gelesen) == 120
    assert _spalte(gelesen, "firma") == _spalte(wahr, "firma")
    assert zaehler["bild"] == 10
    messung = (tmp / "messung_b.txt").read_text(encoding="utf-8")
    assert "tokens_ein=20000" in messung and "tokens_aus=9000" in messung
    assert "kosten_eur=0.0060" in messung and "seiten_nicht_gelesen=0" in messung


def test_variante_b_ueberspringt_nur_die_seite_bei_api_ausfall(seite, monkeypatch):
    url, wahr, tmp = seite
    monkeypatch.setattr(vb, "BILDER", tmp / "bilder")
    _fake_claude(monkeypatch, wahr, bild_fehler_seite=3)
    _lauf(vb, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_b.csv")
    assert len(gelesen) == 108 and "3" not in {z["seite"] for z in gelesen}
    assert "seiten_nicht_gelesen=1" in (tmp / "messung_b.txt").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- Variante C: Reparatur
@pytest.mark.parametrize("seite", ["neu"], indirect=True)
def test_variante_c_repariert_sich_bei_neuem_design(seite, monkeypatch):
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    zaehler = _fake_claude(monkeypatch, wahr, NEU)
    _lauf(vc, monkeypatch, tmp, url)
    assert len(_lies(tmp / "ergebnis_c.csv")) == 120
    assert json.loads((tmp / "selektoren.json").read_text())["stelle"] == "article.job"
    assert "übernommen" in _log(tmp)
    assert zaehler["claude"] == 1                       # nur eine Reparatur, danach liest A wieder allein
    assert (tmp / "baseline.json").exists()


@pytest.mark.parametrize("seite", ["teil"], indirect=True)
def test_variante_c_erkennt_teilbruch_nur_ort_umbenannt(seite, monkeypatch):
    """Der Fall aus der Auswertung: Karten, Firma, Titel passen noch, nur der Ort ist überall leer.
    Früher meldete C '120/120 gefunden' und ließ den Ort still verloren gehen."""
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _baseline_schreiben(tmp, wahr)
    zaehler = _fake_claude(monkeypatch, wahr, TEIL)
    _lauf(vc, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_c.csv")
    assert len(gelesen) == 120
    assert _spalte(gelesen, "ort") == _spalte(wahr, "ort")           # Ort ist vollständig und richtig
    assert json.loads((tmp / "selektoren.json").read_text())["ort"] == ".location"
    assert "ort nur noch bei" in _log(tmp)
    assert zaehler["claude"] == 1


@pytest.mark.parametrize("seite", ["teil"], indirect=True)
def test_variante_c_ohne_api_key_warnt_bei_teilbruch(seite, monkeypatch):
    """Ohne Schlüssel keine Reparatur, aber auch kein stilles Weiterlaufen: eine Warnung im Protokoll."""
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _baseline_schreiben(tmp, wahr)
    zaehler = _fake_claude(monkeypatch, wahr, TEIL, key="")
    _lauf(vc, monkeypatch, tmp, url)
    assert len(_lies(tmp / "ergebnis_c.csv")) == 120
    assert "WARNUNG" in _log(tmp) and "ort nur noch bei" in _log(tmp)
    assert zaehler == {"bild": 0, "claude": 0}


@pytest.mark.parametrize("seite", ["felder"], indirect=True)
def test_variante_c_repariert_komplett_umbenannte_felder(seite, monkeypatch):
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _fake_claude(monkeypatch, wahr, FELDER)
    _lauf(vc, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_c.csv")
    assert [(z["firma"], z["titel"], z["ort"], z["datum"]) for z in gelesen] == \
           [(z["firma"], z["titel"], z["ort"], z["datum"]) for z in wahr]
    assert json.loads((tmp / "selektoren.json").read_text())["firma"] == ".company"


@pytest.mark.parametrize("seite", ["tausch"], indirect=True)
def test_variante_c_erkennt_vertauschte_felder_mit_baseline(seite, monkeypatch):
    """Alle Felder gefüllt, alle Zahlen stimmen, aber .firma enthält jetzt die Jobtitel."""
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _baseline_schreiben(tmp, wahr)
    _fake_claude(monkeypatch, wahr, TAUSCH)
    _lauf(vc, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_c.csv")
    assert _spalte(gelesen, "firma") == _spalte(wahr, "firma")
    assert _spalte(gelesen, "titel") == _spalte(wahr, "titel")
    assert "vertauscht" in _log(tmp)


@pytest.mark.parametrize("seite", ["tausch"], indirect=True)
def test_variante_c_erstpruefung_faengt_vertauschte_felder_ohne_baseline(seite, monkeypatch):
    """Kaltstart: Es gibt noch keine Baseline. Die erste Seite wird deshalb einmal gegen einen
    Screenshot geprüft, bevor sie zur Baseline wird, sonst würde der Fehler zur 'Normalität'."""
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _fake_claude(monkeypatch, wahr, TAUSCH)
    _lauf(vc, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_c.csv")
    assert _spalte(gelesen, "firma") == _spalte(wahr, "firma")
    assert "Erstprüfung" in _log(tmp)


@pytest.mark.parametrize("seite", ["neu"], indirect=True)
def test_variante_c_lehnt_falschen_vorschlag_ab(seite, monkeypatch):
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    # trifft auch die Werbung -> 13 statt 12 -> muss abgelehnt werden
    _fake_claude(monkeypatch, wahr, {**NEU, "stelle": "article.karte"})
    _lauf(vc, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_c.csv")
    assert len(gelesen) == 120                                     # trotzdem vollständig (per Screenshot)
    assert json.loads((tmp / "selektoren.json").read_text())["stelle"] == "article.stelle"   # nicht überschrieben
    assert "NICHT übernommen" in _log(tmp)


@pytest.mark.parametrize("seite", ["neu"], indirect=True)
def test_variante_c_lehnt_vorschlag_mit_falschem_inhalt_ab(seite, monkeypatch):
    """Richtige Karten, aber Firma und Titel falsch herum: gleiche Anzahl, falscher Inhalt."""
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _fake_claude(monkeypatch, wahr, {**NEU, "firma": ".titel", "titel": ".firma"})
    _lauf(vc, monkeypatch, tmp, url)
    assert json.loads((tmp / "selektoren.json").read_text())["stelle"] == "article.stelle"
    assert "NICHT übernommen" in _log(tmp)
    assert _spalte(_lies(tmp / "ergebnis_c.csv"), "firma") == _spalte(wahr, "firma")


@pytest.mark.parametrize("seite", ["neu"], indirect=True)
def test_variante_c_verwirft_ungueltigen_selektor_ohne_absturz(seite, monkeypatch):
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _fake_claude(monkeypatch, wahr, {**NEU, "stelle": "article[[["})
    _lauf(vc, monkeypatch, tmp, url)
    assert len(_lies(tmp / "ergebnis_c.csv")) == 120
    assert json.loads((tmp / "selektoren.json").read_text())["stelle"] == "article.stelle"


# --------------------------------------------------------------------------- Variante C: Schaden vermeiden
@pytest.mark.parametrize("seite", ["leer"], indirect=True)
def test_variante_c_repariert_eine_gueltige_leere_seite_nicht(seite, monkeypatch):
    url, wahr, tmp = seite
    assert wahr == []
    _c_einrichten(monkeypatch, tmp)
    zaehler = _fake_claude(monkeypatch, wahr, NEU)
    _lauf(vc, monkeypatch, tmp, url)
    assert _lies(tmp / "ergebnis_c.csv") == []
    assert zaehler == {"bild": 1, "claude": 0}              # eine billige Zählung, keine Reparatur
    assert "leere Seite" in _log(tmp)
    assert json.loads((tmp / "selektoren.json").read_text()) == ALT and not list(tmp.glob("selektoren_alt_*"))


def test_variante_c_gesunder_lauf_kostet_nichts_und_zaehler_wird_zurueckgesetzt(seite, monkeypatch):
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _baseline_schreiben(tmp, wahr)
    zaehler = _fake_claude(monkeypatch, wahr, NEU)
    vc.kosten.update(ein=999, aus=999, usd=5.0)             # Rest eines früheren Laufs im selben Prozess
    _lauf(vc, monkeypatch, tmp, url)
    assert len(_lies(tmp / "ergebnis_c.csv")) == 120
    assert zaehler == {"bild": 0, "claude": 0}
    assert "kosten_eur=0.0000" in (tmp / "messung_c.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("seite", ["neu"], indirect=True)
def test_variante_c_verliert_bei_api_ausfall_nur_die_betroffene_seite(seite, monkeypatch):
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    monkeypatch.setattr(vc, "MAX_REPARATUREN", 0)           # alle Seiten laufen über den Screenshot
    _fake_claude(monkeypatch, wahr, NEU, bild_fehler_seite=3)
    _lauf(vc, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_c.csv")
    assert len(gelesen) == 108 and "3" not in {z["seite"] for z in gelesen}
    assert "API-Fehler" in _log(tmp) and "Seite 3" in _log(tmp)


@pytest.mark.parametrize("seite", ["neu"], indirect=True)
def test_variante_c_verliert_keine_daten_wenn_claude_ausfaellt(seite, monkeypatch):
    url, wahr, tmp = seite
    _c_einrichten(monkeypatch, tmp)
    _fake_claude(monkeypatch, wahr, NEU, claude_fehler=True)
    _lauf(vc, monkeypatch, tmp, url)
    assert len(_lies(tmp / "ergebnis_c.csv")) == 120          # per Screenshot gelesen
    assert json.loads((tmp / "selektoren.json").read_text())["stelle"] == "article.stelle"
    assert "Claude nicht erreichbar" in _log(tmp)
