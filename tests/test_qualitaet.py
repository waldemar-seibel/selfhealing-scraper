"""Schnelle Tests ohne Browser: Gesundheitscheck (Teilbrüche, vertauschte Felder) und inhaltlicher Abgleich."""
import qualitaet as q
from variante_c_kombi import vorschlag_ok


def seite(wahr, nr):
    return [{k: z[k] for k in q.FELDER} for z in wahr if int(z["seite"]) == nr]


def ohne(zeilen, feld):
    return [{**z, feld: ""} for z in zeilen]


def tausche(zeilen):
    return [{**z, "firma": z["titel"], "titel": z["firma"]} for z in zeilen]


# --------------------------------------------------------------------------- Gesundheitscheck
def test_gesunde_seite_ist_gesund_mit_und_ohne_baseline(wahr_daten):
    base = q.baseline_neu(seite(wahr_daten, 1))
    for nr in range(1, 11):
        assert q.extraktion_gesund(seite(wahr_daten, nr), base) == (True, [])
        assert q.extraktion_gesund(seite(wahr_daten, nr), None) == (True, [])


def test_teilbruch_ort_leer_wird_erkannt(wahr_daten):
    """Der Fall aus der Auswertung: Karten werden gefunden, aber der Ort fehlt überall."""
    base = q.baseline_neu(seite(wahr_daten, 1))
    gesund, probleme = q.extraktion_gesund(ohne(seite(wahr_daten, 2), "ort"), base)
    assert not gesund
    assert any(p.startswith("ort") for p in probleme)


def test_teilbruch_ohne_baseline_ist_nicht_erkennbar(wahr_daten):
    """Ehrliche Grenze: ohne Vergleichswert ist ein leerer Ort nicht von 'gibt es nie' zu unterscheiden."""
    assert q.extraktion_gesund(ohne(seite(wahr_daten, 2), "ort"), None)[0]


def test_einzelner_fehlender_ort_ist_kein_fehler(wahr_daten):
    base = q.baseline_neu(seite(wahr_daten, 1))
    zeilen = seite(wahr_daten, 2)
    zeilen[0]["ort"] = ""
    zeilen[1]["ort"] = ""
    assert q.extraktion_gesund(zeilen, base)[0]


def test_vertauschte_felder_werden_erkannt(wahr_daten):
    base = q.baseline_neu(seite(wahr_daten, 1))
    for nr in (1, 2, 7):
        gesund, probleme = q.extraktion_gesund(tausche(seite(wahr_daten, nr)), base)
        assert not gesund, nr
        assert any("vertauscht" in p for p in probleme)


def test_leer_und_pflichtfelder_und_identische_werte(wahr_daten):
    assert q.extraktion_gesund([], None) == (False, ["keine Stellen gefunden"])
    assert not q.extraktion_gesund(ohne(seite(wahr_daten, 1), "firma"), None)[0]
    gleich = [{**z, "firma": z["titel"]} for z in seite(wahr_daten, 1)]
    assert not q.extraktion_gesund(gleich, None)[0]


def test_baseline_waechst_ueber_mehrere_seiten(wahr_daten):
    base = q.baseline_neu(seite(wahr_daten, 1))
    for nr in range(2, 6):
        base = q.baseline_erweitern(base, seite(wahr_daten, nr))
    assert base["n"] == 5
    assert len(base["woerter"]["firma"]) > len(q.baseline_neu(seite(wahr_daten, 1))["woerter"]["firma"])
    assert q.baseline_erweitern(None, seite(wahr_daten, 1))["n"] == 1


# --------------------------------------------------------------------------- DOM gegen Screenshot
def test_vergleich_toleriert_lesefehler(wahr_daten):
    dom = seite(wahr_daten, 3)
    bild = [dict(z) for z in dom]
    mit_ort = next(z for z in bild if z["ort"])
    mit_ort["ort"] = mit_ort["ort"][:-1] + "x"                        # Lesefehler im Ort ("Lagx")
    bild[1]["firma"] = bild[1]["firma"] + "."                         # Zeichensetzung
    assert mit_ort["ort"] != next(z for z in dom if z["ort"])["ort"]
    assert vorschlag_ok(dom, bild)


def test_zwoelf_anzeigen_statt_zwoelf_stellen_werden_abgelehnt(wahr_daten):
    """Lücke aus der Auswertung: gleiche Anzahl, aber die falschen Elemente."""
    echt = seite(wahr_daten, 1)
    anzeigen = [{"firma": "Anzeige", "titel": f"Jetzt Lebenslauf-Check gratis! {i}", "ort": "", "datum": ""}
                for i in range(len(echt))]
    assert len(anzeigen) == len(echt)
    assert not vorschlag_ok(anzeigen, echt)


def test_vertauschte_felder_im_vorschlag_werden_abgelehnt(wahr_daten):
    echt = seite(wahr_daten, 1)
    assert not vorschlag_ok(tausche(echt), echt)


def test_falscher_ort_im_vorschlag_wird_abgelehnt(wahr_daten):
    """Der Teilbruch-Vorschlag, der den Ort nicht trifft, darf nicht übernommen werden."""
    echt = seite(wahr_daten, 1)
    assert not vorschlag_ok(ohne(echt, "ort"), echt)


def test_fehlende_zeile_im_screenshot_wird_nie_zu_falscher_persistierung(wahr_daten):
    """Liest das Bild eine Zeile zu wenig, wird der (richtige) Vorschlag vorsichtshalber abgelehnt.
    Das kostet höchstens eine Seite Screenshot-Daten, aber nie falsche Selektoren."""
    echt = seite(wahr_daten, 1)
    assert not vorschlag_ok(echt, echt[:-1])
