# Anleitung — gedrucktes Bedienungsheft

Baut `out/Sasso-Radar-Tower-Anleitung.pdf`: eine 36-seitige, A5-hohe
Bedienungsanleitung im Braun-/Dieter-Rams-Stil des Geräts selbst (siehe
`docs/ANFORDERUNGEN.md` Abschnitt 15) — invertiert für Papier (dunkle
Scheibe auf hellem Grund statt hellem Text auf dunklem Grund), sonst
dieselben Design-Tokens wie `flugradar/display/theme.py`.

Deckt **nur die Bedienung** ab (Screens, Gesten, Menü, Portal) — keine
Installation, keine Architektur.

## Bauen

```bash
pip install -e ".[display,web,dev]"
sudo apt-get install -y fonts-inter fonts-ibm-plex   # für die Screenshots
python -m anleitung.build
```

Ergebnis: `out/Sasso-Radar-Tower-Anleitung.pdf`.

Nützliche Flags:

```bash
python -m anleitung.build --ohne-bilder   # vorhandene bilder/*.png wiederverwenden,
                                           # kein pygame/Flask/Chromium-Serverstart nötig
python -m anleitung.build --vorschau      # nur den HTML-Pfad ausgeben, im Browser ansehen
python -m anleitung.build --seiten-png    # zusätzlich jede Seite als PNG (braucht `pip install pymupdf`)
```

`bilder/*.png` wird mitversioniert — das PDF lässt sich also mit
`--ohne-bilder` auch ohne pygame/Chromium-Serverstart neu drucken, solange
nur an `buch/anleitung.html`/`buch.css` etwas geändert wurde.

## Aufbau

```
szene.py          feste, deterministische Beispieldaten (14 Flugzeuge,
                   ein Hauptflug DLH420 FRA->FCO, Wetter/Vorschau) --
                   bewusst nicht flugradar.data_sources.demo.DemoSource,
                   die nutzt ungeseedetes random
screenshots.py     rendert alle Geräte-Screens headless (SDL_VIDEODRIVER=
                   dummy, 720x720, echte Inter-Schrift) zu bilder/*.png
portal_shots.py    startet das Flask-Portal gegen ein leeres Datenverzeichnis
                   und fotografiert vier Seiten per Chromium
buch/
  anleitung.html   die 36 Seiten, als einzelne .seite-Sections
  buch.css         Satzsystem (A5, Farben/Schrift aus theme.py abgeleitet)
  wischkarte.svg   das Navigationsdiagramm, von Hand aus der tatsächlichen
                   Übergangstabelle in flugradar/display/app.py:653-785
                   gezeichnet
bilder/            erzeugte PNGs (committed)
out/               erzeugtes PDF (committed) + optionale Seiten-PNGs
build.py           Orchestrator: Screenshots -> HTML -> Chromium-Druck -> Prüfung
```

## Stolpersteine, die beim Bauen aufgetreten sind

- **Chromiums Druckpfad kennt keine `@page`-Margin-Boxen** (`@top-center`),
  kein `string-set`/`target-counter`. Kolumnentitel und Seitenzahlen sind
  deshalb normale, im Dokument selbst positionierte Elemente je Seite,
  nicht über CSS Paged Media erzeugt — das Buch ist explizit als 36
  einzelne `.seite`-Sections aufgebaut (`page-break-after: always`),
  nicht als fließender Text.
- **Neu erschienene Flugzeuge blenden über `TOKENS.duration_short_ms` (150 ms)
  von Alpha 0 ein** (`RadarRenderer.draw_aircraft`, `age = now -
  first_seen`, beide `time.monotonic()`). Mit einer eingefrorenen Uhr
  (nötig für einen reproduzierbaren Sweep-Winkel) bleibt `age` für immer 0
  → jedes Flugzeug unsichtbar. Behoben, indem `screenshots.py` vor jedem
  Aufruf `renderer._first_seen[hex] = 0.0` vorbelegt.
- **Dieses gepackte, headless Chromium lädt lokale SVG-Dateien als
  `<img src="…svg">`-Subressource über `file://` nicht zuverlässig**
  (leeres "gebrochenes Bild"-Icon; weder `--allow-file-access-from-files`
  noch `--headless=new` ändern das — PNG-`<img>` aus demselben Verzeichnis
  funktioniert dagegen anstandslos). `wischkarte.svg` bleibt trotzdem die
  eigenständig editierbare Quelle; `build.py` setzt ihren Inhalt inline in
  die Seite ein (`{{WISCHKARTE_SVG}}`-Platzhalter) statt sie zu referenzieren.
- **Das Menü schreibt bei jedem Tap sofort in `settings.json`**
  (`menu.py:_save`, kein Speichern-Button). `screenshots.py` setzt deshalb
  `FLUGRADAR_DATA_DIR` auf ein temporäres Verzeichnis, *bevor*
  irgendetwas aus `flugradar.config.settings` importiert wird (die
  Dateipfad-Konstante wird beim Import ausgewertet) — sonst würden die
  Bildläufe hier die echten Geräteeinstellungen verändern.
- **Hostname/IP im Screenshot**: `about._hostname()`/`_ip_address()` lesen
  echte Systemwerte; im Build-Container wäre das z. B. `vm`, was im
  gedruckten Buch wie ein Artefakt der Build-Umgebung aussähe.
  `screenshots.py` patcht beide Funktionen (in `about.py` *und* `menu.py`,
  die importiert sie separat per `from … import`) auf plausible
  Platzhalter (`sasso` / `192.168.1.42`).

## Tests

`flugradar/tests/test_anleitung.py` koppelt Buch und Code, ohne pygame zu
initialisieren (reiner Quelltext-/Datenabgleich, gleiches Prinzip wie
`test_design_tokens.py`):

- `anleitung.szene` baut fehlerfrei, der Hauptflug hat eine vollständige Route
- jede Zeilenbeschriftung, die `menu.py` für die sieben Menübereiche
  tatsächlich anbietet, kommt im Buch vor — fällt auf, wenn ein neuer
  Menüpunkt gebaut, aber nicht ins Buch übernommen wird
- jede Attributionsquelle aus `about.py` (Info-Bildschirm) kommt auf der
  Nachweisseite vor
