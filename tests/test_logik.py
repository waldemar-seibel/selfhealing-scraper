"""Schnelle Tests ohne Browser: Antwort-Parsing, Prüfregel, Vergleich."""
import vergleich
from variante_b_screenshots import antwort_parsen
from variante_c_kombi import vorschlag_ok


def test_antwort_parsen_mit_codeblock():
    text = 'Hier:\n```json\n[{"firma": "A GmbH", "titel": "Dreher", "ort": "Lage", "datum": "heute"}]\n```'
    assert antwort_parsen(text) == [{"firma": "A GmbH", "titel": "Dreher", "ort": "Lage", "datum": "heute"}]


def test_antwort_parsen_kaputt_gibt_leere_liste():
    assert antwort_parsen("Leider kann ich das nicht lesen") == []
    assert antwort_parsen('[{"firma": "A",') == []
    assert antwort_parsen("") == []


def test_vorschlag_ok_nur_bei_gleicher_anzahl():
    stellen = [{"firma": "A", "titel": "T"}] * 12
    assert vorschlag_ok(stellen, stellen)
    assert not vorschlag_ok(stellen + [{"firma": "Anzeige", "titel": "Werbung"}], stellen)   # Werbung mitgezählt
    assert not vorschlag_ok([], [])                                                       # findet nichts
    assert not vorschlag_ok([{"firma": "", "titel": "T"}] * 12, stellen)                  # Felder leer


def test_vergleich_vertauscht_gleiche_stellen_nicht(capsys):
    wahr = [{"seite": "1", "firma": "A", "titel": "Dreher", "ort": "Lage", "datum": "heute"},
            {"seite": "1", "firma": "A", "titel": "Dreher", "ort": "Verl", "datum": "vor 3 Tagen"}]
    gelesen = [dict(wahr[1]), dict(wahr[0])]   # umgekehrte Reihenfolge
    vergleich.bewerten("Test", gelesen, wahr, {})
    out = capsys.readouterr().out
    assert "Feld ort    richtig: 2/2" in out
    assert "Feld datum  richtig: 2/2" in out


# --------------------------------------------------------------------------- Hilfsfunktionen von C
import json  # noqa: E402

import variante_c_kombi as vc  # noqa: E402


def test_html_kuerzen_entfernt_skripte_und_ereignisse():
    html = ('<html><head><meta http-equiv="refresh" content="0;url=http://boese.example"><style>a{}</style></head>'
            '<body><script>alert(1)</script><iframe src="x">y</iframe>'
            '<main><a onclick="böse()" href="#">Hallo</a></main></body></html>')
    out = vc.html_kuerzen(html)
    for verboten in ("<script", "<style", "<iframe", "http-equiv", "onclick", "alert"):
        assert verboten not in out
    assert "Hallo" in out


def test_html_kuerzen_behaelt_main_und_navigation_bei_langen_seiten():
    html = ("<html><body><main>" + "<article>Stelle</article>" * 5000 + "</main>"
            '<nav><a class="weiter" href="seite-2.html">Weiter</a></nav></body></html>')
    out = vc.html_kuerzen(html, 20000)
    assert len(out) <= 20000
    assert "<article>Stelle</article>" in out
    assert 'class="weiter"' in out                 # ohne Navigation könnte Claude "weiter" nie vorschlagen


def test_vorschlag_bereinigen_laesst_nur_erlaubtes_durch():
    ok = vc.vorschlag_bereinigen({"stelle": " article.job ", "firma": ".f", "titel": ".t", "ort": None,
                                  "datum": ".d", "weiter": "a.weiter", "extra": "ignoriert"})
    assert ok == {"stelle": "article.job", "firma": ".f", "titel": ".t", "ort": "", "datum": ".d",
                  "weiter": "a.weiter"}
    assert vc.vorschlag_bereinigen({"firma": ".f"}) is None                     # ohne "stelle" unbrauchbar
    assert vc.vorschlag_bereinigen({"stelle": "x" * 201}) is None               # überlang
    assert vc.vorschlag_bereinigen({"stelle": ["a"]}) is None                   # kein Text
    assert vc.vorschlag_bereinigen("kein dict") is None


def test_selektoren_speichern_sichert_alte_fassung_atomar_und_begrenzt_sicherungen(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "SEL_DATEI", tmp_path / "selektoren.json")
    vc.SEL_DATEI.write_text(json.dumps({"stelle": "erste"}), encoding="utf-8")
    for i in range(8):
        vc.selektoren_speichern({"stelle": f"fassung-{i}"})
    sicherungen = sorted(tmp_path.glob("selektoren_alt_*.json"))
    assert len(sicherungen) == vc.MAX_SICHERUNGEN
    assert json.loads(vc.SEL_DATEI.read_text())["stelle"] == "fassung-7"
    assert json.loads(sicherungen[-1].read_text())["stelle"] == "fassung-6"     # jüngste Sicherung = Vorgänger
    assert not list(tmp_path.glob("*.tmp"))                                      # keine halben Dateien


def test_baseline_roundtrip_und_kaputte_datei(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "BASE_DATEI", tmp_path / "baseline.json")
    assert vc.baseline_laden() is None
    vc.baseline_speichern({"n": 1, "quoten": {"ort": 0.9}, "woerter": {}})
    assert vc.baseline_laden()["quoten"]["ort"] == 0.9
    vc.BASE_DATEI.write_text("{kaputt", encoding="utf-8")
    assert vc.baseline_laden() is None
