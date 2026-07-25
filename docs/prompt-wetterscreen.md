# Auftrag: Wetterscreen nach Mockup umsetzen

> Für Claude Code. Kann als `docs/AUFGABE-WETTERSCREEN.md` ins Repo.
> Referenz-Layout: `docs/mockups/weather-screen-mockup.svg`
> Bezug: `docs/ANFORDERUNGEN.md`, Abschnitt 6 (Screens), Abschnitt 15
> (Gestaltung). Design-Tokens aus `theme.py`.

## Ziel

Der Wetterscreen wird nach dem beiliegenden SVG-Mockup gestaltet: aktuelles
Wetter oben, darunter mehrere Vorhersagetage. Amber-auf-Anthrazit,
Rams-Sprache, mittlere Info-Dichte.

## Wie das Mockup zu lesen ist

- `docs/mockups/weather-screen-mockup.svg` ist die **Layout-Referenz**:
  Anordnung, Proportionen, Farbwerte, Schriftgrößen, Positionen können daraus
  direkt abgelesen werden.
- **Das SVG wird nicht eingebettet oder gerendert.** Der Screen wird wie alle
  anderen in **pygame nachgebaut**. Das SVG ist Vorlage, kein Asset.
- Die Farb-Hex-Werte im Mockup sind an der bestehenden Design-Sprache
  orientiert. **Maßgeblich sind aber die Tokens aus `theme.py`** — falls es
  Abweichungen gibt, gewinnen die Tokens, nicht das Mockup. Das Mockup zeigt
  die Absicht, nicht die verbindlichen Werte.
- Die Icons im Mockup sind bewusst nur grob angedeutet (Sonne als Kreis mit
  Strahlen, Wolke als Kreisgruppe). Im echten Screen kommen **echte
  Wetter-Icons** aus einem lizenzierten Set (siehe unten).

## Aufbau (von oben nach unten)

1. **Kopf**: Ortsname in Großbuchstaben mit Letter-Spacing, darunter klein
   Wochentag + Uhrzeit. Ort kommt aus der aktuellen Standort-Einstellung
   (der Anzeigename, den auch das Standort-Untermenü nutzt).
2. **Aktuelles Wetter**: großes Wetter-Icon, sehr große Temperatur,
   darunter der Wetterzustand als Text.
3. **Drei Kernwerte** nebeneinander: Wind, Gefühlte Temperatur,
   Regenwahrscheinlichkeit. Jeweils Label (klein, gedämpft) über Wert.
4. **Haarlinie** als Trenner (an der Kreissehne endend, nicht bis zum Rand).
5. **Fünf-Tage-Vorhersage** als leicht gebogene Reihe, die der runden Form
   folgt (die y-Versätze im Mockup zeigen die Wölbung): Wochentag,
   Wetter-Icon, Höchst- über Tiefsttemperatur.
6. **Screen-Indikator** unten (Punktreihe + Label „WETTER"), konsistent mit
   den anderen Screens.

## Wetter-Icons

- Ein frei und klar lizenziertes Set verwenden, das stilistisch zu Rams
  passt (einfarbige Strichsymbole, keine bunten/verspielten Icons).
  Kandidaten: **Weather Icons** von Erik Flowers (SIL OFL) oder
  **Meteocons** (freie Lizenz). Bitte die aktuelle Lizenz der gewählten
  Quelle vor Verwendung prüfen und den Lizenztext im Repo ablegen
  (`flugradar/assets/icons/weather/LICENSE.txt`, mit Quelle und Abrufdatum).
- Zuordnung der Tomorrow.io-Wettercodes zu den Icons als eigene, lesbare
  Tabelle. Für jeden Code, den Tomorrow.io liefern kann, ein passendes Icon;
  wo kein exaktes existiert, das nächstliegende plus ein generisches
  Fallback. Bitte eine Tag-/Nacht-Variante berücksichtigen, falls das Set
  sie anbietet (klarer Himmel Tag ≠ Nacht).
- Icons einfärben und cachen wie die Flugzeug-Icons (zur Ladezeit, nicht pro
  Frame). Farbe aus den Theme-Tokens.

## Daten

- Werte kommen aus dem bestehenden Tomorrow.io-Client (`weather`-Modul). Der
  Screen fügt keine neue Datenquelle hinzu.
- **Ohne Tomorrow.io-Key**: Der Screen darf nicht leer/kaputt sein. Klare
  Meldung anzeigen („Kein Wetter-Key hinterlegt — im Portal eintragen"),
  Layout bleibt stehen. Bitte als expliziten Fall behandeln und testen.
- **Bei Abruffehler / offline**: zuletzt bekannte Werte mit dezentem
  Hinweis auf das Alter der Daten; kein Absturz.
- Einheiten (°C/°F, km/h vs. mph) folgen der bestehenden Einheiten-Einstellung.

## Gestaltung (Abschnitt 15)

- Nur die Theme-Akzentfarbe für Hervorhebung (das aktuelle Icon/die aktuelle
  Temperatur), alles andere in gedämpften Grautönen. **Keine** bunten
  Wetterfarben.
- Tabellarische Ziffern für alle Temperaturen und Werte, damit bei
  Aktualisierung nichts springt.
- Nichts wird vom Kreisrand abgeschnitten — die Vorhersagereihe folgt der
  Sehne, äußere Tage sitzen etwas höher (wie im Mockup).
- Keine Schatten, keine Verläufe, Haarlinien mit geringer Deckkraft.
- Übergang beim Hereinwischen: dieselbe Dauer/Easing wie die anderen Screens.

## Tests

- Wettercode → Icon-Zuordnung für alle bekannten Codes (inkl. Tag/Nacht,
  falls umgesetzt) plus generisches Fallback
- Kein Key → definierte Hinweisdarstellung, kein Absturz
- Abruffehler → letzte Werte + Altershinweis
- Einheitenumschaltung wirkt auf alle angezeigten Werte
- Rendern mit vollständigen Beispieldaten wirft keine Exception
- Fehlende einzelne Felder (z. B. keine Regenwahrscheinlichkeit) → Wert wird
  ausgelassen, Layout bleibt stabil

## Reihenfolge

1. Layoutgerüst mit statischen Beispieldaten (Positionen nach Mockup)
2. Icon-Set einbinden, Lizenz ablegen, Code→Icon-Tabelle
3. Anbindung an den Tomorrow.io-Client, Einheiten, Fehlerfälle
4. Feinschliff nach Abschnitt 15, Vergleich mit dem Mockup

Nach jedem Punkt `python -m pytest -v`, dann committen.

## Abnahme

1. Der Screen entspricht in Anordnung und Ruhe dem Mockup.
2. Echte, lizenzierte Wetter-Icons, Lizenztext im Repo.
3. Ohne Key und bei Netzwerkausfall verhält sich der Screen definiert.
4. Nichts wird vom Kreisrand abgeschnitten, Ziffern springen nicht.
5. Alle Tests grün, keine Regression.
