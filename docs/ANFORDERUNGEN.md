# Bauauftrag: Eigenständiges ADS-B-Flugradar für Raspberry Pi 4 mit rundem Touch-Display

## Kontext für Claude Code

Baue mit mir von Grund auf ein eigenständiges Python-Projekt: einen Live-Flug- und
Schiffs-Radar für einen Raspberry Pi 4 mit rundem 4"-Touch-Display (Waveshare
4inch DSI LCD (C), 720×720, kapazitiv, 10-Punkt-Touch). Es soll **komplett eigener
Code** sein — keine Übernahme von Quelltext aus bestehenden Projekten. Die
Funktionsliste, Datenquellen und das grobe UX-Konzept unten sind als **Anforderung**
zu verstehen, nicht als Vorlage zum Abschreiben. Bitte in eigenständiger Architektur
und eigenem Stil umsetzen.

Ich werde während der Entwicklung per SSH auf dem Ziel-Pi testen. Zum Testen ohne
das Display (noch nicht geliefert) läuft die App vorerst per HDMI auf einem Monitor
und/oder über Raspberry Pi Connect Screen Sharing (Wayland/labwc-Desktop-Session).

---

## 1. Zielsetzung

Ein always-on Gerät, das auf einem runden Bildschirm ein animiertes Radar mit
Live-Flugverkehr um einen festen Standort zeigt, per Touch bedienbar ist, und über
ein lokales Web-Portal (im selben WLAN, kein Internet-Zugriff nötig) konfiguriert
werden kann, ohne dass man dafür SSH braucht.

## 2. Zielhardware

- Raspberry Pi 4 Model B (2/4/8 GB), 64-bit Raspberry Pi OS mit Desktop
- Waveshare 4" DSI LCD (C), rund, 720×720 Pixel, kapazitiver Touch, DSI + I2C
- Für die aktuelle Entwicklungsphase: Test über HDMI-Monitor bzw. Pi Connect
  Screen Sharing (Wayland/labwc-Session mit Xwayland), da das Rundpanel noch
  nicht angeschlossen ist
- Später produktiv: DSI-Panel, `dtoverlay=vc4-kms-dsi-waveshare-panel` in der
  Boot-Config, feste Auflösung 720×720

## 3. Grundkonzept

- Radarschirm zeigt Live-Flugzeuge um einen konfigurierbaren Heimatstandort
  (Lat/Lon), mit rotierendem Sweep, Kompassrose, Entfernungsring-Beschriftung
- Tap auf ein Flugzeug öffnet eine Detailansicht (Airline, Route, Höhe,
  Geschwindigkeit, Kurs)
- Zusätzliche Screens: Uhr mit aktuellem Wetter, mehrtägige Vorhersage,
  Tracking-Ansicht für einen ausgewählten Flug (Fortschrittsbalken,
  ETA, Restdistanz), Einstellungen (Helligkeit, Zeitfenster für Nachtmodus,
  Farbthema), About-Screen (Version, Netzwerkstatus, Portal-URL)
- Alle Bedienung per Touch-Gesten: Tap, Swipe zwischen Screens, Pinch-Zoom auf
  dem Radar; für die Entwicklungsphase ohne Touch-Panel müssen Maus-Events
  (Klick = Tap, Ziehen = Swipe) als Ersatz funktionieren
- Ein lokales Web-Portal (Flask, erreichbar per `http://<hostname>.local`)
  erlaubt Konfiguration ohne SSH: Standort, Zoombereich, Farbthema, API-Keys,
  Update-Funktion, Systemsteuerung (Reboot/Shutdown)

## 4. Architekturübersicht

Vier lose gekoppelte Schichten, die unabhängig entwickelt und getestet werden
können sollen:

1. **Datenschicht** — Clients für externe APIs, mit Caching und Fallback-Logik
2. **Renderschicht** — pygame-Vollbildanwendung, zeichnet auf das (virtuelle)
   Rundpanel, verarbeitet Touch-/Maus-Events
3. **Konfigurationsschicht** — Environment-Datei + lokale JSON-Settings-Datei,
   mit klarer Prioritätsreihenfolge
4. **Web-/Portalschicht** — schlankes Flask-Backend für Fernkonfiguration

Dazu kommt die **Systemintegration**: systemd-Service, Boot-Splash, Autologin,
Update-Mechanismus.

Bitte die Schichten als eigene Python-Packages/Module trennen, damit z. B. die
Datenschicht auch ohne laufendes Display per CLI getestet werden kann.

## 5. Datenquellen & Schnittstellen

### 5.1 Live-Flugpositionen

- **adsb.fi** — kostenlose öffentliche REST-API für ADS-B-Live-Positionen,
  kein eigener Empfänger/Dongle nötig. Soll die **Standard-Datenquelle** sein,
  die ohne jeden bezahlten Key funktioniert.
- **FlightRadar24 (FR24) API** — optional, erfordert ein kostenpflichtiges
  Abo. Der `fr24_api_key`-Einstellungsslot existiert (Portal, Env), es gibt
  aber **keinen echten FR24-Client** im Code — diese Rolle (Airline/Route/
  angereicherte Flugdetails) übernimmt in der tatsächlichen Umsetzung
  **AirLabs** (`flugradar/data_sources/enrichment.py`, `EnrichmentClient`).
  Wer hier tatsächlich Vorrang hat, ist also AirLabs, nicht FR24 — bitte bei
  zukünftigen Änderungen an dieser Priorität von AirLabs als der
  "kostenpflichtigen, optionalen" Quelle ausgehen, nicht von FR24.
- **AirLabs** — optional (Key im Portal), liefert Airline/Route/
  Flugnummer. Hat Vorrang, wenn ein Key hinterlegt ist.
- **adsbdb.com** (siehe `docs/prompt-adsbdb-openaip.md`, Teil A) — kostenlose
  Anreicherung ohne Key: Flugzeugstammdaten (Typ, Halter, Registrierung,
  Foto-URL), Route (Airline, Start-/Zielflughafen) für ein von adsb.fi
  bereits gemeldetes Hex/Callsign. **Reine Ergänzungsschicht, niemals
  Positionsquelle** — adsb.fi bleibt exklusiv und unverändert die
  Positionsquelle. Priorität: AirLabs falls Key vorhanden, sonst adsbdb
  (Standard), sonst keine Anreicherung. Läuft nebenläufig (eigener
  Hintergrund-Worker-Thread, gedrosselt auf einen Request nach dem
  anderen) mit Vorrang für das gerade in der Detailansicht geöffnete
  Flugzeug. Routendaten ausschließlich im Arbeitsspeicher mit TTL
  gecacht, nie auf Platte (Lizenzauflage, siehe Abschnitt 16).

### 5.2 Wetter

- **Tomorrow.io** — aktuelle Temperatur (Uhr-Screen) und mehrtägige
  Vorhersage. Erfordert einen kostenlosen/kostenpflichtigen API-Key.
- **RainViewer** — Regenradar-Kachel-Overlay auf der Karte, kein eigener Key
  nötig (kostenlose Weather-Maps-API, für persönliche/edukative Nutzung
  gemäß deren Nutzungsbedingungen — bitte deren aktuelle ToS und
  Attributionspflichten selbst prüfen und einhalten).
  **Update (Ausbaustufe 2, Schritt 2)**: umgesetzt in
  `flugradar/maps/rainviewer.py`. Geprüft am 2026-07-24 direkt gegen
  `https://api.rainviewer.com/public/weather-maps.json` (kein Key,
  Attributionspflicht als Link auf rainviewer.com, "personal or
  educational use only" laut deren eigener API-Doku). Kachel-Basis-URL
  ändert sich mit jedem neuen Radar-Frame (~alle 5 Minuten) — der
  Kachel-Cache wird deshalb pro Frame geführt und beim Frame-Wechsel für
  den alten Frame automatisch geleert (`TileCache.clear_provider()`),
  sonst würden veraltete Regendaten unbegrenzt auf der SD-Karte
  liegen bleiben.

### 5.3 Kartenkacheln

Konfigurierbarer Kartenhintergrund mit mehreren Anbietern zur Auswahl:

- **CARTO** (Dark Matter / Positron, "no labels"-Varianten) als Standard
- **OpenStreetMap** Standard-Kacheln als Alternative
- **FAA VFR Sectional Charts** als optionale Zusatzkarte für US-Standorte
  (public domain)
- **openAIP** (siehe `docs/prompt-adsbdb-openaip.md`, Teil B, und Abschnitt
  16 für die vollständigen Lizenzdetails): transparentes Overlay
  (Lufträume, Flugplätze, Navaids) über der Basiskarte, kein eigenständiger
  Kartenhintergrund. Erfordert einen kostenlosen openAIP-Account samt
  API-Key (`OPENAIP_API_KEY`); ohne Key wird das Overlay gar nicht erst
  angeboten. Per Einstellung ein-/ausschaltbar
  (`openaip_overlay_enabled`), live-reload-fähig. CC BY-NC 4.0 — nur
  nicht-kommerzielle Nutzung.

Anforderungen an die Kartenlogik:
- Kachel-Download parallelisiert, mit lokalem Disk-Cache (Kacheln nicht bei
  jedem Start neu laden)
- Farbliche Nachbearbeitung der Kacheln, damit sie zum dunklen Radar-Theme
  passen (z. B. Kontrast/Helligkeit anpassen)
- **Attribution/Copyright-Hinweis der jeweiligen Kartenquelle im UI anzeigen**
  — das ist eine Nutzungsbedingung der kostenlosen Kartenanbieter (CARTO,
  OpenStreetMap) und sollte im Neubau standardmäßig respektiert werden,
  außer für einen konkreten Anbieter liegt eine eigene, gesonderte
  Genehmigung vor
- Konfigurierbar: Kartenhintergrund ganz abschaltbar (nur Radar ohne
  Kartenkacheln)

**Update — Ausbaustufe 2, Schritt 2** (siehe `docs/prompt-ausbaustufe-2.md`):
Basiskarten-Auswahl (`map_provider`: `carto_dark`/`carto_light`/`osm`/
`none`) ist jetzt live im Web-Portal einstellbar (Bereich Radar → Karte),
Env > Portal > Default, live-reload-fähig. openAIP- und
RainViewer-Overlay sind unabhängig voneinander und vom Basisanbieter
schaltbar und können gleichzeitig aktiv sein — `MapCompositor` unterstützt
dafür jetzt eine Liste von Overlays statt nur eines einzelnen
(`flugradar/maps/compositor.py`). FAA-VFR-Charts wurden **nicht** gebaut
(im Code weiterhin nicht vorhanden, siehe Abschnitt 16); die
Portal-Auswahl beschränkt sich auf die tatsächlich vorhandenen Anbieter.
Der Kartenaufbau läuft jetzt in einem Hintergrund-Thread: `render()`
zeigt beim Anbieterwechsel weiter das zuletzt fertige Bild, bis das neue
fertig ist, statt die Sweep-Animation zu blockieren.

### 5.4a Flugzeugtyp-Icon-System (Radar-Ansicht)

Damit man Flugzeuge auf einen Blick unterscheiden kann, statt nur ein
einziges generisches Symbol zu sehen, braucht es ein kleines Set
eigenständig gezeichneter Icons, eins pro Kategorie:

- **Linienjet, schmalrumpfig** (z. B. A320/737-Klasse) — Standard-Symbol,
  wird am häufigsten vorkommen
- **Linienjet, großraumig** (z. B. A350/777-Klasse) — etwas größere/breitere
  Variante desselben Grundmotivs
- **Turboprop/Regionalflugzeug**
- **Helikopter** — deutlich anderes Silhouette (Rotor statt Tragflächen)
- **Militär-/Kampfflugzeug** — spitzere, aggressivere Silhouette
- **Leichtflugzeug/General Aviation** (Cessna-Klasse u. ä.)
- **Segelflugzeug**
- **Drohne/UAV**
- **Generisch/unbekannt** — Fallback, falls die Kategorie nicht bestimmbar
  ist

**Ableitung der Kategorie aus den ADS-B-Daten**: adsb.fi liefert ein
`category`-Feld nach dem Mode-S-Emitter-Category-Schema (z. B. `A1`
Leichtflugzeug, `A2`/`A3` mittel/groß, `A5` schwer, `A7` Rotorcraft, `B1`
Segelflugzeug, `B4` UAV, u. a. — bitte anhand der öffentlichen ADS-B-
Spezifikation eine vollständige Zuordnungstabelle Kategorie-Code →
Icon-Variante bauen). Wo `category` fehlt, hilfsweise über das
Flugzeugtyp-Kürzel (`t`, z. B. `A20N`, `B738`, `C172`) auf eine grobe
Klasse schließen; wenn beides fehlt, das generische Fallback-Icon zeigen.

**Visuelle Anforderungen** (im Einklang mit Abschnitt 15,
Gestaltungsrichtlinien):
- Alle Icons in **derselben Linienstärke** und demselben Zeichenstil
  gezeichnet, wie eine zusammengehörige Icon-Familie — nicht wie
  zusammengewürfelte Symbole aus verschiedenen Quellen
- Silhouetten von oben gesehen (Top-Down), passend zur Radar-Perspektive
- Icon dreht sich mit dem tatsächlichen Steuerkurs (`track`), damit die
  Flugrichtung auf einen Blick erkennbar ist
- Farbe des Icons zeigt den Zustand: Normalfarbe laut Theme, abweichende
  Akzentfarbe für ausgewähltes/getracktes Flugzeug, Warnfarbe **nur** bei
  echtem Notfall-Squawk (7500/7600/7700) oder Militär-Hervorhebung, wenn
  aktiviert
- Icon-Größe leicht gestaffelt nach Kategorie (z. B. Großraumjet minimal
  größer als Leichtflugzeug), aber alle klar erkennbar auch bei kleiner
  Zoomstufe
- Direkt am Icon ein kompaktes Label mit Höhe (in 100ft, wie im
  Original üblich) und ggf. Geschwindigkeit, in der in Abschnitt 15
  festgelegten Typografie

**Wichtig**: Diese Icons sollen **komplett neu und eigenständig
gezeichnet** werden (z. B. als SVG-Pfade oder direkt in pygame als
Polygon-Koordinaten definiert) — keine Icons aus bestehenden Projekten,
Icon-Bibliotheken mit unklarer Lizenz oder Screenshots übernehmen.

**Update (siehe `docs/prompt-flugzeug-icons.md`)**: Auf expliziten
Auftrag hin wurde diese Vorgabe für das Icon-System bewusst
aufgeweicht. Der Radar zeigt standardmäßig (`AIRCRAFT_ICON_SET=detailed`)
jetzt ein lizenziertes, extern bezogenes SVG-Icon-Set (37 Icons,
adsb-radar.com, frei nutzbar mit Backlink-Pflicht — siehe
`flugradar/assets/icons/aircraft/LICENSE.txt` und `SOURCE.md`) statt
komplett eigengezeichneter Icons. Die ursprünglich eigenständig
gezeichneten Polygon-Silhouetten (alle neun oben genannten Kategorien,
inkl. Drohne/UAV) bleiben als zweite, per Einstellung wählbare
Render-Variante (`AIRCRAFT_ICON_SET=simple`) im Code erhalten
(`flugradar/display/aircraft_icons.py`) — u. a. als Fallback ganz ohne
externe Assets und für Performance-Vergleiche. Bekannte Lücke: Das
externe Set hat kein eigenes Drohnen-/UAV-Icon (ADS-B-Kategorie B6 fällt
auf das generische Icon zurück); die selbstgezeichnete `_DRONE_HALF`-
Silhouette im "simple"-Pfad deckt diesen Fall weiterhin ab.

### 5.4b Weitere Bilder & Fotos

- **Planespotters** — Flugzeugfotos zur Anreicherung der Detailansicht
  (kostenlos, nicht-kommerziell). Priorität: **Foto bevorzugt**; nur wenn kein
  brauchbares Foto gefunden wird, als Fallback ein **Airline-Logo** anzeigen
  (per Einstellung ein-/ausschaltbar, Default eher aus, da nicht jeder ein
  großes Logo mag)
- **Attribution pro Einzelbild**: nicht nur ein pauschaler "Quelle:
  Planespotters"-Hinweis, sondern nach Möglichkeit der Name des
  Fotografen/Künstlers aus den Metadaten der Quelle mit anzeigen (z. B.
  "© Max Mustermann"), da das die übliche Attributionspflicht solcher
  Foto-Communities ist
- **adsbdb (airport-data.com) als zweiter Fallback** — nur wenn Planespotters
  nichts liefert **und** `AIRCRAFT_PHOTOS_ENABLED` explizit aktiviert ist
  (Default **aus**, siehe unten). Grund: Die adsbdb-API liefert pro Foto
  **keine** Fotografen-/Urheberangabe, nur einen pauschalen
  „airport-data.com"-Hinweis in der Projekt-README — deshalb bewusst kein
  automatisches Default-an, bis das geklärt ist (jetzt geklärt: es bleibt
  bei der pauschalen Quellenangabe, nicht pro Bild)
- **Cache-Größenbegrenzung**: Der gemeinsame Foto-Cache-Ordner (Planespotters
  + adsbdb) wird auf eine konfigurierbare Obergrenze begrenzt
  (Default 200 MB, `FLUGRADAR_PHOTO_CACHE_MAX_MB`); älteste Bilder werden
  zuerst entfernt, wenn die Grenze überschritten wird
- **Qualitätsfilter bei automatischer Bildauswahl**: Ergebnisse aussortieren,
  die keine echten Flugzeugfotos sind — z. B. Cartoons, Clipart, SVG-Grafiken,
  Flottenlisten-Thumbnails, Infobox-Bilder. Eine automatisch gewählte
  Bildquelle liefert sonst gerne mal ein falsches/unpassendes Ergebnis
- **Schiffsfotos (optional, für den AIS/Marine-Modus)**: analog über
  **Wikimedia Commons**, mit derselben Attributionspflicht und demselben
  Prinzip beim Aussortieren unpassender Treffer (Münzen, Medaillen, Poster,
  Werbegrafiken, Cartoons, Clipart, SVGs)
- **aisstream.io** — kostenlose AIS-Schiffspositionen für einen optionalen
  Marine-Radar-Modus
- **Nominatim (OSM)** — Reverse-Geocoding im Portal, um aus Koordinaten
  einen Ortsnamen anzuzeigen

### 5.5 Caching-Vorgaben

- Live-Positionen: alle 1–3 Sekunden neu abfragen
- Angereicherte Flugdetails (Route/Airline): deutlich seltener cachen
  (Minuten), da diese sich pro Flug kaum ändern
- **adsbdb-Anreicherung** (siehe `docs/prompt-adsbdb-openaip.md`):
  Flugzeugstammdaten lange im RAM cachen (Stunden, ändern sich praktisch
  nie während eines Fluges), Route mittel (30–60 Minuten). Negativ-Cache
  (kürzere TTL) für „nicht gefunden", damit ein Hex/Callsign nicht bei
  jedem Zyklus erneut angefragt wird. **Routendaten ausschließlich im
  Arbeitsspeicher** — keine Persistenz auf Platte, keine eigene
  Routentabelle über die Zeit (Lizenzauflage der Routendaten, siehe
  Abschnitt 16). Abfragestrategie höflich gegenüber dem Dienst: nur die
  nächstgelegenen N Flugzeuge im Hintergrund (konfigurierbar,
  `ADSBDB_ENRICH_NEAREST`), gedrosselt auf einen Request nach dem anderen,
  mit Vorrang für das gerade angetippte/in der Detailansicht offene
  Flugzeug.
- Wetter: stündlich reicht
- Kartenkacheln: dauerhaft lokal cachen, nur bei fehlender Kachel neu laden

## 6. Bildschirme / UI-Funktionen im Detail

| Screen | Aufruf | Inhalt |
|---|---|---|
| Radar (Startbildschirm) | Boot / Home | Live-Flugzeuge mit typspezifischen Icons (Jet/Turboprop/Helikopter/Militär), Kartenhintergrund, rotierender Sweep, Kompassrose, Entfernungsring, Höhen-Tags |
| Flugdetail | Tap auf Flugzeug | Foto (Planespotters, mit Fotografen-Attribution) bevorzugt, sonst Airline-Logo als Fallback; Route, Flugzeugtyp, Höhe, Geschwindigkeit, Kurs; Wischen/Footer zum Durchblättern |
| Getrackter Flug | Auswahl im Portal, oder Swipe auf Radar | Fortschrittsbalken mit Flugzeug-Icon, ETA/verbleibende Distanz, vertikale Geschwindigkeit |
| Uhr + aktuelles Wetter | Swipe runter vom Radar | Uhrzeit, Datum, Temperatur, Wetterlage |
| Wettervorhersage | Swipe von der Uhr | Mehrtägige Vorhersage |
| Einstellungen (Uhr) | Swipe von der Uhr | Uhrformat und verwandte Optionen direkt am Gerät |
| About | Swipe hoch vom Radar | Versionsnummer, Netzwerkstatus, Portal-URL |
| Einstellungen (Anzeige) | Swipe von Radar | Helligkeit, Timeouts, Farbthema, Anzeigeoptionen |

Gesten, die unterstützt werden müssen:
- Tap auf Flugzeug → Detailansicht
- Tap auf Entfernungslabel → Zoom-Presets durchschalten
- Zwei-Finger-Pinch → Zoom-Bereich stufenlos anpassen
- Swipe zwischen den o. g. Screens
- Footer-Buttons auf Detail-/Tracking-/Settings-Screens (Vor/Zurück/Radar/Pin)
- Auto-Rückkehr zur Uhr, wenn längere Zeit kein Flugzeug sichtbar ist
  (konfigurierbar)
- Nachtmodus-Zeitfenster: Display dimmen, ausschalten, oder auf Uhr wechseln

Zusatzfunktionen, die sinnvoll sind:
- Alarm-/Hervorhebungsmodus: Militärflugzeuge, Notfall-Squawks (7700/7600/7500),
  eigene Watchlist optisch hervorheben, optional alles andere ausblenden
- Mindesthöhen-Filter, um z. B. Platzrunden-Verkehr auszublenden
- Distanzeinheiten umschaltbar (km / sm / nm)

## 7. Konfigurationssystem

- Eine zentrale `.env`-Datei als Grundkonfiguration (API-Keys, Heimat-Standort,
  Displayoptionen, Einheiten)
- Für den produktiven Systemd-Betrieb: Kopie/Verlinkung auf eine
  root-geschützte Datei (z. B. `/etc/<projektname>.env`, `chmod 600`), damit
  API-Keys nicht für jeden lokalen Nutzer lesbar sind
- Laufzeit-Einstellungen, die über das Web-Portal geändert werden (Standort,
  Zoom, Farbthema, getrackter Flug), in einer separaten lokalen JSON-Datei
  speichern, die Neustarts übersteht und **nicht** durch ein Code-Update
  überschrieben wird
- Klare Prioritätsreihenfolge dokumentieren: System-Env > Portal-Einstellung >
  Datei-Default
- **Live-Reload**: Die Display-App darf die Portal-Settings-Datei nicht nur
  einmal beim Start lesen, sondern muss laufend (z. B. alle 1–2 Sekunden per
  Zeitstempel-Check, nicht bei jedem Frame) prüfen, ob sich die Datei
  geändert hat, und betroffene Werte (Theme, Distanzeinheit, Heimatstandort,
  Radius, Mindesthöhe) ohne Neustart der App übernehmen. Ein Wert, der im
  Web-Portal gespeichert wird, muss sich im laufenden Radar-Fenster
  bemerkbar machen, ohne dass jemand den Prozess neu startet. Der Reload
  darf keinen sichtbaren Ruckler oder Reset der Sweep-Animation verursachen.
  Env-Variablen selbst müssen dabei nicht live neu eingelesen werden, da sie
  sich zur Laufzeit ohnehin normalerweise nicht ändern.

## 8. Web-Portal

Flask-App, im lokalen Netzwerk erreichbar, mit mindestens folgenden Bereichen:

- **Radar**: Standort (Lat/Lon), Zoombereich, Distanzeinheiten, Mindesthöhe,
  Farbthema, Kompassrose/Sweep an/aus
- **Anzeige & Screens**: Helligkeit, Timeouts, Auto-Rückkehr zur Uhr
- **Nachtmodus**: Zeitfenster, Verhalten (dimmen/aus/Uhr)
- **Wetter**: Einheiten (°C/°F)
- **Alarm/Watchlist**: Militär, Notfall-Squawk, eigene Liste, Ausblenden
  von nicht markiertem Verkehr
- **Tracking**: Callsign auswählen, Routensuche (Start+Ziel)
- **API-Keys**: FR24, Tomorrow.io, AirLabs — Speichern bzw. Speichern+Neustart
- **Updates**: Prüfen auf neue Version, Update anstoßen (bei dir: gegen dein
  **eigenes** Repo, nicht gegen ein fremdes)
- **System**: Neustart/Herunterfahren des Pi aus der Ferne
- Zusatzseiten: einfache Statistikseite (Flugzähler pro Tag), Karten/Logs für
  nächstes/entferntestes gesehenes Flugzeug

## 9. Systemintegration

- systemd-Service, der die pygame-App im Kontext der laufenden
  Desktop-Session startet (`DISPLAY`, `XAUTHORITY`/Wayland-Äquivalent
  korrekt setzen — bei Wayland/labwc auf Trixie ggf. andere Pfade als unter
  X11/Bookworm, bitte robust gegen beide Fälle bauen)
- **Zwei Betriebsmodi, umschaltbar per Konfiguration** (z. B.
  `DISPLAY_BACKEND=desktop|kiosk` in der Env-Datei):
  - **`desktop`** (aktueller Standard während der Entwicklung): App läuft
    über die laufende Autologin-Desktop-Session (X11/Xwayland unter
    Wayland/labwc), damit Fernzugriffs-/Screen-Sharing-Werkzeuge
    (z. B. Pi Connect) währenddessen weiter funktionieren
  - **`kiosk`** (für den späteren Produktivbetrieb am fest verbauten
    Rundpanel): App greift direkt über KMS/DRM auf das Display zu, ganz
    ohne laufende Desktop-Session — schlanker, aber inkompatibel mit
    Screen-Sharing-Werkzeugen, die eine Desktop-Session voraussetzen
  - Beide Modi dürfen sich nicht gegenseitig blockieren (KMS/DRM kann immer
    nur von einem Prozess gleichzeitig belegt werden) — die Umschaltung
    muss also eindeutig eines von beiden wählen, nie beide gleichzeitig
    versuchen
- **Robuster Start im `desktop`-Modus**: Der Service darf nicht davon
  ausgehen, dass die grafische Session beim Systemstart schon bereit ist.
  Vor dem eigentlichen App-Start soll aktiv auf das Vorhandensein der
  laufenden Session gewartet werden (z. B. Polling auf das X11-Socket unter
  `/tmp/.X11-unix/`, mit Timeout und klarer Fehlermeldung im Log, falls die
  Session nach angemessener Zeit nicht erscheint) — nicht nur über eine
  systemd-Zieleinheit, da rein User-Session-bezogene Targets
  (z. B. `graphical-session.target`) aus einem System-Service heraus unter
  Umständen nicht zuverlässig wirken
- Boot-Splash (Plymouth) und Desktop-Wallpaper passend zum eigenen
  Branding, austauschbar über eine einzelne Bilddatei
- Installations-Skript, das: System-Pakete installiert, eine
  Python-virtualenv anlegt, Assets herunterlädt (Fonts, Icons), die
  Laufzeit-Datenverzeichnisse anlegt, die Env-Datei einrichtet, den
  systemd-Service registriert und optional direkt startet
- Sudoers-Eintrag mit **minimalem, eng gefasstem** Rechteumfang, damit das
  Portal einen Update-Befehl ausführen kann, ohne dem Web-Prozess volle
  Root-Rechte zu geben

## 10. Nicht-funktionale Anforderungen

- Muss auf einem Pi 4 (2 GB RAM) flüssig laufen (Ziel: spürbar flüssige
  Sweep-Animation, keine sichtbaren Ruckler bei normaler Flugzeugdichte)
- Robust gegenüber Netzwerkausfällen: bei fehlendem Internet soll das UI
  nicht abstürzen, sondern zuletzt bekannte Daten weiter anzeigen bzw.
  einen klaren Offline-Hinweis zeigen
- Robust gegenüber fehlenden/ungültigen API-Keys: App muss mit reinem
  adsb.fi-Betrieb ohne jeden Key vollständig funktionsfähig sein
- Konfigurierbare Update-Intervalle pro Datenquelle, um API-Kontingente zu
  schonen

## 11. Vorgeschlagener Tech-Stack

- Python 3.11+
- **pygame** für das Rendering auf dem Display
- **Flask** für das Web-Portal
- **requests** oder **httpx** für API-Zugriffe
- Lokale Konfigurationsdateien als JSON (kein schwergewichtiges DB-System
  nötig für diesen Umfang)
- **pytest** für Tests der Datenschicht und Geo-Berechnungen (unabhängig
  vom Display testbar)

## 12. Vorschlag Projektstruktur

```
flugradar/
  config/            # Env-Handling, Settings-Datei, Prioritätslogik
  data_sources/       # adsb.fi, FR24, AirLabs, Tomorrow.io, RainViewer Clients
  maps/                # Kachel-Download, Cache, Farb-Nachbearbeitung
  display/             # pygame-App: screens/, gestures.py, theme.py
  web/                  # Flask-Portal: routes, templates, static
  system/                # systemd-Unit-Template, install-Skript, Boot-Splash-Assets
  tests/
  main.py               # Einstiegspunkt für die Display-App
```

## 13. Empfohlene Entwicklungsreihenfolge

1. **Datenschicht zuerst, ohne Display**: adsb.fi-Client, der Live-Positionen
   als CLI-Ausgabe zeigt. Erst hier Caching/Fallback-Logik sauber bauen und
   testen.
2. **Geo-Projektion**: Umrechnung Lat/Lon → Bildschirmkoordinaten relativ zum
   Heimatstandort, mit Unit-Tests, unabhängig vom Rendering.
3. **Pygame-Prototyp, eckig**: erst ein normales rechteckiges Fenster mit
   Radar-Darstellung, ohne Rundmaskierung — Fokus auf Sweep-Animation,
   Flugzeug-Icons, Klick-Handling (als Ersatz für Touch).
4. **Rundmaskierung + Zielauflösung**: Auf 720×720 umstellen, kreisförmig
   maskieren, für spätere Panel-Rotation vorbereiten (konfigurierbarer
   Rotationswinkel).
5. **Kartenkacheln integrieren**: erst CARTO, dann Cache, dann Farbstil,
   zuletzt Attribution-Overlay.
6. **Web-Portal**: Flask-Grundgerüst, dann Schritt für Schritt Einstellungen
   anbinden, die die Settings-JSON verändern, die die Display-App live
   ausliest.
7. **Weitere Screens** (Detail, Tracking, Uhr/Wetter, About, Settings) einzeln
   ergänzen.
8. **Systemintegration zuletzt**: systemd, Boot-Splash, Installations-Skript
   — erst wenn die App im Vordergrund manuell zuverlässig läuft.

## 14. Teststrategie

- Datenschicht: Unit-Tests mit gemockten API-Antworten (kein Live-Call in
  Tests)
- Geo-Berechnungen: Unit-Tests mit bekannten Koordinatenpaaren und erwarteten
  Pixelpositionen
- Rendering: manuelles Testen auf dem Pi (per HDMI/Screen-Sharing während der
  Entwicklung, später am echten Rundpanel)
- Config-Prioritätslogik: Unit-Tests für alle Kombinationen (nur Env, nur
  Portal-Settings, beides gesetzt)

## 15. Gestaltungsrichtlinien (Design-Sprache)

Das UI soll sich an den zehn Prinzipien guten Designs von Dieter Rams
orientieren — konkret auf dieses Radar-Display übersetzt:

**"Weniger, aber besser" / so wenig Design wie möglich**
- Jeder Ring, jede Linie, jeder Glow-Effekt muss eine echte Information
  codieren (Entfernung, Status, Warnung) — keine rein dekorativen Elemente
- Sekundäre Bedienelemente nur zeigen, wenn sie im aktuellen Kontext
  relevant sind, statt dauerhaft alles auf einmal anzuzeigen

**Ehrlichkeit**
- Farben und Hervorhebungen bilden reale Datenzustände ab (Höhe,
  Geschwindigkeit, Notfall-Squawk) — keine geschönten oder rein
  atmosphärischen Effekte, die Aktivität vortäuschen, wo keine ist

**Verständlichkeit / klare Hierarchie**
- Maximal 3–4 Schriftgrößen, konsistentes Grundlinienraster, großzügiger
  Weißraum (bzw. "Dunkelraum" bei dunklem Theme)
- **Eine** Akzentfarbe für primäre Hervorhebung, alles andere in
  gedämpften Grau-/Off-White-Tönen; Warnfarbe (Rot/Orange) ausschließlich
  für echte Alarme (Notfall-Squawk) reserviert, nicht für generische
  Betonung
- Zahlen (Höhe, Geschwindigkeit) in **tabellarischen Ziffern** darstellen,
  damit sie beim Aktualisieren nicht "wackeln"

**Konsistenz**
- Einheitliche Strichstärke bei Icons (z. B. durchgängig 2 px Outline,
  keine gemischten gefüllten/Outline-Stile außer bewusst fürs
  Flugzeug-Symbol selbst, das aus Lesbarkeitsgründen als Vollfläche
  dargestellt werden darf)
- Einheitliche Eckenradien, einheitliche Randabstände zum Kreisrand auf
  allen Screens
- Eine einzige Easing-Kurve und zwei Dauer-Klassen für Animationen (z. B.
  ~150 ms für Tap-Feedback, ~350–400 ms für Screen-Übergänge) — nicht pro
  Screen unterschiedlich "erfunden"

**Zeitlosigkeit statt Trend**
- Flaches Design, keine Glasmorphismus-Effekte, keine harten Drop-Shadows;
  stattdessen dünne Haarlinien (1 px, niedrige Deckkraft) zur Trennung von
  Flächen
- Farbpalette dezent und gedämpft statt neon-grell (auch beim
  "Radar-Grün" — ein ruhiges, leicht entsättigtes Grün/Petrol wirkt
  hochwertiger als reines Neongrün)

**Vorschlag für eine konkrete Farbpalette** (als Ausgangspunkt, nicht
bindend):
- Hintergrund: sehr dunkles Anthrazit, nicht reines Schwarz (z. B. `#0B0D0F`)
- Primärtext: warmes Off-White (z. B. `#EDEFF1`)
- Sekundärtext/Gitterlinien: gedämpftes Grau, reduzierte Deckkraft
- Ein Akzentton (z. B. gedämpftes Petrol/Teal oder warmes Gold) für aktive
  Zustände und Hervorhebung
- Warnfarbe ausschließlich für echte Alarmzustände, nirgendwo sonst
  verwendet

**Typografie**
- Eine klare, geometrische oder humanistische Sans-Serif-Schrift (z. B.
  Inter oder IBM Plex Sans — beide frei lizenziert und auf dem Pi gut
  darstellbar), keine Systemstandard-Schrift ohne bewusste Wahl
- Großbuchstaben-Label (z. B. Screen-Titel) mit leichtem Letter-Spacing,
  Fließtext/Werte ohne

**Bewegung**
- Sweep-Rotation mit konstanter Winkelgeschwindigkeit, keine ruckartigen
  Sprünge
- Screen-Übergänge sanft ein-/ausgeblendet oder geschoben, keine
  überzogenen/"bouncy" Animationen
- Neu erscheinende/verschwindende Flugzeuge sanft ein-/ausblenden statt
  abrupt zu erscheinen

**Detailtreue**
- Konsistentes Ausrichtungsraster über alle Screens hinweg, auch unter
  Berücksichtigung der späteren Panel-Rotation
- Einheitliche Innenabstände (Padding), keine sich überlappenden Elemente

Diese Richtlinien sind bewusst als **Gestaltungsprinzipien in Worten**
formuliert, nicht als Code oder exakte Pixel-Vorlage einer bestehenden
Anwendung — die konkrete Umsetzung (genaue Farbwerte, Layout-Code,
Animationskurven) soll eigenständig entwickelt werden.

**Update — Ausbaustufe 2, Schritt 1** (siehe `docs/prompt-ausbaustufe-2.md`):
Die Themes wurden von sechs auf genau zwei reduziert — `amber` (Standard,
gedämpftes Gold) und `mono` (neutrales Off-White) — beide mit identischem
dunklem Anthrazit-Grundton, unterschieden ausschließlich durch die
Akzentfarbe (`flugradar/display/theme.py`, `_theme_from_accent()`, damit
beide Themes strukturell nicht auseinanderlaufen können). Alte
Theme-Namen (`dark`/`green`/`red`/`yellow`/`white`) in einer bestehenden
`settings.json` fallen über `resolve_theme()` still auf `amber` zurück,
ohne Fehler. Zusätzlich zentrale Design-Tokens (`DesignTokens`/`TOKENS`
im selben Modul): Abstandsraster, vier Schriftgrößen-Stufen,
Linienstärke, zwei Animationsdauern (150 ms / 350 ms) und eine
gemeinsame Easing-Kurve (`ease_out_cubic`). Die Tokens sind angelegt,
aber noch **nicht** flächendeckend in den Screens verdrahtet — das ist
Aufgabe des Politur-Durchgangs in Schritt 3.

**Update — Ausbaustufe 2, Schritt 3** (siehe `docs/prompt-ausbaustufe-2.md`):
Politur-Durchgang abgeschlossen. Alle sechs Screens (Radar, Detail, Uhr,
About, Settings, plus die Nav-Chrome in `nav.py`) beziehen Schriftgrößen
jetzt aus `TOKENS.font_title/value/standard/small` statt aus verstreuten
Literalen; einzige bewusste Ausnahme ist die große Uhrzeit auf dem
Uhr-Screen (`ClockScreen._HERO_TIME_SCALE`), als dokumentiertes Vielfaches
von `font_title`, nicht als freistehende Zahl. Sich ändernde Zahlenwerte
(Höhe, Geschwindigkeit, Entfernung, V/S, Uhrzeit) laufen durchgängig über
die Mono-Schriftvariante (`get_font(..., mono=True)`) für tabellarische
Ziffern. Einheitliche Strichstärke über `TOKENS.line_stroke` (Kompass,
Sweep, Footer-Icons); echte 1px-Haarlinien (Entfernungsringe,
Mittelpunkt-Fadenkreuz) bleiben bewusst unskaliert. Zwei neue Theme-Felder
(`surface`, `surface_accent`) lösen die zuvor hartcodierten grünen
Footer-Button-Farben in `nav.py` ab; der Rundbezel (`mask.py`) ist jetzt
themenabhängig und reagiert auf Live-Reload. Screen-Wechsel blenden über
`TOKENS.duration_long_ms`/`ease_out_cubic` weich über (statt hart
umzuschalten); neu erscheinende/verschwindende Flugzeuge blenden über
`TOKENS.duration_short_ms` sanft ein bzw. aus (`RadarRenderer.draw_aircraft`
in `flugradar/display/renderer.py`). Typografie: Inter/IBM Plex Sans werden
per `install.sh` als apt-Pakete bereitgestellt (beide OFL-lizenziert, kein
Vendoring von Font-Binaries nötig); fehlen sie auf älteren
Raspbian-Versionen, fällt `flugradar/display/fonts.py` sauber auf
DejaVu/Noto/System-Sans zurück (kein Absturz, per Test abgesichert). Ein
Regressionstest (`flugradar/tests/test_design_tokens.py`) prüft, dass
außerhalb von `theme.py` keine neuen Farbtupel hinzukommen (mit expliziter
Ausnahmeliste für strukturelle Alpha-Masken-Konstanten, die keine
Design-Entscheidung sind).

**Update — Ausbaustufe 2, Schritt 4** (siehe `docs/prompt-ausbaustufe-2.md`):
Einstellungsmenü am Gerät gebaut (`flugradar/display/screens/menu.py`,
`MenuScreen`), ersetzt das bisherige einfache `SettingsScreen`. Zwei
Ebenen (Wurzelliste `Karte/Standort/Darstellung/Filter/Anzeige/Einheiten/
System` + je ein Untermenü), Aufruf per Swipe links vom Radar (oder von der
Uhr), zurück per Swipe rechts oder Zurück-Pfeil links oben — beides springt
eine Ebene zurück bzw. von der Wurzel zum Radar. Ebenenwechsel als
horizontales Schieben über `TOKENS.duration_long_ms`/`ease_out_cubic`.
Vier Bedienelement-Arten wie in 4.3 gefordert: Umschalter, Einfachauswahl
(zyklisch bei Tap, Häkchen-Äquivalent als Wertanzeige rechts), Stufenregler
(Tap-Position auf der Zeile setzt den Wert, gerastert auf `step_v`), Aktion
mit Rückfrage (Neustart/Herunterfahren — erster Tap zeigt zwei getrennte
Schaltflächen Bestätigen/Abbrechen, kein versehentliches Auslösen). Zeilen
folgen der Kreissehne (`scaling.circle_half_width_at_row`), Trennlinien als
Haarlinien in Sehnenbreite, Scroll-Indikator als dünner Bogen
(`_draw_scroll_arc`) statt gerader Leiste; sanftes Scrollen mit Nachlauf
über `nav.ScrollState.kick()`/`current_offset()` (neue, rein additive
Erweiterung — bestehende `.step()`/`.offset`-Nutzung z. B. in
`DetailScreen` unverändert).

**Standort**: exakt zwei feste Orte (kein Suchfeld, keine Tastatur), als
benannte Konstanten in `flugradar/config/locations.py`:
- Gießen, DE — 50.58727° N, 8.67554° E (Stadtmitte; Quelle: latitude.to,
  latlong.info, beide übereinstimmend auf 5 Nachkommastellen)
- Sassofortino (Roccastrada, Provinz Grosseto), IT — 43.02583° N,
  11.11222° E (Quelle: Wikipedia-Koordinaten-Infobox)

Radius als Presets 25/50/100/150/250 km. Die vorher im Portal
existierenden „Quick Presets" (`radar.html`) hatten abweichende
Koordinaten für „Grosseto" (Stadtzentrum statt Sassofortino) — beim Bau
dieses Schritts entdeckt und korrigiert: das Portal zieht die Presets jetzt
aus derselben `LOCATIONS`-Liste wie das Gerätemenü, damit beide garantiert
denselben Stand zeigen.

**Persistenz**: jede Änderung wird sofort über
`AppSettings.save_portal_settings()` geschrieben (kein Speichern-Knopf),
atomar (temporäre `.tmp`-Datei, dann `os.replace()` — betrifft jetzt auch
den Web-Portal-Pfad, der vorher nicht atomar war). Damit das eigene
Schreiben des Geräts nicht wenig später durch den Live-Reload-Poll
(`check_portal_reload()`, alle 2 s) redundant nochmal angewendet wird und
dabei sichtbar flackert (v. a. der Kartenkompositor würde neu aufgebaut),
markiert `AppSettings.mark_portal_synced()` den Dateistand direkt nach dem
Schreiben als bereits gesehen; `RadarApp` wendet die Änderung stattdessen
sofort selbst an (`_apply_live_settings()`, wie beim Portal-Reload, nur
ohne die 2-Sekunden-Verzögerung).

**Neue Einstellungen** (Filter/Darstellung/Anzeige/Einheiten) — Übersicht
Einstellung → Env-Variable → Portal-Seite → Menüpfad am Gerät:

| Einstellung | Env-Variable | Portal-Seite | Menüpfad (Gerät) |
|---|---|---|---|
| Standort (Lat/Lon) | `FLUGRADAR_HOME_LAT`/`_LON` | Radar | Standort → Ort |
| Radius | `FLUGRADAR_RADIUS_KM` | Radar | Standort → Radius |
| Kartenanbieter | `MAP_PROVIDER` | Radar | Karte → Anbieter |
| openAIP-Overlay | `OPENAIP_OVERLAY_ENABLED` | Radar | Karte → openAIP-Luftraum |
| Regenradar | `RAINVIEWER_ENABLED` | Radar | Karte → Regenradar |
| Kartenhelligkeit | `MAP_BRIGHTNESS` | Radar | Karte → Kartenhelligkeit |
| Distanzeinheit | `FLUGRADAR_DISTANCE_UNIT` | Radar | Einheiten → Distanz |
| Mindesthöhe | `FLUGRADAR_MIN_ALT_FT` | Radar | Filter → Mindesthöhe |
| Notfall hervorheben | `FLUGRADAR_HIGHLIGHT_EMERGENCY` | Radar | Filter → Notfall hervorheben |
| Militär hervorheben | `FLUGRADAR_HIGHLIGHT_MILITARY` | Radar | Filter → Militär hervorheben |
| Nur Hervorgehobene | `FLUGRADAR_ONLY_HIGHLIGHTED` | Radar | Filter → Nur Hervorgehobene |
| Theme | `FLUGRADAR_THEME` | Display | Darstellung → Theme |
| Icon-Set | `FLUGRADAR_AIRCRAFT_ICON_SET` | Display | Darstellung → Icon-Set |
| Beschriftung | `FLUGRADAR_SHOW_AIRCRAFT_TAGS` | Display | Darstellung → Beschriftung |
| Kompassrose | `FLUGRADAR_SHOW_COMPASS` | Display | Darstellung → Kompassrose |
| Sweep | `FLUGRADAR_SHOW_SWEEP` | Display | Darstellung → Sweep |
| Ringe | `FLUGRADAR_SHOW_RINGS` | Display | Darstellung → Ringe |
| Automatisch zur Uhr | `FLUGRADAR_AUTO_CLOCK_S` | Display | Anzeige → Automatisch zur Uhr |
| Helligkeit | `FLUGRADAR_BRIGHTNESS` | Display | Anzeige → Helligkeit |
| Nachtmodus an/aus | `FLUGRADAR_NIGHT_MODE_ENABLED` | Display | Anzeige → Nachtmodus |
| Nachtmodus ab/bis | `FLUGRADAR_NIGHT_MODE_START`/`_END` | Display | Anzeige → Nachtmodus ab/bis |
| Nachthelligkeit | `FLUGRADAR_NIGHT_MODE_BRIGHTNESS` | Display | Anzeige → Nachthelligkeit |
| Temperatureinheit | `FLUGRADAR_TEMPERATURE_UNIT` | Display | Einheiten → Temperatur |
| Uhrzeitformat | `FLUGRADAR_TIME_FORMAT` | Display | Einheiten → Uhrzeit |
| API-Keys (FR24/Tomorrow/AirLabs/openAIP) | je `*_API_KEY` | API Keys | — (bewusst kein Gerätepfad: 4.3 verbietet freie Textfelder) |
| adsbdb an/aus, Enrich-Radius, Fotos | `ADSBDB_*`/`AIRCRAFT_PHOTOS_ENABLED` | API Keys | — (dito) |
| Version/Hostname/IP/Portal/Quellen | — | About | System → (Info-Zeilen, nur lesend) |
| Neustart/Herunterfahren | — | System | System → Neustart/Herunterfahren |

„Helligkeit" ist eine **Software-Abdunkelung** (halbtransparentes Overlay
über dem fertigen Frame, `flugradar/display/brightness.py`), keine echte
Backlight-/PWM-Ansteuerung — ein Sysfs-Pfad lässt sich nicht für jede
Panel-/Treiber-Kombination voraussetzen. Funktioniert dadurch garantiert
auf jeder Pi+Display-Kombination, dimmt aber nicht so tief wie eine echte
Hintergrundbeleuchtungssteuerung. Nachtmodus setzt in seinem Zeitfenster
(mit Mitternachts-Wrap, z. B. 22:00–06:00) eine niedrigere Helligkeits-
Obergrenze, hebt eine ohnehin schon niedrigere manuelle Einstellung aber
nie an.

**Update — Ausbaustufe 2, Schritt 5** (siehe `docs/prompt-ausbaustufe-2.md`,
letzter Schritt des Auftrags): Getrackter-Flug-Screen
(`flugradar/display/screens/tracking.py` — `TrackedFlightScreen`).

- **Auswahl** (5.1, alle drei Wege funktionieren): Footer-Aktion
  „Track"/„Untrack" auf der Detailansicht (`DetailScreen._footer_buttons`,
  nur sichtbar wenn ein Callsign vorliegt, zeigt „Untrack" statt „Track"
  wenn der gerade angezeigte Flug schon der getrackte ist); Callsign-Feld
  im Portal (Radar-Seite, Bereich „Flight Tracking", inkl. Zeitfenster in
  Minuten); automatisches Beenden nach `tracking_timeout_s` ohne Empfang
  (Default 900s/15min, konfigurierbar an beiden Stellen). Das getrackte
  Callsign liegt in `settings.json` (`tracked_callsign`) und übersteht
  einen Neustart; die „zuletzt gesehen"-Uhr startet nach einem Neustart
  bewusst neu (kein sofortiger Timeout nur weil die App kurz neu startete).
- **Routendaten**: adsbdb liefert `latitude`/`longitude` für Origin-/
  Destination-Flughäfen bereits in der bestehenden `/callsign/`-Antwort —
  wurde bisher nicht ausgelesen (`AdsbdbAirport` hatte nur Code/Name/Stadt).
  Jetzt ergänzt (`flugradar/data_sources/adsbdb.py`) und über
  `AdsbdbEnricher.apply()` in vier neue `Aircraft`-Felder durchgereicht
  (`origin_lat/lon`, `destination_lat/lon`) — keine neue Datenquelle,
  keine zusätzlichen API-Calls, unterliegt derselben RAM-only/TTL-Regel
  wie alle anderen Routendaten. AirLabs liefert diese Koordinaten nicht
  (nur `dep_iata`/`arr_iata`), fällt bei aktivem AirLabs-Key also auf den
  „Route unbekannt"-Zustand zurück (Codes werden trotzdem angezeigt).
- **Fortschrittsberechnung** (5.2, reine Funktionen, keine pygame-Abhängigkeit,
  `flugradar/data_sources/route_progress.py`): Fortschritt = (Gesamtstrecke
  − Reststrecke zum Ziel) / Gesamtstrecke, beidseitig auf 0–100% geklemmt;
  Reststrecke via bestehendem `geo.haversine_km`; Restzeit aus
  Reststrecke/Geschwindigkeit, `None` (→ „—" in der Anzeige) bei
  Geschwindigkeit 0 oder unbekannt statt Division durch Null. Steig-/
  Sinkrate als Wort („climbing"/„descending"/„level"), nicht nur Vorzeichen.
- **Die vier Sonderfälle aus 5.3** — alle im Screen selbst behandelt
  (`TrackedFlightScreen.draw`), kein leerer Screen und kein Absturz:
  1. Keine Route bekannt → kein Balken, Codes (falls vorhanden) plus Hinweis
     „Route position unknown"/„Route unknown", Live-Telemetrie bleibt sichtbar
  2. Außer Reichweite, Tracking aktiv → letzter bekannter Zustand plus
     „No current data · last seen Xm ago" (App hält den letzten Snapshot in
     `RadarApp._tracked_last_snapshot`, nicht im Screen selbst, damit er
     auch beim Screen-Wechsel erhalten bleibt)
  3. Kein getrackter Flug → kurzer Hinweistext statt leerem Screen
  4. Gelandet / Signal endgültig weg → Tracking beendet, zurück zum Radar
     (`RadarApp._update_tracking_lifecycle`, läuft pro Poll unabhängig vom
     aktiven Screen; „gelandet" erkennt einen Wechsel `is_on_ground`
     False→True **innerhalb der Tracking-Session**, damit ein am Gate
     gestarteter Trackingvorgang nicht sofort wegen Bodenstatus endet)
- **Integration** (5.4): erreichbar per Swipe rechts vom Radar (neue
  vierte Swipe-Richtung, vervollständigt die bisher nur 3 belegten
  Radar-Swipes runter/hoch/links); getrackter Flug auf dem Radar mit der
  Akzentfarbe hervorgehoben (`RadarRenderer._is_tracked`, dieselbe
  `aircraft_selected`-Farbe wie die Tap-Auswahl auf der Detailansicht,
  keine zweite Akzentfarbe eingeführt); tabellarische Ziffern für alle
  Werte wie in Schritt 1/3.

Vollständige Übersichtstabelle ergänzt:

| Einstellung | Env-Variable | Portal-Seite | Menüpfad (Gerät) |
|---|---|---|---|
| Getrackter Flug (Callsign) | `FLUGRADAR_TRACKED_CALLSIGN` | Radar | — (nur Detailansicht-Footer, kein Gerätemenü-Eintrag) |
| Tracking-Timeout | `FLUGRADAR_TRACKING_TIMEOUT_S` | Radar | — (dito) |

**Ausbaustufe 2 damit vollständig abgeschlossen** (alle 5 Schritte aus
`docs/prompt-ausbaustufe-2.md`).

## 16. Lizenz & Rechtliches

- Eigene Wahl der Lizenz für das neue Repository (z. B. MIT, falls keine
  Einschränkung gewünscht)
- Nutzungsbedingungen der eingebundenen Drittanbieter-APIs (adsb.fi, FR24,
  Tomorrow.io, RainViewer, CARTO, OpenStreetMap, AirLabs, aisstream.io,
  Planespotters, Wikimedia Commons, adsb-radar.com, adsbdb.com) unabhängig
  prüfen — diese Bedingungen gelten unabhängig davon, wie der eigene Code
  lizenziert ist. Für adsb-radar.com (Flugzeugtyp-Icon-Set, siehe
  Abschnitt 5.4a) gilt eine Backlink-Attributionspflicht, umgesetzt in
  README.md, dem On-Device-About-Screen und der Portal-About-Seite (siehe
  `flugradar/assets/icons/aircraft/LICENSE.txt`)
- **adsbdb.com** (siehe `docs/prompt-adsbdb-openaip.md`, Teil A): kostenlose
  Anreicherungsquelle ohne Key, Standardquelle wenn kein AirLabs-Key
  hinterlegt ist. Die Flugroutendaten sind Arbeit von David Taylor
  (Edinburgh) und Jim Mason (Glasgow) und dürfen ohne deren ausdrückliche
  Genehmigung nicht kopiert, veröffentlicht oder in andere Datenbanken
  übernommen werden — deshalb werden Routendaten ausschließlich im
  Arbeitsspeicher mit TTL gehalten, nie auf Platte persistiert (siehe
  `flugradar/data_sources/adsbdb.py`, Modul-Kopfkommentar). Für
  Flugzeugfotos über adsbdb (Fallback, Standard aus) liefert die API keine
  Pro-Bild-Fotografen-/Urheberangabe, nur einen pauschalen
  „airport-data.com“-Hinweis — entsprechend generisch ist auch die im UI
  gezeigte Quellenangabe
- **openAIP** (siehe `docs/prompt-adsbdb-openaip.md`, Teil B): eigenständig
  geprüft (2026-07-24, per Tiles-API-OpenAPI-Schema unter
  `https://api.tiles.openaip.net/api/system/specs/v1/schema.json`, direkt
  von openAIP selbst, nicht von Dritt-Blogs):
  - **Lizenz**: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0),
    https://creativecommons.org/licenses/by-nc/4.0/ — **nur nicht-kommerzielle
    Nutzung**, passt zu diesem privaten Hobby-Projekt, aber wichtig bei
    jeder Weitergabe/Veröffentlichung des Codes zu erwähnen
  - **Attributionspflicht** (Zitat aus dem Schema): „Please add a proper
    attribution link to OpenAIP (https://www.openaip.net) as data source
    within your application!“ — umgesetzt als Link im On-Device-About-Screen
    und der Portal-About-Seite, aber **nur wenn ein Key hinterlegt ist**
    (sonst wird das Feature gar nicht genutzt)
  - **Kein eigenständiger Kartenhintergrund, sondern transparentes
    Overlay**: Der `openaip`-PNG-Tile-Layer zeigt nur Luftraum-/Flugplatz-
    /Navaid-Symbolik mit transparentem Hintergrund, kein Terrain/Straßen —
    ist zum Überlagern über eine Basiskarte gedacht (bestätigt durch
    Community-Implementierungen, die ihn explizit mit `transparent: true`
    einbinden). Deshalb als Overlay über der bestehenden CARTO/OSM-Karte
    umgesetzt, nicht als eigene Auswahl in der Basiskarten-Liste
  - **Key erforderlich**: kostenloser openAIP-Account, API-Client-Key über
    das eigene Profil („API Clients“-Seite)
  - **Rate-Limits**: vorhanden, aber ohne genaue Zahl dokumentiert — openAIP
    empfiehlt eigenes Caching, was der bestehende Kachel-Cache-Mechanismus
    bereits erfüllt
  - **Zoom-Bereich**: 2 (Weltansicht) bis „unlimited“ laut Doku; Anfragen
    außerhalb des unterstützten Bereichs liefern HTTP 204 (kein Fehler,
    einfach keine Kachel)
  - **Wichtiger Befund**: Der Auftrag geht von einem bereits bestehenden
    Regenradar-Overlay (RainViewer) aus, „analog“ dazu soll openAIP gebaut
    werden — ein solches Overlay existiert im Code aber **nicht**. Die
    Overlay-Logik in `flugradar/maps/compositor.py` (`MapCompositor.
    overlay_tiles`) ist daher komplett neu, nicht von einem bestehenden
    Muster abgeleitet. Ebenso gibt es (trotz `PROVIDERS`-Dict mit
    carto_dark/carto_light/osm) **keine** Laufzeit-Auswahl zwischen
    Basiskarten-Anbietern — nur `carto_dark` ist tatsächlich fest verdrahtet
    in `flugradar/display/app.py`. Das war für Teil B nicht blockierend, da
    ein Overlay unabhängig von der (nicht vorhandenen) Basiskarten-Auswahl
    per eigenem Ein/Aus-Schalter funktioniert — wird hier aber als Lücke
    zur bestehenden Spezifikation (Abschnitt 5.3) festgehalten
- Kein Quelltext, keine Asset-Dateien (Icons, Layout-Dateien, Fonts) aus
  bestehenden Drittprojekten übernehmen — nur die hier beschriebene
  Funktionsliste und die öffentlichen API-Dokumentationen als Grundlage
  verwenden
- **Weather Icons von Erik Flowers** (siehe `docs/prompt-wetterscreen.md`,
  Schritt 2): eigenständig geprüft (2026-07-25, direkt aus dem README des
  Repos `erikflowers/weather-icons`, nicht von Dritt-Quellen). Lizenz laut
  README wörtlich: „Weather Icons licensed under SIL OFL 1.1 / Code
  licensed under MIT License / Documentation licensed under CC BY 3.0" —
  nur die einzelnen SVG-Icon-Dateien werden verwendet (nicht das
  Webfont/CSS-Tooling, da der Screen wie alle anderen in pygame gerendert
  wird), verwendet ist also nur der SIL-OFL-1.1-Teil. Volltext der Lizenz
  liegt bei `flugradar/assets/icons/weather/LICENSE.txt`, inkl.
  Quellenangabe und Abrufdatum. SIL OFL 1.1 verlangt (anders als das
  Backlink-Erfordernis von adsb-radar.com) keine sichtbare In-App-Nennung,
  nur die Weitergabe des Lizenztexts bei Redistribution — trotzdem aus
  Konsistenz mit den übrigen Quellen zusätzlich im On-Device-About-Screen,
  der Portal-About-Seite und README.md genannt.
- **Lucide UI-Icons** (Ausbaustufe 3, UI-Überarbeitung Schritt 1, siehe
  `flugradar/display/ui_icons.py`): lizenziert unter ISC
  (`flugradar/assets/icons/ui/LICENSE.txt`, vollständiger Text inkl.
  Copyright-Zeile — ISC verlangt deren Erhalt bei Weitergabe). Lucide ist
  ein Fork von Feather Icons; drei der übernommenen Dateien
  (`chevron-left`, `chevron-right`, `lock`) sind laut Lucides eigener
  LICENSE-Datei zusätzlich von Feather abgeleitet und stehen daher
  zusätzlich unter Feathers MIT-Lizenz (Copyright Cole Bemis) — auch das
  ist im übernommenen Lizenztext vollständig enthalten, nicht separat
  zusammengefasst. Weder ISC noch MIT verlangen eine sichtbare
  In-App-Nennung, ist aber aus Konsistenz mit den übrigen Icon-/Font-
  Quellen trotzdem in README.md, dem On-Device-About-Screen (bzw. dessen
  Nachfolger in den Einstellungen) und der Portal-About-Seite aufgeführt.
  Es liegen nur die tatsächlich verwendeten SVG-Dateien im Repo, nicht das
  komplette Lucide-Set — Quelle, Abrufdatum und Versionsnummer stehen in
  `flugradar/assets/icons/ui/SOURCE.md`.
