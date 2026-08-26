"""Koppelt die gedruckte Anleitung (anleitung/) an den tatsächlichen
App-Code, damit ein neuer Menüpunkt oder eine geänderte Attributionsquelle
nicht unbemerkt am Buch vorbeigebaut wird.

Bewusst kein pygame.init()/Rendering hier -- geprüft wird nur, dass die im
Buch (anleitung/buch/anleitung.html) behaupteten Texte tatsächlich aus dem
Code stammen, per einfachem Substring-Abgleich. Gleiches Prinzip wie
test_design_tokens.py (Quelltext-Scan statt Ausführen).
"""

import ast
import pathlib

import pytest

ANLEITUNG_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "anleitung"
BUCH_HTML = ANLEITUNG_DIR / "buch" / "anleitung.html"
ABOUT_PY = pathlib.Path(__file__).resolve().parent.parent / "display" / "screens" / "about.py"

pytestmark = pytest.mark.skipif(
    not BUCH_HTML.exists(), reason="anleitung/buch/anleitung.html nicht vorhanden"
)


@pytest.fixture(scope="module")
def buch_text() -> str:
    return BUCH_HTML.read_text(encoding="utf-8")


class TestSzene:
    """anleitung.szene baut fehlerfrei und liefert einen Hauptflug mit
    vollständiger Route -- ohne das würde der Tracking-Screenshot (S. 11)
    ohne Fortschrittsbalken dastehen."""

    def test_baut_ohne_fehler(self):
        from anleitung import szene

        aircraft = szene.build_aircraft()
        assert len(aircraft) >= 10

    def test_hauptflug_hat_vollstaendige_route(self):
        from anleitung import szene

        flug = szene.build_tracked_flight()
        assert flug.callsign == "DLH420"
        assert None not in (flug.origin_lat, flug.origin_lon, flug.destination_lat, flug.destination_lon)

    def test_wetter_und_vorschau_bauen(self):
        from anleitung import szene

        assert szene.build_weather().temperature_c
        assert len(szene.build_forecast()) == 5

    def test_frozen_time_stellt_zeit_still(self):
        import time

        from anleitung import szene

        with szene.frozen_time():
            a = time.monotonic()
            b = time.monotonic()
        assert a == b


class TestMenuReferenz:
    """Jede Einstellung, die das Gerätemenü tatsächlich anbietet, muss im
    Buch auftauchen -- sonst hat ein späterer Menüpunkt keine Seite
    bekommen."""

    @classmethod
    @pytest.fixture(scope="class")
    def menu_screen(cls):
        # Kein pygame.init() nötig: MenuScreen()/._rows_for() bauen nur
        # _Row-Objekte (Dataclass + Lambdas), pygame.Rect() braucht keine
        # laufende SDL-Instanz. Fonts/Zeichnen fasst dieser Test nicht an.
        from flugradar.config import settings as settings_mod
        from flugradar.config.settings import AppSettings
        from flugradar.display.screens.menu import MenuScreen
        from flugradar.display.theme import CLASSIC_AMBER

        settings_mod.PORTAL_SETTINGS_FILE = pathlib.Path("/nonexistent/settings.json")
        settings = AppSettings()
        return MenuScreen(300, CLASSIC_AMBER, settings)

    def test_alle_wurzelbereiche_im_buch(self, menu_screen, buch_text):
        from flugradar.display.screens.menu import _ROOT_LABELS, _ROOT_ORDER

        assert len(_ROOT_ORDER) == 7
        for key in _ROOT_ORDER:
            label = _ROOT_LABELS[key]
            assert label in buch_text, f"Wurzelbereich {label!r} fehlt im Buch"

    def test_alle_zeilenbeschriftungen_im_buch(self, menu_screen, buch_text):
        from flugradar.display.screens.menu import _ROOT_ORDER

        fehlend = []
        for key in _ROOT_ORDER:
            for row in menu_screen._rows_for(key):
                if row.kind == "info":
                    continue  # Systeminfo-Zeilen (Version/IP/...) sind kein Einstellungspunkt
                if row.label not in buch_text:
                    fehlend.append(f"{key}.{row.label}")
        assert not fehlend, f"Menüzeilen fehlen im Buch: {fehlend}"


class TestNachweise:
    """Jede statische Attributionsquelle aus about.py (dem tatsächlichen
    Info-Bildschirm) muss auf der Nachweisseite des Buchs vorkommen."""

    @staticmethod
    def _quellnamen_aus_about() -> list[str]:
        """Extrahiert die Quellnamen aus den literalen Strings in
        AboutScreen.draw() (z. B. "Daten: adsb.fi (opendata)" -> "adsb.fi").
        Nutzt `ast` statt eines Imports, damit kein pygame/SDL laufen muss."""
        baum = ast.parse(ABOUT_PY.read_text(encoding="utf-8"))
        literale: list[str] = []
        for node in ast.walk(baum):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value:
                if ": " in node.value:
                    literale.append(node.value)

        namen: list[str] = []
        for text in literale:
            rest = text.split(": ", 1)[1]
            rest = rest.split(" (", 1)[0]  # "(opendata)"/"(CC BY-NC 4.0)" etc. abschneiden
            namen.extend(teil.strip() for teil in rest.split(" / "))
        return namen

    def test_extraktion_findet_bekannte_quellen(self):
        # Gegenprobe, dass die ast-Extraktion selbst nichts kaputt macht --
        # ohne das könnte der eigentliche Test unbemerkt an einer leeren
        # Liste vorbei "grün" durchlaufen.
        namen = self._quellnamen_aus_about()
        assert "adsb.fi" in namen
        assert "adsbdb.com" in namen
        assert len(namen) >= 6

    def test_alle_quellen_im_buch(self, buch_text):
        fehlend = [n for n in self._quellnamen_aus_about() if n not in buch_text]
        assert not fehlend, f"Datenquellen aus about.py fehlen im Buch: {fehlend}"


class TestSeitenplan:
    def test_genau_36_seiten(self, buch_text):
        assert buch_text.count('class="seite') == 36

    def test_wischkarte_platzhalter_vorhanden(self, buch_text):
        # build.py ersetzt das -- bleibt der Platzhalter stehen, wurde
        # build.py nicht (mehr) über diese Datei gelaufen.
        assert "{{WISCHKARTE_SVG}}" in buch_text
