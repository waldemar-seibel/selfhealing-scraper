"""Gemeinsame Test-Bausteine: Übungsseite in einem Temp-Ordner erzeugen und lokal ausliefern."""
import csv
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "uebungsseite"))

import erzeugen  # noqa: E402


def _seite_bauen(tmp_path: Path, design: str):
    erzeugen.HIER = tmp_path
    erzeugen.SITE = tmp_path / "site"
    erzeugen.main(design)
    with open(tmp_path / "wahrheit.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _server(verzeichnis: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(verzeichnis))
    handler.log_message = lambda *a, **k: None
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def seite(tmp_path, request):
    """Liefert (Start-URL, Wahrheit, Arbeitsordner). Design über @pytest.mark.parametrize('seite', ['neu'], indirect=True)."""
    design = getattr(request, "param", "alt")
    wahr = _seite_bauen(tmp_path, design)
    srv = _server(tmp_path / "site")
    yield f"http://127.0.0.1:{srv.server_address[1]}/seite-1.html", wahr, tmp_path
    srv.shutdown()
    srv.server_close()
