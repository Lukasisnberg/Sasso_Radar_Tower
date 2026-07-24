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
  Abo. Liefert zusätzlich Airline, Route, angereicherte Flugdetails. Soll
  adsb.fi ergänzen bzw. ersetzen, wenn ein gültiger Key hinterlegt ist.
  Fallback-Logik: ohne FR24-Key läuft die App ausschließlich mit adsb.fi
  weiter (nur Positionen, keine Routen/Airline-Details).
- **AirLabs** — optional, für Abflugplandaten, wenn ein getrackter Flug noch
  nicht in der Luft ist.

### 5.2 Wetter

- **Tomorrow.io** — aktuelle Temperatur (Uhr-Screen) und mehrtägige
  Vorhersage. Erfordert einen kostenlosen/kostenpflichtigen API-Key.
- **RainViewer** — Regenradar-Kachel-Overlay auf der Karte, kein eigener Key
  nötig (kostenlose Weather-Maps-API, für persönliche/edukative Nutzung
  gemäß deren Nutzungsbedingungen — bitte deren aktuelle ToS und
  Attributionspflichten selbst prüfen und einhalten).

### 5.3 Kartenkacheln

Konfigurierbarer Kartenhintergrund mit mehreren Anbietern zur Auswahl:

- **CARTO** (Dark Matter / Positron, "no labels"-Varianten) als Standard
- **OpenStreetMap** Standard-Kacheln als Alternative
- **FAA VFR Sectional Charts** als optionale Zusatzkarte für US-Standorte
  (public domain)

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

## 16. Lizenz & Rechtliches

- Eigene Wahl der Lizenz für das neue Repository (z. B. MIT, falls keine
  Einschränkung gewünscht)
- Nutzungsbedingungen der eingebundenen Drittanbieter-APIs (adsb.fi, FR24,
  Tomorrow.io, RainViewer, CARTO, OpenStreetMap, AirLabs, aisstream.io,
  Planespotters, Wikimedia Commons) unabhängig prüfen — diese Bedingungen
  gelten unabhängig davon, wie der eigene Code lizenziert ist
- Kein Quelltext, keine Asset-Dateien (Icons, Layout-Dateien, Fonts) aus
  bestehenden Drittprojekten übernehmen — nur die hier beschriebene
  Funktionsliste und die öffentlichen API-Dokumentationen als Grundlage
  verwenden
