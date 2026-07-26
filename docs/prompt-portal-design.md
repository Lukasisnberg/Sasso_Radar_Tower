# Auftrag: Web-Portal im Dieter-Rams-Stil gestalten

> Für Claude Code. Kann als `docs/AUFGABE-PORTAL-DESIGN.md` ins Repo.
> Betrifft die Flask-Weboberfläche (`flugradar/web/`), erreichbar unter
> `http://<host>.local:5000` — nicht die pygame-Display-Screens.
> Bezug: `docs/ANFORDERUNGEN.md`, Abschnitt 15 (Gestaltungsrichtlinien).

## Ziel

Das Web-Portal funktioniert, sieht aber noch wie ein Standard-Formular aus.
Es soll dieselbe Designsprache bekommen wie die Display-Screens: Dieter Rams
— reduziert, funktional, zeitlos. Portal und Gerät sollen erkennbar zur
selben Anwendung gehören.

**Wichtig: Das ist ein reiner Gestaltungs-Durchgang.** Keine neuen Funktionen,
keine geänderten Routen, keine geänderte Speicherlogik. Was das Portal kann,
bleibt exakt gleich — es sieht danach nur anders aus. Alle bestehenden
Web-Tests müssen unverändert grün bleiben.

## Grundprinzipien (aus Abschnitt 15, auf Web übertragen)

- **Weniger, aber besser**: keine dekorativen Elemente, keine Farbflächen
  ohne Funktion, kein visuelles Rauschen. Jede Linie trägt Information.
- **Eine Akzentfarbe** (das Amber aus den Display-Tokens), sonst gedämpfte
  Grautöne auf dunklem Grund. Warnfarbe ausschließlich für echte
  Warnungen (z. B. Bestätigung vor Neustart/Herunterfahren).
- **Haarlinien statt Kästen und Schatten**: Trennung durch dünne Linien
  geringer Deckkraft, keine Cards mit Schlagschatten, keine Verläufe.
- **Zeitlos statt trendig**: flaches Design, kein Glasmorphismus, keine
  runden bunten Buttons, keine Animationsspielereien.
- **Ruhe durch Weißraum** (hier: Dunkelraum): großzügige Abstände,
  klare Gruppierung, nichts gedrängt.

## Farb- und Schrifttoken zentral, konsistent mit dem Gerät

- Die Portal-Farben und -Schriftgrößen als **CSS-Custom-Properties**
  (`:root { --bg: …; --text: …; --accent: … }`) an einer Stelle in der
  bestehenden `style.css` definieren, analog zu den `theme.py`-Tokens der
  Display-App. **Dieselben Hex-Werte** verwenden wie das Gerät, damit Portal
  und Panel farblich identisch sind:
  - Hintergrund: sehr dunkles Anthrazit (kein reines Schwarz)
  - Primärtext: warmes Off-White
  - Sekundärtext / Labels: gedämpftes Grau
  - Haarlinie: Grau mit niedriger Deckkraft
  - Akzent: gedämpftes Amber
  - Warnung: nur für destruktive Aktionen
- **Schrift Inter** (dieselbe wie auf dem Gerät), lokal ausgeliefert statt
  von einem CDN geladen — das Portal muss auch ohne Internetzugang im
  lokalen Netz sauber aussehen. Schriftdateien unter
  `flugradar/web/static/fonts/` ablegen, Lizenz (SIL OFL) mit dazu, per
  `@font-face` einbinden. Fallback auf System-Sans, falls die Datei fehlt.
- **Tabellarische Ziffern** (`font-variant-numeric: tabular-nums`) für alle
  Zahlenwerte.

## Layout

- **Ein durchgehendes Raster** über alle sechs/sieben Seiten: gleiche
  maximale Inhaltsbreite (das Portal wird am Rechner/Handy geöffnet, also
  eine lesbare Spaltenbreite zentriert, nicht über die ganze Fensterbreite
  laufen lassen).
- **Kopfbereich** je Seite: kleiner, ruhiger Titel in Großbuchstaben mit
  Letter-Spacing, keine große fette Überschrift. Darunter ggf. eine Zeile
  Kontext.
- **Navigation** zwischen den Seiten: schlicht, textbasiert, aktuelle Seite
  dezent per Akzent markiert — keine schweren Tabs, keine Buttons mit
  Rahmen.
- **Formularzeilen** einheitlich: Label links oder oben, Eingabe/Auswahl
  klar davon getrennt, Zeilen durch Haarlinien gegliedert. Konsistente
  Abstände über alle Seiten.
- **Responsiv genug**, dass es auf dem Handy (man ruft das Portal
  unterwegs im WLAN auf) nicht bricht — einspaltig, ausreichend große
  Tap-Ziele.

## Bedienelemente

- **Eingabefelder, Auswahllisten, Umschalter, Buttons** in einem
  einheitlichen, ruhigen Stil neu gestalten: dünne Umrandung oder
  Unterstreichung statt gefüllter Kästen, Fokuszustand dezent über die
  Akzentfarbe, keine grellen Rahmen.
- **Primäraktion vs. Sekundäraktion** klar unterscheidbar, aber beide
  zurückhaltend — die Primäraktion über die Akzentfarbe, nicht über Größe
  oder Knalligkeit.
- **Destruktive Aktionen** (Neustart, Herunterfahren): in der Warnfarbe und
  mit Bestätigungsschritt, damit sie sich klar vom Rest abheben.
- **Umschalter** (an/aus) als schlichte, flache Variante, nicht als bunter
  iOS-Toggle.

## Rückmeldungen

- **Speicherbestätigung** dezent und ruhig (kurze, unaufdringliche
  Bestätigung), kein grelles grünes Erfolgsbanner.
- **Fehlermeldungen** klar, in der Warnfarbe, mit konkretem Hinweis, nicht
  nur „Fehler".
- Zustände (z. B. „API-Key gesetzt" vs. „kein Key") ruhig und eindeutig
  kennzeichnen.

## Konsistenz mit dem Gerät

- Die Attributionshinweise (adsb.fi, adsbdb, CARTO/OSM, ggf. openAIP,
  Wetter-Icons) auf der About-/Attributionsseite im selben ruhigen Stil,
  als klickbare Links.
- Wo das Portal dieselben Einstellungen anbietet wie das Gerätemenü, sollen
  die Bezeichnungen **wortgleich** sein, damit man nicht rätselt, ob zwei
  verschieden benannte Optionen dasselbe tun.

## Was nicht passieren darf

- Keine Änderung an Routen, Formularfeldern (Namen/`name`-Attribute),
  Speicherlogik oder der Settings-Priorität.
- Keine neue Abhängigkeit, die aus dem Internet nachgeladen wird
  (kein CDN für CSS, Fonts oder Icons) — das Portal läuft im lokalen Netz,
  ggf. ohne Internet.
- Kein JavaScript-Framework einziehen. Falls für Umschalter/Bestätigungen
  etwas Interaktivität nötig ist, schlichtes Vanilla-JS, sparsam.

## Reihenfolge

1. CSS-Custom-Properties (Tokens) + `@font-face` (Inter lokal) + Grundraster
   in `style.css` anlegen; eine Seite (z. B. das Dashboard) beispielhaft
   darauf umstellen
2. Die übrigen Seiten auf dasselbe System ziehen
3. Bedienelemente (Felder, Auswahl, Umschalter, Buttons) vereinheitlichen
4. Rückmeldungen (Speichern/Fehler/Zustände) und destruktive Aktionen
5. Abgleich mit den Display-Screens: gleiche Farben, gleiche Begriffe

Nach jedem Punkt `python -m pytest -v` (Web-Tests müssen grün bleiben),
dann committen und mir den Stand melden, damit ich im Browser draufschaue.

## Tests

- Alle bestehenden Web-Tests unverändert grün (Struktur/Routen unangetastet)
- Font-Datei fehlt → Fallback greift, keine kaputte Seite
- Die Seiten rendern ohne Fehler mit gesetzten und mit leeren Werten

## Abnahme

1. Portal und Gerät wirken erkennbar wie dieselbe Anwendung (Farben,
   Schrift, Ruhe).
2. Keine funktionale Änderung — alles, was vorher ging, geht unverändert.
3. Kein extern nachgeladenes Asset; funktioniert im lokalen Netz ohne
   Internet.
4. Auf Handy und Desktop gleichermaßen benutzbar.
5. Alle Tests grün.
