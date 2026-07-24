# Auftrag: Ausbaustufe 2 — Design, Portal-Kartenauswahl, Gerätemenü, Flugtracking

> Für Claude Code. Kann als `docs/AUFGABE-AUSBAU-2.md` ins Repo.
> Bezug: `docs/ANFORDERUNGEN.md`, Abschnitte 5.3 (Karten), 6 (Screens/Gesten),
> 7 (Konfiguration/Live-Reload), 15 (Gestaltungsrichtlinien).

## Warum diese Reihenfolge

Fünf Schritte, bewusst in dieser Abfolge. Der wichtigste Grund: **das
Einstellungsmenü wird erst gebaut, wenn die Design-Sprache steht.** Andersherum
würde man das Menü zweimal gestalten — einmal provisorisch, einmal richtig.
Ebenso stehen die Design-Tokens vor dem Politur-Durchgang, weil der Durchgang
sonst überall Einzelwerte ändert statt an einer zentralen Stelle.

Nach **jedem** Schritt: `python -m pytest -v`, committen, und mir Bescheid
geben — dann teste ich am Gerät, bevor es weitergeht. Nicht zwei Schritte in
einem Rutsch.

---

# Schritt 1 — Design-Tokens und Theme-Reduktion

Klein, aber Fundament für alles Weitere.

## 1.1 Zentrale Design-Tokens

Alle Farben, Schriftgrößen, Abstände, Linienstärken, Eckenradien und
Animationsparameter an **einer** Stelle definieren (z. B. erweitertes
`theme.py`), und im gesamten Renderingcode nur noch von dort beziehen. Keine
verstreuten Zahlenwerte oder Farbtupel mehr in den einzelnen Screens.

Mindestens diese Tokens:

- Hintergrund, Primärtext, Sekundärtext, Haarlinie, Akzent, Warnung
- Schriftgrößen: maximal vier Stufen (Titel, Wert, Standard, Klein)
- Abstände: ein Grundraster (z. B. 4 px) und daraus abgeleitete Vielfache
- Linienstärke für Icons und Trennlinien
- Zwei Animationsdauern (kurz ~150 ms für Tap-Rückmeldung, lang ~350 ms für
  Screen-/Ebenenwechsel) und **eine** gemeinsame Easing-Kurve

## 1.2 Themes auf zwei reduzieren

Die bisherigen Themes werden ersetzt durch genau zwei Varianten. Beide
behalten den **dunklen Grundton** (sehr dunkles Anthrazit, kein reines
Schwarz) — unterschieden wird nur die Akzentfarbe:

| Theme | Akzent | Charakter |
|---|---|---|
| `amber` (Standard) | gedämpftes Bernstein/Amber | warm, ruhig, Braun-/Rams-Anmutung |
| `mono` | neutrales Off-White | sachlich, maximal reduziert |

- Alle übrigen Themes (dark/grün, sonstige) **ersatzlos entfernen** —
  inklusive der zugehörigen Farbdefinitionen, Portal-Optionen und Tests.
- **Kein freier Farbwähler**, keine RGB-Regler, keine erweiterte Palette.
- Die **Warnfarbe** (Notfall-Squawk) bleibt in beiden Themes unverändert
  erhalten und ist die einzige weitere Farbe im UI.
- **Migration**: Steht in einer vorhandenen `settings.json` ein Theme, das es
  nicht mehr gibt, wird stillschweigend auf `amber` zurückgefallen — ohne
  Fehler, ohne leeren Screen. Bitte als Test abbilden.

## Tests Schritt 1

- Beide Themes liefern vollständige Token-Sätze, keine fehlenden Schlüssel
- Unbekanntes/entferntes Theme in der Settings-Datei → Fallback auf `amber`
- Bestehende Tests laufen nach dem Entfernen der alten Themes durch
  (angepasst, nicht deaktiviert)

## Abnahme Schritt 1

Radar startet in Amber, Umschalten auf `mono` funktioniert, alte
Theme-Namen führen nicht zum Absturz.

---

# Schritt 2 — Kartenanbieter im Portal auswählbar machen

Kleiner, schneller Gewinn: Die Anbieter existieren im Code, aber es wird fest
`carto_dark` verwendet.

## Aufgaben

- Auswahl im Web-Portal (Bereich Radar/Karte), gespeichert wie jede andere
  Einstellung (Env > Portal > Default), wirksam über den bestehenden
  Live-Reload **ohne Neustart**:
  - CARTO dunkel (Standard)
  - CARTO hell
  - OpenStreetMap
  - VFR (FAA) — soweit vorhanden
  - **keine Karte**
- **openAIP-Overlay** separat schaltbar (an/aus), unabhängig vom
  Basisanbieter, da es als Ebene darüber liegt. Nur anwählbar, wenn ein Key
  hinterlegt ist — sonst ausgegraut mit Hinweis, wo man ihn bekommt.
- **Regenradar-Overlay** ebenfalls als eigener Schalter, gleiche Systematik.
- **Kachel-Cache pro Anbieter getrennt** halten — beim Umschalten dürfen
  keine Kacheln des vorherigen Anbieters durchschlagen.
- Umschalten darf die laufende Sweep-Animation nicht unterbrechen: neue
  Kacheln nachladen, bis dahin den alten Hintergrund stehen lassen oder
  leer zeichnen, aber nicht die App blockieren.

## Tests Schritt 2

- Jeder Anbieter lässt sich setzen und wird von der Kartenlogik verwendet
- Cache-Trennung: derselbe Kachelindex bei zwei Anbietern liefert nicht
  dieselbe Datei
- „keine Karte" deaktiviert den Hintergrund vollständig
- Overlays lassen sich unabhängig vom Basisanbieter schalten
- Ohne openAIP-Key ist das Overlay nicht aktivierbar

## Abnahme Schritt 2

Im Portal umschalten → Kartenhintergrund am Gerät wechselt innerhalb
weniger Sekunden, ohne Neustart und ohne Ruckler.

---

# Schritt 3 — Politur-Durchgang nach Abschnitt 15

Kein neues Feature. Die bestehenden Screens (Radar, Detail, Uhr, Wetter,
About, Settings) werden konsequent auf die Gestaltungsrichtlinien gezogen.
Grundlage sind die Tokens aus Schritt 1.

## Aufgaben

- **Typografie**: eine frei lizenzierte, geometrische oder humanistische
  Sans-Serif (Vorschlag: Inter oder IBM Plex Sans). Schrift mit ausliefern
  bzw. per Installationsskript bereitstellen, Lizenzdatei mit ablegen.
  Maximal vier Schriftgrößen, Großbuchstaben-Label mit leichtem
  Letter-Spacing, Werte und Fließtext ohne.
- **Tabellarische Ziffern** für alle sich ändernden Zahlen (Höhe,
  Geschwindigkeit, Entfernung, Uhrzeit), damit nichts springt.
- **Eine Akzentfarbe** pro Theme, konsequent nur für aktive/hervorgehobene
  Zustände. Warnfarbe ausschließlich bei echtem Alarm.
- **Haarlinien statt Schatten**: 1 px, geringe Deckkraft. Keine
  Drop-Shadows, keine Glaseffekte, keine Verläufe außer dem dezenten
  Hintergrund.
- **Einheitliche Linienstärke** bei allen Icons und Rahmen.
- **Einheitliche Randabstände** zum Kreisrand auf allen Screens, gemeinsames
  Ausrichtungsraster.
- **Übergänge**: alle Screenwechsel mit derselben Dauer und Easing-Kurve
  (Token aus Schritt 1). Neu erscheinende und verschwindende Flugzeuge
  sanft ein-/ausblenden statt hart zu erscheinen.
- **Aufräumen**: alles entfernen, was keine Information trägt — dekorative
  Linien, doppelte Beschriftungen, Elemente, die dauerhaft sichtbar sind
  obwohl sie nur im Kontext gebraucht werden.

## Tests Schritt 3

- Kein Modul greift noch auf hartcodierte Farben/Größen zu (z. B. per
  einfacher Prüfung, dass außerhalb des Token-Moduls keine Farbtupel
  definiert werden)
- Schriftdateien werden gefunden; fehlende Schrift führt zu sauberem
  Fallback statt Absturz
- Bestehende Screen-Tests unverändert grün

## Abnahme Schritt 3

Optischer Eindruck: ruhig, einheitlich, nichts springt, alle Screens wirken
wie aus einem Guss. Ich beurteile das am Gerät.

---

# Schritt 4 — Einstellungsmenü am Gerät (Swipe nach links)

Jetzt erst, weil es die fertige Design-Sprache aus Schritt 1 und 3 nutzt.

## 4.1 Aufbau

Zwei Ebenen, keine dritte. Aufruf per **Swipe links** vom Radar, zurück per
**Swipe rechts** (bzw. aus der Wurzel zurück zum Radar). Zusätzlich ein
antippbarer Zurück-Pfeil links oben.

**Wurzelliste:**

| Eintrag | Untermenü-Inhalt |
|---|---|
| Karte | Anbieter, openAIP-Overlay, Regenradar, Kartenhelligkeit |
| Standort | Auswahl zwischen zwei festen Orten, Radius |
| Darstellung | Theme (amber/mono), Icon-Set, Beschriftung, Kompassrose, Sweep |
| Filter | Mindesthöhe, Notfall hervorheben, Militär hervorheben, nur Hervorgehobene |
| Anzeige | Helligkeit, Nachtmodus + Zeitfenster, automatisch zur Uhr |
| Einheiten | Distanz (km/sm/nm), Temperatur (°C/°F), Uhrzeit (24 h/12 h) |
| System | Version, Hostname, IP, Portal-Adresse, Datenquellen, Neustart, Herunterfahren |

## 4.2 Standort — nur zwei feste Einträge

**Keine Ortssuche, keine Bildschirmtastatur, kein Geocoding.** Das
Untermenü „Standort" enthält genau zwei auswählbare Orte:

- **Gießen, DE**
- **Sassofortino, IT**

Die Koordinaten als benannte Konstanten im Code hinterlegen (z. B.
`flugradar/config/locations.py`), nicht in der Settings-Datei verstreuen.
Bitte die Koordinaten beider Orte nachschlagen, mit Quelle im Kommentar
vermerken und mir vor dem Commit zur Bestätigung nennen — Richtwerte:
Gießen etwa 50,58 N / 8,68 O, Sassofortino (Roccastrada, Provinz Grosseto)
etwa 43,0 N / 11,15 O.

Zusätzlich im selben Untermenü: **Radius** als Presets
(25 / 50 / 100 / 150 / 250 km, Einheit gemäß Einstellung).

Eine **Feinjustierung** der Koordinaten ist nicht nötig und wird nicht
gebaut.

## 4.3 Bedienelemente

Bewusst auf wenige Typen begrenzt:

- Umschalter (an/aus)
- Einfachauswahl (Liste, Häkchen beim aktiven Wert)
- Stufenregler (Helligkeit, Kartenhelligkeit)
- Aktion mit Rückfrage (Neustart, Herunterfahren) — zwei klar getrennte
  Schaltflächen, damit ein versehentlicher Tap das Gerät nicht ausschaltet

**Keine freien Textfelder.**

## 4.4 Layout auf dem runden Panel

- Äußere ~8 % des Radius bleiben frei von Bedienelementen
- Zeilenbreite folgt der Kreissehne: mittig breit, oben/unten schmaler.
  Text wird bei Bedarf gekürzt, niemals abgeschnitten
- Zeilenhöhe einheitlich und fingerfreundlich (Richtwert nicht unter ~64 px
  bei 720 px Panelbreite)
- Pro Zeile: Bezeichnung links, aktueller Wert rechts in gedämpfter Farbe,
  Untermenüs mit Chevron
- Trennlinien als Haarlinien, an der Sehne endend, nicht bis zum Rand
- Scroll-Indikator als dünner Bogen am Rand statt gerader Leiste
- Ebenenwechsel als horizontales Schieben, Tokens aus Schritt 1
- Vertikales Ziehen scrollt mit Nachlauf und weichem Abbremsen

## 4.5 Speichern

- Jede Änderung wird **sofort** gespeichert, kein Speichern-Knopf
- Schreiben in dieselbe `settings.json` wie das Portal, **atomar**
  (temporäre Datei schreiben, dann umbenennen)
- Bestehende Live-Reload-Logik greift weiter; die App darf durch ihr
  **eigenes** Schreiben keinen Reload auslösen und dadurch flackern
- Jede Einstellung am Gerät existiert auch im Portal und umgekehrt.
  Übersichtstabelle (Einstellung → Env-Variable → Portal-Seite → Menüpfad)
  in `docs/ANFORDERUNGEN.md` ergänzen

## Tests Schritt 4

- Navigation: Wurzel → Untermenü → zurück → Radar; keine Sackgasse
- Trefferzonen unter Kreisbeschneidung: Tap außerhalb der sichtbaren
  Sehnenbreite löst die Zeile nicht aus
- Ortswechsel setzt Koordinaten und Radius korrekt
- Wertebereiche werden begrenzt, ungültige Werte abgefangen
- Persistenz: Änderung am Gerät landet in `settings.json` und wird beim
  Neuladen zurückgeliefert
- Atomares Schreiben: simulierter gleichzeitiger Zugriff hinterlässt keine
  beschädigte Datei
- Bestehende Radar-Gesten (Tap auf Flugzeug, Tap auf Entfernungslabel,
  Pinch-Zoom) unverändert grün

## Abnahme Schritt 4

Alle Einstellungen ohne Rechner erreichbar, nichts wird vom Kreisrand
abgeschnitten, Gerät und Portal zeigen denselben Zustand, Änderungen sind
sofort im Radar sichtbar.

---

# Schritt 5 — Getrackter-Flug-Screen

Der letzte in Abschnitt 6 der Spec vorgesehene, noch fehlende Screen.

## 5.1 Auswahl eines Fluges

Drei Wege, alle drei sollen funktionieren:

1. **Aus der Detailansicht**: Aktion „Diesen Flug verfolgen" im Footer
2. **Im Web-Portal**: Callsign eintragen
3. **Automatisch beenden**: Wird der Flug über einen längeren Zeitraum nicht
   mehr empfangen (konfigurierbar, Vorschlag 15 Minuten), wird das Tracking
   beendet und zum Radar zurückgekehrt

Das getrackte Callsign wird in der Settings-Datei gespeichert und übersteht
einen Neustart.

## 5.2 Inhalt des Screens

- **Fortschrittsbalken** von Start- nach Zielflughafen, mit dem
  Flugzeug-Icon an der aktuellen Position auf der Strecke. Der Fortschritt
  errechnet sich aus der zurückgelegten Distanz im Verhältnis zur
  Gesamtstrecke
- **Start und Ziel** als Kürzel plus Ortsname, links und rechts am Balken
- **Verbleibende Distanz** und **geschätzte Restflugzeit**, abgeleitet aus
  aktueller Geschwindigkeit über Grund
- **Höhe**, **Geschwindigkeit**, **Steig-/Sinkrate** — letztere mit
  eindeutigem Richtungshinweis, nicht nur als Vorzeichen
- **Callsign, Typ, Halter** aus der bestehenden Anreicherung

## 5.3 Fälle, die sauber abgefangen werden müssen

Das ist der eigentliche Aufwand bei diesem Screen — bitte nicht nur den
Idealfall bauen:

- **Keine Route bekannt** (adsbdb kennt das Callsign nicht): Screen zeigt
  Live-Daten ohne Fortschrittsbalken, mit klarem Hinweis statt leerem Balken
- **Flugzeug außer Reichweite**, aber Tracking aktiv: letzte bekannte Werte
  mit Zeitstempel und deutlicher Kennzeichnung „keine aktuellen Daten"
- **Kein getrackter Flug ausgewählt**: Screen erklärt kurz, wie man einen
  auswählt, statt leer zu sein
- **Flug gelandet / Signal endgültig weg**: Tracking beenden, zurück zum
  Radar
- Fortschritt wird auf 0–100 % begrenzt (ein Flug, der über das Ziel
  hinausfliegt, ergibt keinen Balken über den Rand hinaus)

## 5.4 Integration

- Erreichbar über die bestehende Screen-Navigation, an sinnvoller Stelle in
  der Swipe-Reihenfolge
- Auf dem Radar wird der getrackte Flug mit der Akzentfarbe hervorgehoben
- Gestaltung nach Schritt 1/3, insbesondere tabellarische Ziffern für alle
  Werte

## Tests Schritt 5

- Fortschrittsberechnung mit bekannten Koordinatenpaaren (Start, Ziel,
  aktuelle Position) → erwarteter Prozentwert
- Begrenzung auf 0–100 %
- Restzeit-Berechnung inklusive Division durch null (Geschwindigkeit 0)
- Alle vier Sonderfälle aus 5.3 führen zu definiertem Verhalten, nicht zu
  Absturz oder leerem Screen
- Tracking übersteht Neustart (Persistenz des Callsigns)
- Zeitüberschreitung beendet das Tracking

## Abnahme Schritt 5

Einen realen Flug aus der Detailansicht heraus verfolgen: Fortschritt,
Restdistanz und Restzeit sind plausibel und aktualisieren sich; der Flug ist
auf dem Radar hervorgehoben; nach Verlassen des Empfangsbereichs verhält
sich der Screen wie beschrieben.

---

# Gesamtabschluss

- `docs/ANFORDERUNGEN.md` fortschreiben: reduzierte Themes, feste
  Standortauswahl statt Ortssuche, Portal-Kartenauswahl,
  Einstellungsmenü-Struktur, Tracking-Screen
- `CLAUDE.md`: Stand und offene Punkte aktualisieren
- Nach jedem Schritt einzeln committen — nicht alle fünf in einem Commit
