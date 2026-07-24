# Sasso Radar Tower

Eigenständiges ADS-B-Flugradar für Raspberry Pi 4 mit rundem 4"-Touch-Display
(Waveshare 720×720 DSI LCD). Eigenständige Implementierung; Ausnahmen:
das "detailed" Flugzeug-Icon-Set ist ein lizenziertes Drittanbieter-SVG-Set
(adsb-radar.com, Backlink-Pflicht erfüllt — siehe
`flugradar/assets/icons/aircraft/LICENSE.txt`), und die Anreicherungsdaten
(Route/Airline/Halter/Foto) kommen optional von adsbdb.com bzw. AirLabs.
Die ursprünglich eigengezeichneten Icon-Silhouetten existieren weiterhin
als "simple"-Modus. **adsb.fi bleibt in jedem Fall die alleinige,
unveränderte Positionsquelle.**

**Wichtiger Hinweis zu FR24 vs. AirLabs**: `docs/ANFORDERUNGEN.md` (Abschnitt
5.1) beschreibt FR24 als die kostenpflichtige Anreicherungsquelle. Es gibt
im Code aber **keinen FR24-Client** — diese Rolle übernimmt tatsächlich
**AirLabs** (`flugradar/data_sources/enrichment.py`). `fr24_api_key` ist
nur ein ungenutzter Einstellungs-Slot. Bei Änderungen an der
Quellenpriorität ("kostenpflichtig vs. kostenlos") ist AirLabs gemeint,
nicht FR24.

**Kartenlogik-Historie**: `docs/ANFORDERUNGEN.md` Abschnitt 5.2/5.3 hatte
ursprünglich ein RainViewer-Regenradar-Overlay und eine Auswahl zwischen
mehreren Kartenanbietern (CARTO/OSM/FAA VFR) vorgesehen, aber bis
Ausbaustufe 2 existierte im Code keins von beidem (`app.py` verwendete
fest `provider_key="carto_dark"`). Das openAIP-Overlay (Teil B) war
deshalb die erste Overlay-Implementierung überhaupt, nicht "analog zu
RainViewer" wie ursprünglich angenommen. **Beide Lücken sind inzwischen
geschlossen** (Ausbaustufe 2, Schritt 2, siehe unten): RainViewer-Overlay
existiert jetzt (`flugradar/maps/rainviewer.py`), Kartenanbieter ist im
Portal live wählbar. FAA-VFR-Charts bleiben weiterhin ungebaut (siehe
Offene Punkte).

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
- Foto-/Logo-Anreicherung (Abschnitt 5.4b): Planespotters-Integration mit
  Fotografen-Attribution (`flugradar/data_sources/aircraft_photo.py`) ist
  fertig; adsbdb/airport-data.com als zweiter Fallback (nur bei explizit
  aktiviertem `AIRCRAFT_PHOTOS_ENABLED`, generische Quellenangabe statt
  Fotografen-Name) ist dazugekommen. Gemeinsamer Foto-Cache jetzt
  größenbegrenzt (`FLUGRADAR_PHOTO_CACHE_MAX_MB`, Default 200 MB)
- adsbdb-Anreicherung (Abschnitt 5.1/5.5, siehe
  `docs/prompt-adsbdb-openaip.md`, Teil A): kostenlose Route-/Airline-/
  Halter-Anreicherung ohne Key (`flugradar/data_sources/adsbdb.py`,
  `flugradar/data_sources/enrichment.py` — `AdsbdbEnricher`,
  `FlightEnrichment`), Priorität AirLabs > adsbdb > keine, nebenläufiger
  gedrosselter Hintergrund-Worker + Vorrang für die offene Detailansicht,
  Routendaten ausschließlich im RAM (Lizenzauflage)
- openAIP-Luftraum-Overlay (Abschnitt 5.3/16, siehe
  `docs/prompt-adsbdb-openaip.md`, Teil B): transparentes PNG-Tile-Overlay
  über der bestehenden CARTO/OSM-Karte (`flugradar/maps/tiles.py` —
  `PROVIDERS["openaip"]`, `flugradar/maps/compositor.py` —
  `MapCompositor.overlay_tiles`), nur aktiv wenn `openaip_api_key`
  hinterlegt UND `openaip_overlay_enabled` an ist. Lizenz CC BY-NC 4.0
  (nicht-kommerziell). Kachel-Cache läuft über den bestehenden
  `TileCache`-Mechanismus, eigener `"openaip"`-Unterordner, keine
  Vermischung mit CARTO/OSM.
- Doku-Bereinigung: `LICENSE` (MIT) ergänzt, README.md komplett
  überarbeitet (Web-Portal-Sektion, Pi-Deployment-Sektion, korrigierte
  Projektstruktur), `.env.example` um alle seither hinzugekommenen
  Variablen ergänzt, `docs/prompt-adsbdb-openaip (1).md` in den sauberen
  Dateinamen umbenannt.
- **Ausbaustufe 2, Schritt 1** (Abschnitt 15, siehe
  `docs/prompt-ausbaustufe-2.md`): Themes von sechs auf zwei reduziert
  (`amber`/`mono`, `flugradar/display/theme.py`), zentrale
  `DesignTokens`/`TOKENS` (Abstandsraster, 4 Schriftgrößen, Linienstärke,
  2 Animationsdauern, 1 Easing-Kurve) angelegt. `resolve_theme()` fängt
  alte/entfernte Theme-Namen ab (Fallback `amber`, kein Fehler).
- **Ausbaustufe 2, Schritt 2** (Abschnitt 5.3, siehe
  `docs/prompt-ausbaustufe-2.md`): Kartenanbieter (`map_provider`:
  carto_dark/carto_light/osm/none) live im Portal wählbar
  (`flugradar/web/templates/radar.html`, Bereich „Karte"). Neu gebaut:
  RainViewer-Regenradar-Overlay von Grund auf
  (`flugradar/maps/rainviewer.py`, kein Key nötig, Kachel-Cache pro
  Radar-Frame mit automatischer Bereinigung des Vorgänger-Frames beim
  Wechsel). `MapCompositor` unterstützt jetzt mehrere gleichzeitig aktive
  Overlays (`overlay_tiles: list[TileManager]`) statt nur eines, sowie
  optional gar keine Basiskarte (`tiles: Optional[TileManager]`).
  Kartenaufbau läuft jetzt in einem Hintergrund-Thread (`render()` zeigt
  weiter das letzte fertige Bild, bis der Rebuild fertig ist), damit ein
  Anbieterwechsel die Sweep-Animation nicht blockiert. **Wichtig: nur
  Schritt 1+2 von 5 sind umgesetzt** — der Auftrag verlangt explizit,
  nach jedem Schritt zu testen/committen und erst nach Rückmeldung
  weiterzumachen, nicht alle fünf am Stück.

266 Tests grün.

## Offene Punkte

- **Ausbaustufe 2, Schritte 3–5** (siehe `docs/prompt-ausbaustufe-2.md`):
  Politur-Durchgang nach Abschnitt 15 (Tokens aus Schritt 1 tatsächlich in
  allen Screens verwenden), Einstellungsmenü am Gerät (Swipe links),
  Getrackter-Flug-Screen. Reihenfolge ist bewusst so vom Auftrag
  vorgegeben.
- FAA VFR Sectional Charts (Abschnitt 5.3) weiterhin nicht gebaut — kein
  Provider im Code, keine Portal-Option.
- Live-Reload-Verifikation (Settings-Änderungen im Portal ohne App-Neustart)
- Kein dediziertes Drohnen-/UAV-Icon im lizenzierten "detailed"-Set
  (ADS-B-Kategorie B6 fällt dort auf das generische Icon zurück; die
  `simple`-Silhouette deckt Drohnen weiterhin ab)

## Konventionen

- **Konfigurationspriorität**: Env-Variable > Portal-Settings (JSON) > Datei-Default
- **Nutzer wird zur Laufzeit ermittelt** — kein hartcodiertes `"pi"` im Code
- **Tests vor jedem Commit**: `python -m pytest -v`
- **Tech-Stack**: Python 3.11+, pygame (Display), Flask (Web-Portal), requests/httpx (APIs)
- **Projektstruktur**: `flugradar/` mit Untermodulen `config/`, `data_sources/`, `display/`, `maps/`, `web/`, `system/`, `tests/`
