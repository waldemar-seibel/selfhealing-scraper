"""Ende-zu-Ende-Tests mit echtem (unsichtbarem) Browser gegen die lokale Übungsseite.
Claude wird simuliert: kein API-Schlüssel nötig, keine Kosten, immer gleiches Ergebnis."""
import json
import re
import sys

import pytest

import variante_a_daten as va
import variante_b_screenshots as vb
import variante_c_kombi as vc


def _lauf(modul, monkeypatch, tmp_path, url, *extra):
    monkeypatch.setattr(modul, "HIER", tmp_path)
    monkeypatch.setattr(sys, "argv", ["x", "--unsichtbar", "--url", url, *extra])
    modul.main()


def _lies(pfad):
    import csv
    with open(pfad, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _fake_claude(monkeypatch, wahr, vorschlag):
    def bild(pfad, key):
        nr = int(re.search(r"seite-(\d+)", pfad.name).group(1))
        return [r for r in wahr if int(r["seite"]) == nr], 2000, 900

    monkeypatch.setattr(vb, "bild_lesen", bild)
    monkeypatch.setattr(vb, "api_key", lambda: "test")
    monkeypatch.setattr(vc, "claude_fragen", lambda prompt, key: json.dumps(vorschlag))


def test_variante_a_liest_alles_und_ueberspringt_werbung(seite, monkeypatch):
    url, wahr, tmp = seite
    monkeypatch.setattr(va, "PAUSE_SEKUNDEN", (0, 0))
    _lauf(va, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_a.csv")
    assert len(gelesen) == len(wahr) == 120
    assert not any("Lebenslauf" in z["titel"] for z in gelesen)


@pytest.mark.parametrize("seite", ["neu"], indirect=True)
def test_variante_c_repariert_sich_bei_neuem_design(seite, monkeypatch):
    url, wahr, tmp = seite
    monkeypatch.setattr(vc, "SEL_DATEI", tmp / "selektoren.json")
    monkeypatch.setattr(vc, "LOG", tmp / "log.txt")
    monkeypatch.setattr(vb, "BILDER", tmp / "bilder")
    _fake_claude(monkeypatch, wahr, {"stelle": "article.job", "firma": ".firma", "titel": ".titel",
                                     "ort": ".ort", "datum": ".datum", "weiter": "a.weiter"})
    _lauf(vc, monkeypatch, tmp, url)
    assert len(_lies(tmp / "ergebnis_c.csv")) == 120
    assert json.loads((tmp / "selektoren.json").read_text())["stelle"] == "article.job"
    assert "übernommen" in (tmp / "log.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("seite", ["neu"], indirect=True)
def test_variante_c_lehnt_falschen_vorschlag_ab(seite, monkeypatch):
    url, wahr, tmp = seite
    monkeypatch.setattr(vc, "SEL_DATEI", tmp / "selektoren.json")
    monkeypatch.setattr(vc, "LOG", tmp / "log.txt")
    monkeypatch.setattr(vb, "BILDER", tmp / "bilder")
    # trifft auch die Werbung -> 13 statt 12 -> muss abgelehnt werden
    _fake_claude(monkeypatch, wahr, {"stelle": "article.karte", "firma": ".firma", "titel": ".titel",
                                     "ort": ".ort", "datum": ".datum", "weiter": "a.weiter"})
    _lauf(vc, monkeypatch, tmp, url)
    gelesen = _lies(tmp / "ergebnis_c.csv")
    assert len(gelesen) == 120                                     # trotzdem vollständig (per Screenshot)
    assert json.loads((tmp / "selektoren.json").read_text())["stelle"] == "article.stelle"   # nicht überschrieben
    assert "NICHT übernommen" in (tmp / "log.txt").read_text(encoding="utf-8")
