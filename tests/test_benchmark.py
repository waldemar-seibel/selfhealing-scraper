"""Hält das Benchmark-Skript lauffähig: zwei Szenarien (gesund, Teilbruch) im simulierten Modus."""
import benchmark
import variante_b_screenshots as vb
import variante_c_kombi as vc


def _szenario(name):
    return next(s for s in benchmark.SZENARIEN if s["name"].startswith(name))


def test_benchmark_gesund_und_teilbruch_und_stellt_den_zustand_wieder_her():
    vorher = (vc.WARTE_MS, vc.SEL_DATEI, vc.claude_fragen, vb.bild_lesen, vb.api_key)

    gesund = benchmark.szenario_laufen(_szenario("gesund (Kontrolle)"))
    assert gesund["entscheidung_ok"] and not gesund["schaden"] and gesund["daten_ok"]
    assert (gesund["bild"], gesund["claude"]) == (0, 0)

    teil = benchmark.szenario_laufen(_szenario("Teilbruch"))
    assert teil["entscheidung_ok"] and teil["uebernommen"] and not teil["schaden"] and teil["daten_ok"]
    assert (teil["bild"], teil["claude"]) == (1, 1)

    assert (vc.WARTE_MS, vc.SEL_DATEI, vc.claude_fragen, vb.bild_lesen, vb.api_key) == vorher
    text = benchmark.tabelle([gesund, teil], echt=False, lesefehler=False, wiederholungen=1)
    assert "| Teilbruch: nur Ort umbenannt | reparieren | repariert | ok | nein | 480/480 |" in text
    assert "Richtige Entscheidungen: 2 von 2" in text


def test_benchmark_zaehlt_einen_uebernommenen_falschen_vorschlag_als_schaden(monkeypatch):
    """Wenn die Prüfregel versagt (hier: alles wird akzeptiert), muss der Benchmark das als Schaden melden."""
    monkeypatch.setattr(vc, "vorschlag_ok", lambda test, gegenprobe: True)
    ergebnis = benchmark.szenario_laufen(_szenario("Falscher Vorschlag: Werbung"))
    assert ergebnis["uebernommen"] and ergebnis["schaden"] and not ergebnis["entscheidung_ok"]
