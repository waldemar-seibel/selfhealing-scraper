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
