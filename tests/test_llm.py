"""Tests für den API-Baustein: Wiederholung bei Aussetzern, endgültige Fehler, Kosten. Kein Netz nötig."""
import pytest
import requests

import llm


class Antwort:
    def __init__(self, status, daten=None, header=None, text=""):
        self.status_code, self._daten, self.headers, self.text = status, daten or {}, header or {}, text

    def json(self):
        return self._daten


@pytest.fixture
def api(monkeypatch):
    """Ersetzt requests.post durch eine Liste vorbereiteter Antworten; Pausen werden nicht abgewartet."""
    aufrufe, pausen = [], []

    def einrichten(*antworten):
        folge = list(antworten)

        def post(*a, **k):
            aufrufe.append(1)
            nxt = folge.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt
        monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.setattr(llm.time, "sleep", pausen.append)
    return einrichten, aufrufe, pausen


def test_wiederholt_bei_429_5xx_und_netzfehler_und_klappt_dann(api):
    einrichten, aufrufe, pausen = api
    einrichten(Antwort(429, header={"retry-after": "7"}), requests.Timeout(), Antwort(503), Antwort(200, {"ok": 1}))
    assert llm.api_post({}, "k") == {"ok": 1}
    assert len(aufrufe) == 4
    assert pausen[0] == 7.0            # Retry-After wird beachtet


def test_endgueltige_fehler_werden_nicht_wiederholt(api):
    einrichten, aufrufe, _ = api
    einrichten(Antwort(401, text="invalid x-api-key"))
    with pytest.raises(llm.ApiFehler, match="401"):
        llm.api_post({}, "k")
    assert len(aufrufe) == 1


def test_begrenzte_versuche_dann_apifehler(api):
    einrichten, aufrufe, _ = api
    einrichten(*[Antwort(500)] * 4)
    with pytest.raises(llm.ApiFehler, match="nach 4 Versuchen"):
        llm.api_post({}, "k")
    assert len(aufrufe) == 4


def test_kosten_je_anfrage_mit_langer_stufe():
    k = llm.neue_kosten()
    llm.buche(k, 100_000, 0)           # genau an der Grenze: Normalpreis, 0,10 $ je Mio.
    assert k["usd"] == pytest.approx(0.01)
    llm.buche(k, 200_000, 0)           # über 100k Tokens: Fünffaches, also 0,50 $ je Mio.
    assert k["usd"] == pytest.approx(0.01 + 0.10)
    assert k["ein"] == 300_000
    assert llm.kosten_eur(k) == pytest.approx(k["usd"] * llm.USD_EUR)
