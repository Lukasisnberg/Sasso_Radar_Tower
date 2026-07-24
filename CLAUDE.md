# Sasso Radar Tower

Eigenständiges ADS-B-Flugradar für Raspberry Pi 4 mit rundem 4"-Touch-Display
(Waveshare 720×720 DSI LCD). Eigenständige Implementierung; eine Ausnahme:
das "detailed" Flugzeug-Icon-Set ist ein lizenziertes Drittanbieter-SVG-Set
(adsb-radar.com, Backlink-Pflicht erfüllt — siehe
`flugradar/assets/icons/aircraft/LICENSE.txt`). Die ursprünglich
eigengezeichneten Icon-Silhouetten existieren weiterhin als "simple"-Modus.

## Anforderungen

Vollständige Anforderungen: siehe `docs/ANFORDERUNGEN.md` — bei jeder neuen
Aufgabe zuerst dort den relevanten Abschnitt lesen.

## Aktueller Stand

Schritte 1–8 aus dem Bauauftrag (Abschnitt 13) sind abgeschlossen:

- Datenschicht (adsb.fi-Client, FR24, AirLabs, Tomorrow.io, RainViewer, Caching, Fallback)
- Geo-Projektion (Lat/Lon → Bildschirmkoordinaten)
- Pygame-Rendering (Sweep, Kompassrose, Entfernungsringe, Flugzeug-Darstellung)
- Rundmaskierung + 720×720-Zielauflösung
- Kartenkacheln (CARTO, OSM, Cache, Attribution)
- Web-Portal (Flask, Konfiguration, API-Keys, System-Steuerung)
- Weitere Screens (Detail, Tracking, Uhr/Wetter, About, Einstellungen)
- Systemintegration (systemd, Boot-Splash, install.sh, desktop/kiosk-Modi)
- Flugzeugtyp-Icon-System (Abschnitt 5.4a, siehe `docs/prompt-flugzeug-icons.md`):
  lizenziertes SVG-Set (`AIRCRAFT_ICON_SET=detailed`, Default) mit
  ICAO-Typcode- und ADS-B-Kategorie-Auflösung (`flugradar/display/icon_mapping.py`),
  plus die ursprünglichen eigengezeichneten Polygon-Silhouetten als
  `AIRCRAFT_ICON_SET=simple`-Alternative

165 Tests grün.

## Offene Punkte

- Live-Reload-Verifikation (Settings-Änderungen im Portal ohne App-Neustart)
- Foto-/Logo-Anreicherung (Abschnitt 5.4b): Planespotters-Integration mit Fotografen-Attribution
- Design-Sprache-Umsetzung (Abschnitt 15): Dieter-Rams-Prinzipien durchgängig anwenden
- Kein dediziertes Drohnen-/UAV-Icon im lizenzierten "detailed"-Set
  (ADS-B-Kategorie B6 fällt dort auf das generische Icon zurück; die
  `simple`-Silhouette deckt Drohnen weiterhin ab)

## Konventionen

- **Konfigurationspriorität**: Env-Variable > Portal-Settings (JSON) > Datei-Default
- **Nutzer wird zur Laufzeit ermittelt** — kein hartcodiertes `"pi"` im Code
- **Tests vor jedem Commit**: `python -m pytest -v`
- **Tech-Stack**: Python 3.11+, pygame (Display), Flask (Web-Portal), requests/httpx (APIs)
- **Projektstruktur**: `flugradar/` mit Untermodulen `config/`, `data_sources/`, `display/`, `maps/`, `web/`, `system/`, `tests/`
