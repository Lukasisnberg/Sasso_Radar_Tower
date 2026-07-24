# Auftrag: adsbdb.com als kostenlose Anreicherungsquelle + openAIP als Luftfahrtkarte

> Für Claude Code. Kann gleichzeitig als `docs/AUFGABE-ADSBDB.md` ins Repo.
> Bezug: `docs/ANFORDERUNGEN.md`, Abschnitte 5.1 (Flugdaten), 5.3 (Kartenkacheln),
> 5.4b (Bilder/Fotos), 5.5 (Caching).
> Reihenfolge: **Teil A zuerst vollständig fertigstellen**, Teil B erst danach.

---

# Teil A — adsbdb.com einbinden

## Grundsatz: adsb.fi bleibt unangetastet

**adsb.fi ist und bleibt die primäre Datenquelle des Projekts.** Sie liefert
alle Live-Positionen (Standort, Höhe, Kurs, Geschwindigkeit, Squawk), läuft
zuverlässig, kostet nichts und braucht keinen Key. An dieser Anbindung wird
im Rahmen dieses Auftrags **nichts geändert** — weder Endpunkt noch
Poll-Intervall noch Parsing.

adsbdb ist kein Ersatz und keine Alternative dazu, sondern eine reine
**Ergänzungsschicht obendrauf**: Sie beantwortet Fragen zu einem Flugzeug,
das adsb.fi bereits gemeldet hat („welcher Typ ist das, wem gehört es, wohin
fliegt es"). Sie liefert selbst **keine Positionen** und wird nie zur
Positionsbestimmung herangezogen.

Konkret heißt das:
- Fällt adsbdb komplett aus, funktioniert das Radar unverändert weiter —
  nur ohne Route/Halter in der Detailansicht.
- Fällt adsb.fi aus, hilft adsbdb nichts. Das ist so gewollt und akzeptiert.
- adsbdb wird immer **mit dem Hex bzw. Callsign aus der adsb.fi-Antwort**
  aufgerufen, nie umgekehrt.

## Warum

Die Detailansicht ist bisher auf FR24 angewiesen, um Route, Airline und
Flugzeugdetails zu zeigen — und FR24 kostet Geld. **adsbdb.com** liefert
dieselbe Klasse von Daten kostenlos, quelloffen und **ohne Registrierung
oder API-Key**. Damit wird die App auch ohne jeden bezahlten Zugang
vollständig nutzbar, was ein erklärtes Ziel des Projekts ist.

Zusätzlich liefert adsbdb pro Flugzeug eine Foto-URL — das deckt einen Teil
von Abschnitt 5.4b ab, ohne dass wir eine eigene Bildersuche mit
Qualitätsfilter gegen Cartoons, Clipart und Flottenlisten bauen müssen.

Referenz: https://github.com/mrjackwills/adsbdb

## Schritt 0 — Vorab prüfen

1. **Aktuelle API-Hauptversion ermitteln.** Die Endpunkte enthalten die
   Major-Version im Pfad (`/v1/...`). Bitte im verlinkten Repo bzw. auf
   adsbdb.com nachsehen, welche Version aktuell gültig ist, und diese
   verwenden — nicht blind `v1` annehmen.

2. **Lizenzhinweis zu den Routendaten lesen.** Im adsbdb-Repo steht sinngemäß,
   dass die Flugroutendaten von David Taylor (Edinburgh) und Jim Mason
   (Glasgow) stammen und ohne ausdrückliche Genehmigung nicht kopiert,
   veröffentlicht oder in andere Datenbanken übernommen werden dürfen.

   Daraus folgt für unsere Umsetzung verbindlich:
   - Routendaten **nur flüchtig im Arbeitsspeicher** cachen, mit TTL.
   - **Keine Persistenz auf Platte**, keine SQLite-/JSON-Datei, kein
     Vorab-Download eines Datenbestands, kein „Aufbau einer eigenen
     Routentabelle über die Zeit“.
   - Flugzeug-Stammdaten (Typ, Halter, Registrierung) sind davon nicht
     betroffen, aber wir behandeln sie der Einfachheit halber genauso.

   Bitte diesen Hinweis wörtlich in einem Kommentar am Kopf des neuen
   Client-Moduls festhalten, damit er bei späteren Änderungen nicht verloren
   geht.

3. **Bestehenden Code prüfen.** Es gibt bereits
   `flugradar/data_sources/enrichment.py` mit Tests. Bitte zuerst ansehen und
   entscheiden: erweitern oder einen zweiten Client danebenstellen. Bevorzugt
   erweitern, damit es nur **eine** Anreicherungsschicht mit klarer
   Quellenpriorität gibt.

## Schritt 1 — Client-Modul

Neues bzw. erweitertes Modul in `flugradar/data_sources/`, mit diesen
Endpunkten:

| Zweck | Endpunkt | Schlüssel |
|---|---|---|
| Flugzeugstammdaten | `/aircraft/<MODE_S oder Registrierung>` | ICAO-Hex aus dem `hex`-Feld von adsb.fi |
| Flugroute | `/callsign/<CALLSIGN>` | Callsign aus dem `flight`-Feld (getrimmt) |
| Airline | `/airline/<ICAO oder IATA>` | aus dem Callsign-Präfix ableitbar |

Erwartete Felder bei den Flugzeugstammdaten (bitte gegen die aktuelle
Doku gegenprüfen, nicht blind übernehmen): `type`, `icao_type`,
`manufacturer`, `mode_s`, `registration`, `registered_owner`,
`registered_owner_country_name`, `registered_owner_country_iso_name`,
`registered_owner_operator_flag_code`, `url_photo`, `url_photo_thumbnail`.

Besonderheit, die getestet werden muss: **Ist das Callsign unbekannt, das
Flugzeug aber bekannt, antwortet die API mit Status 200 und liefert nur den
Flugzeugteil ohne Route.** Das ist kein Fehlerfall und darf nicht als solcher
behandelt werden — die Detailansicht zeigt dann Typ und Halter, aber keine
Route.

## Schritt 2 — Abfragestrategie (wichtig für Höflichkeit gegenüber dem Dienst)

Nicht für jedes sichtbare Flugzeug bei jedem Poll-Zyklus anfragen. Stattdessen:

- **Auf Anforderung**: Tippt man ein Flugzeug an und öffnet die Detailansicht,
  wird für genau dieses Flugzeug angereichert — mit Vorrang.
- **Im Hintergrund**: nur die nächstgelegenen N Flugzeuge (konfigurierbar,
  Vorschlag N = 10), gedrosselt, ein Request nach dem anderen statt alle
  gleichzeitig.
- **Negativ-Cache**: Liefert die API für einen Hex/Callsign nichts, wird das
  Ergebnis „nicht gefunden“ ebenfalls gecacht (kürzere TTL), damit nicht bei
  jedem Zyklus erneut angefragt wird.
- **TTL**: Flugzeugstammdaten ändern sich praktisch nie während eines Fluges —
  lange TTL (Stunden) im Speicher. Route: mittlere TTL (Größenordnung
  30–60 Minuten). Beides ausschließlich im RAM, siehe Schritt 0.
- **Netzwerkausfall** darf die Anzeige nicht blockieren: Anreicherung läuft
  nebenläufig, das Radar rendert unabhängig davon weiter.

## Schritt 3 — Fotos

- In der Detailansicht das Flugzeugfoto anzeigen, wenn `url_photo` bzw.
  `url_photo_thumbnail` vorhanden ist. **Thumbnail bevorzugen**, das reicht
  für ein 720×720-Rundpanel und schont Bandbreite und Ladezeit.
- Heruntergeladene Bilder auf Platte cachen (das sind unsere eigenen
  Kopien einzelner Bilder für die Anzeige, keine Datenbankübernahme) — mit
  Größenbegrenzung des Cache-Verzeichnisses, damit er nicht unbegrenzt wächst.
- **Bildrechte prüfen**: Bitte nachsehen, ob die API zum Foto eine
  Urheber-/Quellenangabe mitliefert oder auf eine Quelle verweist. Falls ja,
  diese Angabe im UI mit anzeigen. Falls **keine** Urheberangabe verfügbar
  ist: kurz melden statt einfach anzuzeigen — dann entscheiden wir, ob wir
  die Fotoanzeige standardmäßig aktivieren oder hinter einer Einstellung
  lassen.
- Fehlt ein Foto, bleibt die Detailansicht ohne Bild — kein Platzhalter, der
  wie ein Ladefehler aussieht.

## Schritt 4 — Quellenpriorität und Konfiguration

Die folgende Reihenfolge gilt **ausschließlich für die Anreicherung**
(Route, Airline, Halter, Typdetails, Foto). Für **Positionsdaten** gibt es
keine Priorität und keine Auswahl — die kommen immer und ausschließlich von
adsb.fi:

1. **FR24**, falls ein gültiger Key hinterlegt ist (bleibt optional)
2. **adsbdb**, sonst — und als Standard, da ohne Key nutzbar
3. Keine Anreicherung, falls beides nicht verfügbar

Der Flugzeugtyp (`t`) und die Kategorie (`category`) aus der
adsb.fi-Antwort bleiben die erste Quelle für die Icon-Zuordnung; adsbdb wird
dafür nur herangezogen, wenn adsb.fi diese Felder für ein Flugzeug nicht
liefert.

Neue Einstellungen (Env + Portal + Settings-JSON, Priorität wie gehabt
Env > Portal > Default):

- `ADSBDB_ENABLED` (Default: `true`) — kein Key nötig
- `ADSBDB_ENRICH_NEAREST` (Default: `10`) — wie viele Flugzeuge im
  Hintergrund angereichert werden
- `AIRCRAFT_PHOTOS_ENABLED` (Default: zunächst `false`, bis Schritt 3
  geklärt ist)

Im Web-Portal unter „API-Keys“ bzw. „Anzeige“ sichtbar machen — mit einem
klaren Hinweis, dass adsbdb keinen Key benötigt.

## Schritt 5 — Attribution

adsbdb ist quelloffen und kostenlos; eine Nennung gehört sich und ist
konsistent mit dem, was wir für adsb.fi und die Kartenanbieter schon tun:

- **About-Screen der App**: adsbdb.com in die Quellenzeile aufnehmen
- **Web-Portal, About-Seite**: als Link
- **README.md** und `docs/ANFORDERUNGEN.md` (Lizenzabschnitt): adsbdb
  aufnehmen, inklusive des Hinweises zu den Routendaten aus Schritt 0

## Schritt 6 — Tests

- Parsen einer vollständigen Antwort (Flugzeug + Route)
- **Teilantwort**: Callsign unbekannt, Flugzeug bekannt → Status 200, nur
  Flugzeugdaten, kein Fehler
- Unbekannter Hex → Negativ-Cache greift, kein zweiter Request
- TTL: nach Ablauf wird erneut angefragt, davor nicht
- Netzwerkfehler → zuletzt bekannte Daten bleiben erhalten, kein Absturz
- Quellenpriorität: mit FR24-Key gewinnt FR24, ohne Key wird adsbdb genutzt
- Foto-Cache: zweimaliger Abruf lädt nur einmal herunter

Alle Requests in Tests gemockt — **kein Live-Call in der Testsuite**.

---

# Teil B — openAIP als Luftfahrt-Kartenebene

Erst beginnen, wenn Teil A fertig, getestet und gepusht ist.

## Warum

Der Kartenhintergrund zeigt bisher Straßen und Küstenlinien. Für ein
Flugradar ist die Luftraumstruktur deutlich relevanter: Lufträume, Plätze,
Meldepunkte, Frequenzen. openAIP stellt genau das als weltweite, von einer
Community gepflegte Datenbasis bereit, kostenlos nutzbar, erfordert aber
einen **kostenlosen Account für einen Client-Key**.

## Aufgaben

1. **Nutzungsbedingungen eigenständig prüfen**, bevor irgendetwas eingebaut
   wird: Ist die Nutzung der Kacheln in einer selbstgebauten Anwendung
   gedeckt? Welche Attribution wird verlangt? Gibt es Limits? Ergebnis in
   `docs/ANFORDERUNGEN.md` festhalten. Bei Unklarheit **melden statt
   annehmen**.
2. openAIP als **zusätzliche Auswahl** in die bestehende Kartenlogik
   aufnehmen — die Struktur mit mehreren Anbietern (dunkel / hell / VFR)
   existiert bereits, also dort einreihen statt einen Sonderweg zu bauen.
   Falls openAIP als transparentes Overlay über einer Basiskarte gedacht ist
   und nicht als eigenständiger Hintergrund: dann als Overlay-Ebene
   umsetzen, analog zum bestehenden Regenradar-Overlay.
3. **API-Key** in Env + Portal (Bereich „API-Keys“), Kartenebene nur
   anbieten, wenn ein Key hinterlegt ist — sonst ausgegraut mit Hinweis,
   wo man ihn bekommt.
4. **Kachel-Cache** wie bei den bestehenden Anbietern, kein Sonderweg.
5. **Attribution** gemäß den in Schritt 1 ermittelten Bedingungen im UI
   anzeigen.
6. Tests: Kartenanbieter-Auswahl inklusive openAIP, Verhalten ohne Key,
   Cache-Trennung zwischen den Anbietern (darf sich nicht mit CARTO/OSM
   vermischen).

---

# Nicht umsetzen

**openweathermap.org** wird bewusst **nicht** eingebunden. Das Projekt nutzt
bereits Tomorrow.io für Wetterdaten; zwei parallele Wetteranbieter zu pflegen
bringt keinen Mehrwert und verdoppelt nur den Wartungsaufwand. Falls
Tomorrow.io später Probleme macht, wird openweathermap als **Ersatz**
diskutiert, nicht als Ergänzung.

---

# Abschluss

- `docs/ANFORDERUNGEN.md` aktualisieren: Abschnitt 5.1 (adsbdb als
  Standardquelle für Anreicherung, FR24 nur noch optional bei vorhandenem
  Abo), 5.3 (openAIP), 5.4b (Fotos jetzt über adsbdb statt eigener
  Bildersuche), 5.5 (Caching-Vorgaben inkl. RAM-only für Routendaten),
  Lizenzabschnitt
- `CLAUDE.md`: Stand und offene Punkte fortschreiben
- `python -m pytest -v` grün, keine Regression, dann commit + push

## Abnahmekriterien

1. **Die adsb.fi-Anbindung ist unverändert**: keine Änderung an Endpunkt,
   Poll-Intervall oder Parsing, alle bestehenden adsb.fi-Tests unverändert
   grün. Wird adsbdb komplett deaktiviert (`ADSBDB_ENABLED=false`), verhält
   sich die App exakt wie vorher.
2. Ohne jeden API-Key zeigt die Detailansicht Flugzeugtyp, Halter und —
   sofern bekannt — Start- und Zielflughafen.
3. Routendaten werden nachweislich nicht auf Platte geschrieben.
4. Bei 30+ sichtbaren Flugzeugen entsteht keine Anfrageflut: pro
   Poll-Zyklus nur die konfigurierte Anzahl, gedrosselt.
5. Netzwerkausfall während laufender Anreicherung führt weder zu Absturz
   noch zu spürbarem Ruckeln in der Sweep-Animation.
6. adsbdb ist in App, Portal, README und Anforderungen als Quelle genannt.
7. Alle Tests grün.
