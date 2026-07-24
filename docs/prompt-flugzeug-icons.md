# Auftrag: Flugzeugtyp-Icons einbinden (Icon-Set von adsb-radar.com)


## Ziel

Das Radar zeigt derzeit für alle Flugzeuge dasselbe generische Symbol. Es soll
stattdessen ein typspezifisches Icon-Set verwendet werden, damit man auf einen
Blick unterscheiden kann, was da fliegt. Als Quelle wird das frei nutzbare
Icon-Set von **adsb-radar.com** verwendet (ca. 30 Flugzeug-Icons, speziell für
ADS-B-Kartendarstellungen gemacht, Zuordnung über ICAO-Typkürzel vorgesehen,
Größenunterschiede zwischen leichten und schweren Mustern sind Teil des
Designs):

Quelle: https://adsb-radar.com/help/icons.html



## Schritt 1 — Assets beschaffen und ablegen

- Icons herunterladen (Einzeldateien oder Gesamtpaket, je nachdem was die
  Seite anbietet).
- Ablage: `flugradar/assets/icons/aircraft/`
- Dateinamen normalisieren: klein, ohne Leerzeichen, sprechend
  (z. B. `a320.svg`, `b747.svg`, `heli.svg`, `glider.svg`, `generic.svg`).
- Daneben zwei Dateien anlegen:
  - `LICENSE.txt` — Lizenztext, Quell-URL, Abrufdatum (siehe Schritt 0)
  - `SOURCE.md` — kurze Notiz, woher das Set stammt, welche Bedingung gilt
    und an welchen Stellen im Code/UI die Attribution umgesetzt ist
- Falls Dateien im Download fehlen, die wir für eine Kategorie brauchen
  (typischerweise Drohne/UAV oder Segelflugzeug): **nicht** von einer anderen
  Quelle nachladen, sondern die Kategorie vorerst auf das generische Icon
  mappen und mir melden, was fehlt.

## Schritt 2 — Attribution umsetzen (Pflichtteil der Lizenz)

Der geforderte Backlink muss an mehreren Stellen sichtbar sein, nicht nur
irgendwo im Code versteckt:

1. **README.md** — eigener Abschnitt „Attribution“ mit Link zu
   https://adsb-radar.com/ und Nennung des Icon-Sets
2. **About-Screen der Display-App** — Zeile mit der Quellenangabe, in derselben
   Zeile/Sektion wie die bestehenden Hinweise zu adsb.fi und CARTO/OSM
3. **Web-Portal, About-/Attribution-Seite** — als klickbarer Link
4. **`docs/ANFORDERUNGEN.md`**, Lizenzabschnitt — adsb-radar.com in die Liste
   der Drittanbieter mit eigenen Nutzungsbedingungen aufnehmen

Wichtig: Diese Attribution ist **nicht** über eine Einstellung abschaltbar zu
machen — sie ist Voraussetzung der Nutzung, anders als die
Karten-Attribution, für die eine gesonderte Genehmigung vorliegt.

## Schritt 3 — Icon-Loader (Rendering-seitig)

Neues Modul, z. B. `flugradar/display/aircraft_icons.py`:

- **SVG → Surface**: Bitte zuerst empirisch prüfen, ob die im Projekt
  installierte pygame-Version SVG-Dateien laden kann (SDL_image mit
  SVG-Unterstützung, ggf. `pygame.image.load` bzw. eine größenbasierte
  Lade-Funktion, falls vorhanden). Wenn ja, diesen Weg nutzen. Wenn nein, die
  SVGs **einmalig** beim ersten Start (oder im `install.sh`) mit einem
  geeigneten Werkzeug (z. B. `cairosvg`) in PNGs der benötigten Größen
  rastern und in einem Cache-Verzeichnis unter dem bestehenden
  Datenverzeichnis ablegen. Die gewählte Lösung bitte in `SOURCE.md` bzw.
  im Modul-Docstring kurz begründen.
- **Kein Rastern pro Frame.** Die Zielhardware ist ein Pi 4 — das muss
  flüssig bleiben.
- **Rotation**: Icon wird nach dem tatsächlichen Steuerkurs (`track`) gedreht.
  Gedrehte Surfaces in Winkelschritten (z. B. 5°) cachen, statt bei jedem
  Frame neu zu rotieren. Cache pro (Icon, Größe, Winkelschritt, Farbe).
- **Einfärbung**: Die Icons sind einfarbige Silhouetten und sollen zur
  Theme-Farbe passen. Einfärbung zur Ladezeit (nicht pro Frame), mit
  Varianten für: Normalzustand, ausgewähltes/getracktes Flugzeug,
  Alarmzustand (Notfall-Squawk 7500/7600/7700), Militär-Hervorhebung.
- **Größenstaffelung**: Die Quelldateien unterscheiden bewusst zwischen
  leichten und schweren Mustern. Diese Staffelung erhalten, nicht alle Icons
  auf dieselbe Kantenlänge normalisieren — aber eine Mindestgröße erzwingen,
  damit auch kleine Muster bei großer Zoomstufe erkennbar bleiben.
- **Robustheit**: Fehlende oder defekte Icon-Datei darf die App nicht zum
  Absturz bringen — dann generisches Icon verwenden und einmalig warnen
  (nicht bei jedem Frame ins Log schreiben).

## Schritt 4 — Zuordnungstabelle Flugzeug → Icon

Als eigene, gut lesbare Datendatei (z. B.
`flugradar/display/icon_mapping.json` oder als Python-Dict in einem eigenen
Modul), damit sie ohne Codeänderung erweiterbar ist. Auflösungsreihenfolge:

1. **ICAO-Typkürzel** aus dem `t`-Feld der adsb.fi-Antwort
   (z. B. `A20N`, `B738`, `B77L`, `C152`, `EC35`) → konkretes Icon.
   Das Set ist genau dafür gedacht („Typen kommasepariert hinter dem Icon
   eintragen“), also bitte eine möglichst breite Zuordnung für die im
   mitteleuropäischen Luftraum häufigen Muster anlegen.
2. **ADS-B-Emitter-Kategorie** aus dem `category`-Feld als Fallback
   (`A1`–`A7`, `B1`–`B7` usw. nach der öffentlichen ADS-B-Spezifikation) →
   grobe Klasse (leicht / mittel / schwer / Rotorcraft / Segelflugzeug /
   UAV / …). Die Zuordnungstabelle Kategorie-Code → Klasse bitte anhand der
   Spezifikation vollständig anlegen und im Code kurz kommentieren.
3. **Generisches Icon**, wenn beides fehlt oder unbekannt ist.

Zusätzlich: Militärische Muster (soweit über Typkürzel erkennbar) sollen das
Militär-Icon bekommen, unabhängig von der Kategorie.

## Schritt 5 — Integration in den Radar-Renderer

- Der bestehende Zeichencode für Flugzeuge nutzt ab jetzt den Icon-Loader
  statt der bisherigen generischen Form.
- Das kompakte Label (Höhe in 100 ft, ggf. Geschwindigkeit) bleibt am Icon,
  Position so wählen, dass es sich bei gedrehtem Icon nicht überlappt.
- Typografie und Farben nach `docs/ANFORDERUNGEN.md`, Abschnitt 15
  (Gestaltungsrichtlinien): eine Akzentfarbe, Warnfarbe ausschließlich für
  echte Alarme, tabellarische Ziffern.

## Schritt 6 — Konfiguration

Neue Einstellung (Env + Portal + Settings-JSON, gleiche Prioritätsregel wie
bisher: Env > Portal > Default):

- `AIRCRAFT_ICON_SET=detailed|simple` (Default: `detailed`)
  - `detailed` — das eingebundene Icon-Set
  - `simple` — die bisherige generische Form, ohne externes Set
    (nützlich als Rückfallebene und für Performance-Vergleiche)

Im Web-Portal unter „Anzeige“ auswählbar machen. Die Umschaltung muss über den
Live-Reload greifen, ohne Neustart der App.

## Schritt 7 — Tests

- Zuordnung: für eine Reihe realer Typkürzel (`A20N`, `B738`, `B77L`, `C172`,
  `EC35`, `PC12`, `F16`, …) das erwartete Icon prüfen
- Kategorie-Fallback: Datensatz ohne `t`, aber mit `category` → korrekte Klasse
- Doppelter Fallback: weder `t` noch `category` → generisches Icon
- Fehlende Datei auf der Platte → generisches Icon, kein Absturz
- Rotations-/Farb-Cache: zweimaliger Abruf derselben Kombination liefert
  dasselbe Surface-Objekt (Cache greift) und erzeugt keine zweite Rasterung
- Umschaltung `detailed` ↔ `simple` funktioniert und crasht nicht

## Schritt 8 — Dokumentation und Abschluss

- `docs/ANFORDERUNGEN.md`, Abschnitt 5.4a aktualisieren: Icons kommen jetzt
  aus einer extern lizenzierten Quelle statt vollständig eigengezeichnet —
  inklusive der Attributionspflicht und des Verweises auf `LICENSE.txt`
- `CLAUDE.md`: Stand und offene Punkte fortschreiben
- `README.md`: Attributionsabschnitt (siehe Schritt 2)
- Alle Tests laufen lassen (`python -m pytest -v`), erst danach committen
  und pushen

## Abnahmekriterien

2. Der geforderte Backlink ist an allen vier in Schritt 2 genannten Stellen
   vorhanden und nicht abschaltbar.
3. Auf dem Radar sind Linienjet, Leichtflugzeug und Helikopter optisch klar
   voneinander unterscheidbar.
4. Icons drehen sich korrekt mit dem Steuerkurs.
5. Die Sweep-Animation läuft auf dem Pi 4 unverändert flüssig — kein
   spürbarer Einbruch gegenüber vorher.
6. Alle Tests grün, keine Regression in den bestehenden Tests.
