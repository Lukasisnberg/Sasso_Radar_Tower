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
  Anbieterwechsel die Sweep-Animation nicht blockiert.
- **Ausbaustufe 2, Schritt 3** (Abschnitt 15, siehe
  `docs/prompt-ausbaustufe-2.md`): Politur-Durchgang. Alle Screens
  (Radar, Detail, Uhr, About, Settings, Nav-Chrome) beziehen Schriftgrößen
  jetzt aus `TOKENS.font_title/value/standard/small`
  (`flugradar/display/theme.py`) statt aus verstreuten Literalen; einzige
  bewusste Ausnahme ist die große Uhrzeit auf dem Uhr-Screen, als
  dokumentiertes Vielfaches von `font_title`. Sich ändernde Zahlenwerte
  (Höhe, Geschwindigkeit, Entfernung, V/S, Uhrzeit) laufen durchgängig
  über die Mono-Schriftvariante für tabellarische Ziffern. Einheitliche
  Strichstärke über `TOKENS.line_stroke`; echte 1px-Haarlinien bleiben
  bewusst unskaliert. Neue Theme-Felder `surface`/`surface_accent` lösen
  hartcodierte Button-Farben in `nav.py` ab; der Rundbezel (`mask.py`)
  ist jetzt themenabhängig inkl. Live-Reload. Screen-Wechsel blenden über
  `TOKENS.duration_long_ms`/`ease_out_cubic` weich über
  (`flugradar/display/app.py` — `_compose_frame`); neu
  erscheinende/verschwindende Flugzeuge blenden über
  `TOKENS.duration_short_ms` sanft ein/aus
  (`RadarRenderer.draw_aircraft`). Inter/IBM Plex Sans werden per
  `install.sh` als apt-Pakete bereitgestellt (nicht vendored), mit
  sauberem Fallback auf DejaVu/Noto/System-Sans falls nicht verfügbar.
- **Aircraft-Gleiten** (nicht Teil von `docs/prompt-ausbaustufe-2.md`,
  separat vom Nutzer angefragt): Flugzeuge springen bei neuen ADS-B-Daten
  nicht mehr hart auf ihre neue Position, sondern gleiten dorthin
  (`RadarRenderer._update_motion`/`_interpolated_position` in
  `flugradar/display/renderer.py`). Interpoliert in Lat/Lon (nicht
  Bildschirmkoordinaten, bleibt so bei Zoom/Pan korrekt), Gleitdauer passt
  sich automatisch an das beobachtete Update-Intervall an (im Regelfall
  der ADS-B-Poll-Interval) statt eine feste Dauer zu raten. Ein
  unterbrochenes Gleiten (neue Daten treffen mitten in der Bewegung ein)
  setzt beim aktuell angezeigten Punkt fort statt neu zu springen.
- **Ausbaustufe 2, Schritt 4** (Abschnitt 15, siehe
  `docs/prompt-ausbaustufe-2.md`): Einstellungsmenü am Gerät
  (`flugradar/display/screens/menu.py` — `MenuScreen`), ersetzt das
  bisherige einfache `SettingsScreen` (gelöscht). Zwei Ebenen (Wurzel:
  Karte/Standort/Darstellung/Filter/Anzeige/Einheiten/System + je ein
  Untermenü), Swipe links öffnet, Swipe rechts/Zurück-Pfeil geht eine
  Ebene zurück. Vier Bedienelement-Typen (Umschalter, Einfachauswahl,
  Stufenregler, Aktion-mit-Rückfrage), Zeilen folgen der Kreissehne,
  Haarlinien-Trenner, Bogen-Scrollindikator. Standort auf exakt zwei feste
  Orte begrenzt (`flugradar/config/locations.py` — Gießen/Sassofortino,
  Koordinaten mit Quelle im Kommentar). Jede Änderung wird sofort atomar
  gespeichert (`AppSettings.save_portal_settings()`, jetzt
  temp-file+rename statt direktem Schreiben — betrifft auch den
  Web-Portal-Pfad); `AppSettings.mark_portal_synced()` verhindert, dass
  der eigene Schreibvorgang 2s später über den Live-Reload-Poll nochmal
  angewendet wird und dabei den Kartenkompositor unnötig neu aufbaut
  (sichtbares Flackern). Viele neue Einstellungen dazugekommen (Filter-
  Highlight-Toggles, Kompassrose/Sweep/Beschriftung an/aus,
  Software-Helligkeit + Nachtmodus-Zeitfenster, Kartenhelligkeit,
  Temperatur-/Uhrzeit-Einheit) — vollständige Übersichtstabelle
  (Einstellung → Env-Variable → Portal-Seite → Menüpfad) in
  `docs/ANFORDERUNGEN.md` Abschnitt 15. Alle auch im Web-Portal nachgezogen
  (`radar.html`/`display.html`), mit einer Ausnahme laut Spezifikation:
  API-Keys bleiben portal-only, da das Gerätemenü bewusst keine freien
  Textfelder erlaubt. Nebenbefund beim Bauen: die alten Portal-„Quick
  Presets" hatten andere Koordinaten für „Grosseto" als die jetzt
  recherchierten für Sassofortino — Portal zieht die Presets jetzt aus
  derselben `LOCATIONS`-Liste wie das Gerätemenü.
- **Ausbaustufe 2, Schritt 5** (Abschnitt 15, siehe
  `docs/prompt-ausbaustufe-2.md` — **letzter Schritt, Ausbaustufe 2 damit
  komplett**): Getrackter-Flug-Screen
  (`flugradar/display/screens/tracking.py` — `TrackedFlightScreen`).
  Auswahl über alle drei geforderten Wege (Detail-Footer „Track"/
  „Untrack", Portal-Callsign-Feld auf der Radar-Seite, automatisches Ende
  nach `tracking_timeout_s` ohne Empfang, Default 15 min). Nebenbefund
  beim Bauen: adsbdb liefert Flughafen-Koordinaten (`latitude`/
  `longitude`) bereits in der bestehenden Route-Antwort mit, wurden bisher
  nicht ausgelesen — jetzt ergänzt (`flugradar/data_sources/adsbdb.py`,
  vier neue `Aircraft`-Felder `origin_lat/lon`/`destination_lat/lon`),
  keine neue Datenquelle, keine zusätzlichen Calls. AirLabs liefert diese
  Koordinaten nicht, fällt bei aktivem AirLabs-Key auf „Route unbekannt"
  zurück. Fortschrittsberechnung als reine, pygame-freie Funktionen
  (`flugradar/data_sources/route_progress.py`): Fortschritt = (Gesamt−
  Rest)/Gesamt beidseitig auf 0–100% geklemmt, Restzeit `None` (nicht
  Division durch Null) bei Geschwindigkeit 0. Alle vier Sonderfälle aus
  5.3 im Screen behandelt, kein leerer/abstürzender Screen: keine Route
  bekannt, außer Reichweite (App hält den letzten Snapshot in
  `RadarApp._tracked_last_snapshot`, überlebt Screen-Wechsel), kein
  getrackter Flug, gelandet (erkennt `is_on_ground` False→True
  **innerhalb der Session**, damit ein am Gate gestarteter Trackingvorgang
  nicht sofort endet). Erreichbar per Swipe rechts vom Radar (vierte,
  bisher ungenutzte Swipe-Richtung); getrackter Flug auf dem Radar mit
  derselben Akzentfarbe hervorgehoben wie die Tap-Auswahl
  (`RadarRenderer._is_tracked`). **Nachbesserung nach Gerätetest**: die
  Hervorhebung war zu unauffällig (`aircraft_selected` ist nur ~25%
  heller als die normale Punktfarbe, auf einem kleinen bewegten Icon kaum
  wahrnehmbar) — getrackte Flugzeuge bekommen jetzt die volle Akzentfarbe
  (`theme.sweep_colour`) plus einen sichtbaren Ring
  (`RadarRenderer._draw_tracked_ring`); die Tap-Auswahl auf der
  Detailansicht behält den dezenteren Farbton. Außerdem fehlte das Foto
  im Tracking-Screen komplett (Import beim ersten Entwurf verworfen,
  nie wieder ergänzt) — jetzt nachgezogen, kleiner als im Detail-Screen.
- **Update-Funktion** (nicht Teil von `docs/prompt-ausbaustufe-2.md`,
  separat angefragt — Hintergrund: das Gerät steht im Wohnzimmer, soll
  Code-Änderungen per Knopfdruck aus GitHub übernehmen, ohne dass jemand
  vor Ort SSH braucht): neuer Menüpunkt „Update" in System (Gerät +
  Portal, `flugradar/system/update.py` — `trigger_update_async()`).
  Zieht `git fetch`/`git reset --hard origin/main`, installiert
  Abhängigkeiten neu (`pip install -e .[display,web]`), prüft dass der
  neue Code sauber importiert (`python -c "import ..."`), und startet erst
  dann beide systemd-Dienste neu. Bricht die Aktualisierung bei jedem
  Fehlschlag ab und setzt per `git reset --hard <alter-commit>` auf den
  vorherigen Stand zurück, **bevor** irgendein Dienst angefasst wird — ein
  fehlgeschlagenes Update darf das unbeaufsichtigte Gerät nie in einem
  kaputten Zustand zurücklassen. Verweigert außerdem bei lokal
  abweichendem Arbeitsverzeichnis (`git status --porcelain` nicht leer).
  Läuft als abgekoppelter Hintergrundprozess (`start_new_session=True`),
  da der letzte Schritt genau den Dienst neu startet, der die Anfrage
  ausgelöst hat — Ergebnis landet in
  `~/.local/share/flugradar/update.log` (im Portal auf der System-Seite
  als letzte Zeile angezeigt). **Voraussetzung**: das Installationsverzeichnis
  auf dem Pi (`~/sasso-radar-tower`) muss ein echtes Git-Repo sein (zeigt
  auf denselben GitHub-Remote), nicht nur eine rsync-Kopie wie bisher —
  einmalig manuell umgestellt, danach läuft jedes weitere Update
  eigenständig darüber. Bereits einmal live dogfooded: den Route-Zeilen-Fix
  (nächster Punkt) tatsächlich über den neuen Update-Button ausgerollt statt
  manuell zu deployen.
- **Detail-Screen: Start/Ziel nicht mehr erzwungen zweizeilig** (separat
  angefragt): `DetailScreen` maß den Umbruch bisher nicht — Start und Ziel
  standen immer auf zwei Zeilen, selbst wenn "City (CODE)  →  City (CODE)"
  locker auf eine gepasst hätte. Prüft jetzt die tatsächliche Sehnenbreite
  an der Zeile (`DetailScreen._draw_route`, dieselbe Fit-Logik wie
  `draw_center_text`) und bricht nur bei echtem Platzmangel auf zwei Zeilen
  um. `_build_rows` dafür in `_build_header_rows`/`_build_detail_rows`
  aufgeteilt, da die Passform erst beim tatsächlichen Zeichnen (wenn die
  y-Position feststeht) bekannt ist.
- **adsbdb-Anreicherung: alte "unbekannt"-Antworten laufen ab** (separat
  angefragt, Auslöser: viele Flugzeuge ohne Start/Ziel, z. B. `CFG081` —
  live gegen adsbdb geprüft, die Route ist dort schlicht nicht hinterlegt,
  kein Bug). Echter Bug dabei gefunden: `AdsbdbEnricher` cachte eine
  "kenne ich nicht"-Antwort für die gesamte Laufzeit der Session, obwohl
  adsbdb (community-gepflegt) die Route zwischenzeitlich ergänzt haben
  könnte — nie erneut angefragt. Jetzt Zeitstempel pro Cache-Eintrag
  (`AdsbdbEnricher._results`, `_needs_lookup()`), unbekannte Routen werden
  nach `_UNKNOWN_RETRY_S` (30 Min) erneut versucht; ein einmal gefundener
  Callsign/Route-Treffer bleibt weiterhin dauerhaft gecacht (kein Grund,
  den erneut abzufragen). `adsbdb_enrich_nearest`-Default zusätzlich von
  10 auf 20 angehoben, damit bei vielen gleichzeitig sichtbaren
  Flugzeugen weniger davon einen Poll-Zyklus auf ihre erste Anfrage warten
  müssen. AirLabs als vollständigere (aber kostenpflichtige) Alternative
  bewusst nicht eingerichtet — Nutzer hat keinen Key.
- **Tomorrow.io-Key aus dem Portal wurde nie übernommen + neuer
  Wetter-Screen** (separat angefragt). Root Cause: `AppSettings._apply_data()`
  (liest `settings.json`, sowohl beim Start als auch nach jedem Portal-Save)
  hatte für `tomorrow_api_key` (und ebenso `fr24_api_key`/`airlabs_api_key`)
  schlicht keinen Fall — nur `openaip_api_key` war verdrahtet. Der Key wurde
  also korrekt in `settings.json` geschrieben, aber nie zurück in die
  laufende Instanz übernommen, auch nicht nach einem Neustart. Jetzt
  ergänzt (`flugradar/config/settings.py`). Zusätzlich baute sowohl die
  Pygame-App als auch das Web-Portal ihren `WeatherClient` bisher genau
  einmal beim Start — ein nachträglich im Portal gespeicherter Key hätte
  also weiterhin einen Dienst-Neustart gebraucht. Für die Pygame-App jetzt
  über `_apply_live_settings()` gelöst (Client wird bei jeder erkannten
  Settings-Änderung neu gebaut, `check_portal_reload()` erkennt eine
  reine `tomorrow_api_key`-Änderung jetzt auch als Änderung); fürs Portal
  über eine pro-Request neu geprüfte `_get_weather_client()`-Closure statt
  eines einmal gebauten Objekts (`flugradar/web/app.py`). Neuer
  Wetter-Screen am Gerät (`flugradar/display/screens/weather.py` —
  `WeatherScreen`): nächste 3 Tage, je eine Spalte mit Tag, Min/Max-Temp
  und einem handgezeichneten Wettersymbol (`flugradar/display/
  weather_icons.py` — Sonne/Wolke/Nebel/Regen/Schnee/Gewitter aus
  Pygame-Primitiven, kein Icon-Set nötig, gleiches Prinzip wie Kompassrose/
  Sweep). Tomorrow.io liefert dafür einen neuen Forecast-Endpunkt
  (`WeatherClient.get_forecast()`, eigener 30-Min-Cache getrennt vom
  Live-Wetter-Cache). Erreichbar per Swipe rechts vom Uhr-Screen (bisher
  ungenutzte Richtung dort), zurück per Swipe links/runter oder den
  Radar-Footer-Button. Web-Portal-Wetterseite bekam dieselbe 3-Tage-Tabelle
  dazu.

- **Performance-/Speicher-Durchgang für Dauerbetrieb auf dem Pi 4B**
  (separat angefragt, Hintergrund: das Gerät soll unbeaufsichtigt
  durchlaufen, ohne dass Speicher oder Caches im Lauf von Wochen/Monaten
  volllaufen). Sechs konkrete Fundstellen behoben, keine davon akut
  kritisch, aber alle relevant für "läuft monatelang":
  - `get_font()` (`flugradar/display/fonts.py`) baute bei jedem Aufruf ein
    neues `pygame.font.Font`-Objekt neu auf, statt es wiederzuverwenden —
    mehrere Zeichenpfade (`nav.py` Breadcrumb/Footer-Buttons, `app.py`
    Karten-Attribution) rufen das aber bei **jedem Frame** auf, nicht nur
    einmal beim Screen-Aufbau wie die meisten anderen Stellen. Jetzt ein
    nach `(family, size, bold)` gecachtes `Font`-Objekt statt 30×/Sekunde
    neu zu parsen. Nebenbefund beim Bauen: ein prozessweiter Cache
    überlebt einen `pygame.quit()`/`pygame.font.init()`-Zyklus nicht (das
    alte `Font`-Objekt wird ungültig, ein erneuter Zugriff crasht hart mit
    Segfault statt einer fangbaren Python-Exception) — betrifft nur die
    Testsuite (viele Testdateien machen je einen eigenen
    init/quit-Zyklus im selben Prozess), nicht den Produktivbetrieb (dort
    läuft `pygame.quit()` genau einmal, beim endgültigen Shutdown). Gelöst
    über `fonts.reset_cache()` plus eine neue, testsuiteweite
    `flugradar/tests/conftest.py` mit einer autouse-Fixture, die den Cache
    nach jedem einzelnen Test zurücksetzt.
  - `DetailScreen`/`TrackedFlightScreen` (`flugradar/display/screens/
    detail.py`, `tracking.py`): `load_photo_surface()` wurde bei jedem
    Frame neu aufgerufen, solange der Screen offen war — JPEG-Dekodierung
    + Skalierung + Rundmaskierung komplett neu, 30×/Sekunde, obwohl sich
    das Foto zwischen Frames praktisch nie ändert. Jetzt pro Screen ein
    `(path, Surface)`-Cache-Eintrag, nur neu dekodiert wenn sich der
    Foto-Pfad tatsächlich ändert (anderes Flugzeug ausgewählt, oder Foto
    trifft neu ein).
  - `AdsbdbClient._aircraft_cache`/`_route_cache`
    (`flugradar/data_sources/adsbdb.py`): reine TTL-Frische-Prüfung, aber
    nie eine tatsächliche Löschung — ein Eintrag blieb für die gesamte
    Prozesslaufzeit im RAM, auch nachdem er längst als "stale" galt. Bei
    monatelangem Betrieb in der Einflugschneise sammeln sich so beliebig
    viele Flugzeuge/Callsigns im Speicher an — das widerspricht auch der
    im Modul-Docstring festgehaltenen Lizenzauflage ("no local database of
    routes built up over time"), die zwar RAM-only meint, aber ein nur
    wachsender RAM-Cache ist im Kern dasselbe, nur nicht auf Platte. Neuer
    `_evict_oldest()`-Helper (Alter-zuerst-raus, Obergrenze
    `_MAX_CACHE_ENTRIES=3000`), von `AdsbdbEnricher._results`
    (`enrichment.py`) mitgenutzt, das denselben Fehler eine Ebene höher
    hatte.
  - `aircraft_photo.py`: die Foto-Cache-Größenbegrenzung (`FLUGRADAR_
    PHOTO_CACHE_MAX_MB`, aus einem früheren Durchgang) wird nur bei
    tatsächlich heruntergeladenen Fotos angestoßen — ein "kein Foto
    gefunden"-Eintrag (`miss`) schreibt keine Datei, löst also nie eine
    Bereinigung aus und blieb bislang für immer im Index. Neue, nach Alter
    filternde `_prune_stale_misses()` (180 Tage, höchstens einmal täglich
    geprüft statt bei jedem Aufruf), angestoßen aus dem normalen
    `request_photo()`/`request_adsbdb_photo()`-Pfad statt über einen
    eigenen Timer.
  - `TileCache` (`flugradar/maps/tiles.py`) hatte — anders als der
    Foto-Cache — überhaupt keine Größenbegrenzung: Kartenkacheln für jeden
    je angesehenen Zoomlevel/Anbieter/Ort sammelten sich unbegrenzt auf
    der Platte. Jetzt dieselbe Alter-zuerst-raus-Begrenzung wie beim
    Foto-Cache (`FLUGRADAR_TILE_CACHE_MAX_MB`, Default 300 MB), geprüft
    einmal pro tatsächlichem Kartenneuaufbau (`fetch_region()`), nicht pro
    Kachel oder Frame.
  - Nicht angefasst, bewusst: der SVG-Icon-Render-Cache in
    `aircraft_icons.py` ist bereits durch einen festen, kleinen
    Schlüsselraum begrenzt (Icon-Set × Größe × Farbe × 5°-Winkel-Bucket);
    der Kartenkompositor kann bei sehr schnell aufeinanderfolgenden
    Zoom-Gesten kurzzeitig mehrere Rebuild-Threads gleichzeitig anstoßen
    (kein Leck, nur ein seltener, nutzerausgelöster Nebeneffekt) — beides
    kein tatsächliches Wachstumsproblem, daher nicht verändert.
- **Wetterscreen nach Mockup** (separat angefragt, `docs/prompt-
  wetterscreen.md` + `docs/weather-screen-mockup.svg`, in 4 Schritten
  umgesetzt wie im Auftrag vorgegeben, nach jedem Schritt Tests +
  Commit + Rückmeldung):
  - **Schritt 1** (Layoutgerüst): `WeatherScreen` (`flugradar/display/
    screens/weather.py`) komplett neu aufgebaut — Kopf (Ort + Wochentag/
    Uhrzeit), aktuelles Wetter (Icon + große Temperatur + Zustand), drei
    Kernwerte (Wind/Gefühlt/Regen), Haarlinie, gebogene 5-Tage-Vorhersage,
    Screen-Indikator. Ersetzt die bisherige 3-Tage-Spalten-Ansicht.
    Positionen als Bruchteile von `scaling.visible_radius()` aus dem
    Mockup abgelesen statt fester Pixel; Schriftgrößen/Farben aus
    theme.py-Tokens statt Mockup-Hexwerten; UI-Text Englisch wie der Rest
    der App. Neu: `render_tracked_text()` (draw_helpers.py, Letter-
    Spacing für die Versal-Labels), `location_display_name()`
    (config/locations.py), `WeatherData.wind_speed_str()` (folgt
    distance_unit statt eigener Windeinheit-Einstellung). **Nachbesserung
    nach Gerätetest**: "Mostly Clear" überlappte die "21°"-Temperatur, und
    die Vorhersagereihe geriet in den Fußzeilenbereich — Ursache war, dass
    vertikale Positionen als unabhängige feste Bruchteile aus dem
    Mockup-SVG übernommen wurden (SVG-`<text>`-y ist eine Grundlinie,
    pygame positioniert von der Boxoberkante; bei der 3x größeren
    Hero-Temperatur driftete das spürbar auseinander). Umgestellt auf
    sequenzielle, an der tatsächlich gemessenen Höhe des vorherigen Blocks
    orientierte Positionierung (gleiches Prinzip wie clock.py/detail.py),
    dazu Hero-Schriftgröße und Abstände gestrafft, mit echten
    Pixel-Messungen statt Schätzung verifiziert.
  - **Schritt 2** (Icon-Set): **Weather Icons von Erik Flowers** (SIL OFL
    1.1, Lizenz live gegen das GitHub-README geprüft) unter
    `flugradar/assets/icons/weather/` abgelegt (35 SVGs, LICENSE.txt mit
    vollständigem Lizenztext). `weather_icons.py` von handgezeichneten
    Pygame-Primitiven auf echten SVG-Loader mit Cache umgestellt (gleiches
    Prinzip wie `aircraft_icons.py`). Vollständige Tomorrow.io-Code→Icon-
    Tabelle inkl. Tag-/Nacht-Variante, generischer Fallback ("na"-Icon).
    Nur das aktuelle Icon bekommt die Theme-Akzentfarbe, Vorhersage-Icons
    bleiben neutral. Attribution an den vier etablierten Stellen ergänzt.
  - **Schritt 3** (Tomorrow.io-Anbindung): `WeatherData` um
    `temperature_apparent_c`/`precipitation_probability_pct` erweitert.
    `WeatherClient.is_stale`/`weather_age_s()` neu — `get_weather()` gab
    bei einem fehlgeschlagenen Abruf schon vorher den letzten bekannten
    Wert zurück, diese beiden Properties lassen den Screen erkennen, ob
    eine Anzeige frisch oder nachgereicht ist. `WeatherScreen.set_data()`
    ersetzt die Schritt-1-Beispielwerte durch echte, von `RadarApp`
    injizierte Daten. Alle drei Pflichtfälle umgesetzt: kein Key (Hinweis
    statt Wetterblöcke, Kopfzeile bleibt stehen), Abruffehler/offline
    (letzte Werte + dezentes "· updated 13m ago" direkt in der
    Kopfzeilen-Unterzeile statt einer eigenen Reihe), fehlende
    Einzelwerte (jeweiliger Wert ausgelassen, Layout bleibt stabil).
    Tag/Nacht fürs aktuelle Icon bleibt bei der Uhrzeit-Heuristik aus
    Schritt 2 — Tomorrow.io liefert im abgefragten Feldsatz keine
    Sonnenauf-/-untergangszeit, und der Auftrag verlangt nur Tag-/Nacht-
    Varianten im Icon-*Set*, keine echte Astronomie.
  - **Schritt 4** (Feinschliff): Hero-Temperatur nutzte noch keine
    tabellarischen Ziffern (fehlendes `mono=True`, einzige Ausnahme von
    sonst überall konsequent tabellarischen Zahlenwerten) — behoben,
    außerdem aus Konsistenzgründen in `_ensure_fonts()` gecacht statt bei
    jedem `draw()`-Aufruf neu gebaut (durch den Font-Cache aus dem
    Performance-Durchgang zwar unkritisch, aber stilistisch inkonsistent
    mit jedem anderen Font auf diesem Screen). Geometrische Regressionstests
    ergänzt, die die Kopfzeile und die äußeren Vorhersage-Spalten gegen
    `scaling.circle_half_width_at_row()` prüfen (Abschnitt 15: "nichts vom
    Kreisrand abgeschnitten") — bei der Vorhersagereihe am unteren Ende
    geprüft, wo die Sehne am schmalsten ist, nicht am Zeilenanfang. Übrige
    Abschnitt-15-Punkte (nur Akzentfarbe fürs aktuelle Icon, keine
    Schatten/Verläufe, Haarlinie mit `TOKENS.hairline_alpha`, einheitliche
    Übergangsdauer/Easing über den bestehenden `_compose_frame()`-
    Mechanismus) waren bereits aus den vorherigen Schritten korrekt.

- **Web-Portal-Redesign** (nicht Teil von `docs/prompt-ausbaustufe-2.md`,
  separat angefragt anhand von `docs/prompt-portal-design.md`, in 5
  Schritten wie im Auftrag vorgegeben umgesetzt): reiner Gestaltungs-
  Durchgang übers Flask-Portal (`flugradar/web/`), keine Änderung an
  Routen/Formularfeldnamen/Speicherlogik.
  - **Schritt 1**: CSS-Custom-Properties in `style.css` an `theme.py`s
    `CLASSIC_AMBER`-Hexwerten ausgerichtet, Inter lokal per `@font-face`
    (kein CDN), Grundraster (`.page-header`/`.section`/`.nav-list`)
    exemplarisch aufs Dashboard angewendet. Alte `.card`-Klassen bleiben
    vorerst bestehen, lösen aber schon die neuen Token auf, damit
    unmigrierte Seiten sofort korrekt aussehen. Neue
    `flugradar/tests/test_web_design.py` bindet die Farbwerte testbar an
    `theme.py`.
  - **Schritt 2**: übrige sechs Seiten auf dasselbe `.page-header`/
    `.section`-Raster gezogen, dabei `.card`/`.home-grid`/`.home-link`
    als jetzt toten Code entfernt.
  - **Schritt 3**: Eingabefelder/Auswahllisten von gefülltem Kasten auf
    Haarlinien-Unterstreichung umgestellt, Checkboxen zu schlichten
    flachen Toggle-Switches, Regler von der dicken Browser-Leiste auf
    eine dünne Linie mit Akzent-Punkt. Dabei einen echten Bug gefunden:
    die geteilte `width:100%`-Regel zog auch Checkboxen auf volle
    Zeilenbreite, wodurch das Label auf eine zweite Zeile umbrach.
  - **Schritt 4**: Speicherbestätigung von gerahmtem Banner auf eine
    ruhige, selbst ausblendende Textzeile umgestellt; API-Key-Felder
    zeigen jetzt „Key set"/„Not set"; Restart/Shutdown bekamen einen
    zuvor komplett fehlenden `confirm()`-Bestätigungsschritt plus beide
    die Warnfarbe (der Auftrag nennt explizit beide als destruktiv).
  - **Schritt 5** (Geräte-Abgleich): sollte ursprünglich nur Farben/
    Begriffe zwischen Portal und Gerätemenü abgleichen — dabei aber
    festgestellt, dass das Gerätemenü (`menu.py`) bereits komplett
    Deutsch ist, während Portal und alle anderen Gerätescreens Englisch
    sind. Kein Wording-, sondern ein Sprachunterschied. Auf Nachfrage
    beim Nutzer: die gesamte Anwendung soll Deutsch werden — das ist die
    unten dokumentierte Lokalisierung, kein einfacher Begriffsabgleich
    mehr.
- **Vollständige deutsche Lokalisierung** (ausgelöst durch obigen Fund,
  separat vom Nutzer bestätigt: „Bitte die gesamte Anwendung in Deutscher
  Sprache", danach „und so weiter und alles fertig machen" — alle
  Phasen ohne weitere Rückfrage durchgezogen). Direkte Hardcodierung
  der deutschen Texte wie in `menu.py` bereits etabliert, kein i18n-
  Framework (genau eine Zielsprache). In fünf Phasen umgesetzt:
  - **Phase 1**: alle acht Web-Portal-Templates, `app.py`s drei
    Statustexte, die `confirm()`-Dialogtexte. Dabei über den Plan hinaus
    erweitert: `flugradar/system/update.py` hat mehrere
    `UpdateResult`-Statusmeldungen (nicht nur „already up to date"), die
    alle in dieselbe Portal-Logzeile einfließen — nur eine zu übersetzen
    hätte das Feature halb-deutsch gelassen, also alle mitübersetzt.
  - **Phase 2**: `_WEATHER_CODES`-Tabelle (`data_sources/weather.py`,
    einzige Quelle für Wetter-Zustandstexte, wirkt sich automatisch auf
    Uhr-/Wetter-Screen und Radar-Statuszeile aus) sowie `nav.py`s
    Fußzeilen-Label-Dict (bisher fiel `track`/`untrack`/`stop` auf den
    englischen `kind.upper()`-Fallback zurück, da dafür schlicht kein
    Eintrag existierte). Per Headless-Pygame-Renderbild
    (`SDL_VIDEODRIVER=dummy`) geprüft: die zunächst vorgesehene
    Bezeichnung „VERFOLGEN" wird im gängigen 3-Button-Footer auf
    „VERFOLG…" abgeschnitten — durch das kürzere „FOLGEN" ersetzt, das
    überall sauber passt.
  - **Phase 3**: `route_progress.py`s `vertical_rate_label()` liefert
    jetzt „Steigflug"/„Sinkflug"/„Horizontalflug" statt „climbing"/
    „descending"/„level" — `tracking.py`s Vergleichsstelle (steuert, ob
    das Steig-/Sink-Tag in der Telemetriezeile erscheint) im selben
    Commit mitgeändert, da direkt gekoppelt. `tracking.py`s vier
    Sonderfall-Meldungen sowie `detail.py`s „Kein Verkehr"/„Von"/„Nach"/
    „NOTFALL" übersetzt; Luftfahrt-Kürzel (HDG, V/S, Squawk, kt, fpm, ft)
    bewusst unverändert (Nutzerentscheidung: international gebräuchlich).
  - **Phase 4**: Kompassbuchstaben in `renderer.py` von N/E/S/W auf
    N/O/S/W (deutsche Konvention: O für Ost), Radar-Statuszeile
    übersetzt. Neue `flugradar/display/de_dates.py` mit Wochentags-/
    Monatsnamen-Lookup-Tabellen — bewusst *kein* `locale.setlocale()`,
    da nirgends im Code aufgerufen und fragil (bräuchte `de_DE.UTF-8`
    auf dem Pi generiert); stattdessen dieselbe Art fest hinterlegter
    Tabelle wie `_WEATHER_CODES`. `clock.py` nutzt sie jetzt für Datum
    und lässt `%p` (AM/PM) im 12h-Modus komplett weg (im Deutschen
    unüblich). `weather.py`s Spaltenbeschriftungen („GEFÜHLT WIE" u. a.)
    per Headless-Renderbild auf Breite geprüft, bevor final übernommen.
    `about.py`s Attributionszeilen übersetzt (nur das Label-Wort vor dem
    Doppelpunkt, Domains/Lizenznamen unverändert).
  - **Phase 5** (Abschlussabgleich): systematischer Vergleich jedes
    Gerätemenü-Labels gegen die entsprechende Portal-Bezeichnung ergab
    mehrere echte Diskrepanzen für dieselbe Einstellung — "Basiskarte"
    vs. "Anbieter" (`map_provider`), "Einheit" vs. "Distanz"
    (`distance_unit`), "Notfall-Codes hervorheben" vs. "Notfall
    hervorheben", "Militärverkehr hervorheben" vs. "Militär hervorheben",
    "Sweep-Animation" vs. "Sweep", "Flugzeug-Beschriftung" vs.
    "Beschriftung", sowie "Luftfahrt-Overlay"/"Luftfahrt-Karten-Overlay"
    (About-Seite, API-Keys-Seite) vs. "openAIP-Luftraum" (Gerätemenü,
    Radar-Seite) — auf die jeweils im Gerätemenü etablierte Bezeichnung
    vereinheitlicht. Außerdem ein stehengebliebenes "VERFOLGEN" in
    `radar.html`s Hilfetext gefunden (Rest von vor der FOLGEN-Entscheidung
    in Phase 2) und korrigiert.

584 Tests grün.

## Offene Punkte

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
