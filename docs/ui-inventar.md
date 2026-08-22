# UI-Inventar (Schritt 0)

Bestandsaufnahme vor dem UI-Überarbeitungsauftrag (Icon-System,
Komponenten-Ebene, Navigationsmodell). Reiner Rechercheschritt, kein
Verhaltens-Code geändert — der einzige neue Code in diesem Schritt ist der
Screenshot-Harness (`flugradar/tools/screenshots.py`, Abschnitt 4).

## 1. Icon-Inventar

Jede Stelle im Code, die aktuell ein UI-Symbol aus pygame-Primitiven
zeichnet, statt es aus einer Datei zu laden.

| Datei : Funktion | Zweck | Aktuelle Größe (Referenz-px via `s()`) |
|---|---|---|
| `nav.py` : `draw_page_dots` (148–164) | Pagination-Punkte im Footer | Punktradius `max(2, s(4))`, Abstand `s(14)` |
| `nav.py` : `_draw_nav_arrow` (188–202) | Chevron für Footer-Buttons „Zurück"/„Weiter" | Größe wird vom Aufrufer übergeben |
| `nav.py` : `_draw_radar_icon` (205–224) | Mini-Radar (Kreis+Kreuz+Sweep-Linie+Punkt) für den Footer-Button „RADAR" | `radius = icon_size = s(7)` |
| `screens/menu.py` : Rückpfeil in `_draw_header` (400–408) | Zurück-Navigation, oben links im Kreis-Header | `arrow_size = s(9)` |
| `screens/menu.py` : `_draw_scroll_arc` (483–498) | Scroll-Positions-Bogen am Bezel-Rand | `radius = visible_radius() - s(4)` |
| `screens/weather.py` : `_draw_screen_indicator` (336–347) | Eigene Pagination-Punkte für das Wetter-Screen-Paging | `dot_r = max(2, s(3))` — **Duplikat** von `nav.draw_page_dots`, nicht importiert (siehe Inkonsistenz 5) |
| `screens/wifi.py` : `_draw_signal_bars` (39–55) | WLAN-Signalstärke-Balken (4 Stufen) | `max_h = s(14)` |
| `screens/wifi.py` : `_draw_lock_icon` (58–63) | Schloss-Symbol für gesicherte Netze | `lock_size = s(5)` |
| `screens/wifi.py` : Rückpfeil + Reload-Spinner in `_draw_header` (188–217) | Zurück-Navigation + Netzwerk-Neuscan | `arrow_size = s(9)`, Reload-Bogen `r = s(9)` |
| `screens/wifi.py` : `_draw_scroll_arc` (271–283) | Scroll-Positions-Bogen (gleiches Muster wie `menu.py`) | `radius = visible_radius() - s(4)` |
| `screens/wifi.py` : Auge-Icon in `_draw_password` (285–302) | Passwort ein-/ausblenden | `eye_r = s(10)` |
| `screens/wifi.py` : `_draw_connecting` (313–319) | Verbindungsaufbau-Spinner | `r = s(28)` |

**Korrektur gegenüber der Auftragsannahme**: Im Code existiert **kein**
Notfall-Dreieck, kein Häkchen und kein Zahnrad-Icon — weder in `detail.py`
noch in `menu.py`. Diese drei im Auftrag genannten Symbole sind schlicht
nicht vorhanden; hier explizit vermerkt statt stillschweigend aus der
Liste wegzulassen.

**Explizit außerhalb des Scopes** (Inhalt, kein Icon): Radar-Sweep,
Kompassrose, Entfernungsringe; Flugzeug-Marker/-Tags; `mask.py`s
Kreismaske/Bezel; `keyboard.py`s Text-Glyphen (Unicode-Zeichen über
Font-Rendering, keine gezeichneten Primitiven).

**Referenz für Schritt 1** (nicht Teil dieses Schritts, nur dokumentiert):
`aircraft_icons.py` ist das Vorbild für das künftige `ui_icons.py` — SVG
laden via `pygame.image.load` (kein `load_sized_svg` im Einsatz, repoweit
0 Treffer; die installierte pygame-Version konnte in dieser Sandbox nicht
geprüft werden, `pyproject.toml` pinnt nur `pygame>=2.5`), Recolor via
Multiply-dann-Add-Blend (funktioniert unabhängig von der Füllfarbe der
Quell-SVG), zweistufiger Cache (Rohsurface je Icon-Key, gerendertes Surface
je `(icon_key, size_px, color, angle_bucket)` mit 5°-Winkel-Bucketing),
`_warned_missing`-Set verhindert wiederholte Warnungen bei fehlender Datei,
Fallback auf ein generisches Icon statt Absturz.

**Bekannte Lücke, die `ui_icons.py` NICHT übernehmen darf**:
`aircraft_icons.py` hat kein `reset_cache()`, und `conftest.py`s
autouse-Fixture setzt ausschließlich `fonts.py`s Cache zurück —
`aircraft_icons.py`s Caches werden also nie zwischen Tests geleert. Das
neue `ui_icons.py` braucht laut Auftrag ein eigenes `reset_cache()` plus
Wiring in `conftest.py`. `aircraft_icons.py` selbst bleibt in diesem
Durchgang unangetastet.

## 2. Navigations-Inventar

`ActiveScreen`-Enum (`app.py:48–56`): `RADAR, DETAIL, CLOCK, ABOUT,
SETTINGS, TRACKING, WEATHER, WIFI`.

Tabelle direkt aus `app.py::_handle_gesture` (Zeilen 653–785) transkribiert:

| Screen | Geste / Ereignis | Aktion / Ziel | Zeile |
|---|---|---|---|
| RADAR | Tap auf Flugzeug | → DETAIL (+ Enrichment-Anfrage) | 658–665 |
| RADAR | Swipe runter | → CLOCK | 674–675 |
| RADAR | Swipe hoch | → ABOUT | 676–677 |
| RADAR | Swipe links | → SETTINGS | 678–679 |
| RADAR | Swipe rechts | → TRACKING | 680–681 |
| DETAIL | Tap → „radar" | → RADAR | 685–687 |
| DETAIL | Tap → „track" | → TRACKING, Callsign gemerkt | 688–693 |
| DETAIL | Tap → „untrack" | bleibt DETAIL | 694–696 |
| DETAIL | Swipe rechts/runter | → RADAR | 697–698 |
| DETAIL | Swipe hoch/links | Scrollt Inhalt (**keine** Navigation) | 699–702 |
| TRACKING | Tap „stop" | effektiv → RADAR (via `_end_tracking()`) | 705–709, 480–485 |
| TRACKING | Tap „radar" | → RADAR | 710–711 |
| TRACKING | Swipe rechts/runter | → RADAR | 712–713 |
| CLOCK | Swipe hoch | → RADAR | 716–717 |
| CLOCK | Swipe links | → SETTINGS | 718–719 |
| CLOCK | Swipe rechts | → WEATHER | 720–721 |
| WEATHER | Tap „radar" | → RADAR | 724–727 |
| WEATHER | Swipe links/runter | → CLOCK | 728–729 |
| ABOUT | Tap oder Swipe runter/rechts | → RADAR | 732–736 |
| SETTINGS | Tap „radar" | → RADAR | 739–742 |
| SETTINGS | Tap „wifi_setup" | → WIFI | 755–761 |
| SETTINGS | Swipe rechts | `go_back()` — eine Menüebene zurück, oder → RADAR auf Wurzelebene | 762–764 |
| SETTINGS | Swipe hoch/runter | Scrollt Liste (**keine** Navigation) | 765–768 |
| WIFI | Tap „radar" | → RADAR (+ 300 s Dismiss-Cooldown falls weiterhin `NEEDS_WIFI`) | 771–780 |
| WIFI | Swipe hoch/runter | Scrollt Liste (**keine** Navigation) | 781–784 |

**Sonderfälle** (nicht gestenbasiert): Escape-Taste im Entwicklungsbetrieb
(→ RADAR von jedem Überlagerungsscreen aus, sonst App-Ende, 237–245);
automatischer Rücksprung zur Uhr nach `auto_clock_s` Inaktivität (281–286);
automatischer WLAN-Screen bei Netzausfall, unabhängig von Gesten
(561–580); automatisches Verlassen von WIFI bei erfolgreicher Verbindung
(277–279); Tracking-Timeout/Landung beendet Tracking und wechselt nur dann
zu RADAR, wenn TRACKING gerade aktiv ist — andere Screens (z. B. CLOCK)
bleiben unangetastet (421–440, 480–486); kein eigener
Navigations-Zweig für den Nachtmodus (Dimmung ist reines Rendering über
`apply_dim_overlay` in `_compose_frame`).

**Footer-Buttons je Screen** (gerendert von `nav.py`, Kinds-Liste je
Screen):

| Screen | Footer-Buttons | Quelle |
|---|---|---|
| Radar | keine | — |
| Detail | `prev`/`next` (bei mehreren Flugzeugen) + `track`/`untrack` (bei bekanntem Callsign) + `radar` immer zuletzt | `detail.py:85–93` |
| Tracking | `stop`+`radar`, oder nur `radar` ohne aktives Tracking | `tracking.py:79–80` |
| Clock | keine | — |
| About | `radar` (fix) | `about.py:82` |
| Settings/Menu | kein `nav`-Footer — eigenes `_back_rect`-Icon | `menu.py:410–413, 502–504` |
| Weather | ein Footer-Rect als kombinierter Tap-Ziel-/Seitenindikator → „radar" | `weather.py:336–357` |
| Wifi | eigene Chrome (`_back_rect`, `_reload_rect`, `_eye_rect`, Bildschirmtastatur) | `wifi.py:202–205, 338–361` |

Labels (`nav.py:261–264`): `prev`→„ZURÜCK", `next`→„WEITER",
`radar`→„RADAR", `track`→„FOLGEN", `untrack`/`stop`→„STOPP".

Tests, die diesen Graphen heute abbilden (werden in Schritt 3 angepasst,
nicht jetzt): `test_app_tracking.py` (Tracking-Lifecycle-Übergänge),
`test_app_weather.py::TestClockToWeatherNavigation` (treibt
`_handle_gesture` direkt mit gemockten Screens). Keine weitere Testdatei
referenziert `_handle_gesture`/`ActiveScreen`.

## 3. Inkonsistenzen (verifizierte Befunde)

1. **Swipe hoch bedeutet je nach Screen etwas anderes**: RADAR→ABOUT
   (`app.py:676–677`) vs. CLOCK→RADAR (`app.py:716–717`) — dieselbe Geste,
   unterschiedliches Ziel.
2. **Swipe links bedeutet je nach Screen etwas anderes**: RADAR→SETTINGS
   (`app.py:678–679`) vs. WEATHER→CLOCK (`app.py:728–729`).
3. **„Scroll statt Navigation" ist kein reiner SETTINGS-Sonderfall,
   sondern auch DETAIL betroffen** — Erweiterung der Ausgangsbeobachtung,
   kein Widerspruch: SETTINGS swipe-hoch/runter → `handle_scroll`
   (`app.py:765–768`), DETAIL swipe-hoch/links → `handle_scroll`
   (`app.py:699–702`). Zwei Screens, die dieselbe Geste bereits heute
   umdeuten, nicht nur einer.
4. **About dupliziert Settings→System** — bestätigt, nicht nur plausibel:
   `about.py` definiert `_hostname`/`_ip_address`; `menu.py` importiert
   exakt dieselben Funktionen (`from ...screens.about import _hostname,
   _ip_address`) und zeigt Version/Hostname/IP/Portal-URL im
   System-Untermenü — identischer Inhalt wie der About-Screen.
5. **`weather.py` dupliziert `nav.py`s Pagination-Punkte**:
   `_draw_screen_indicator` (`weather.py:336–347`) zeichnet eigene
   Seiten-Punkte statt `nav.draw_page_dots` (`nav.py:148–164`) zu
   importieren — gleiches visuelles Muster, doppelt implementiert.
6. **Fragilitäts-Hinweis, kein Bug**: Der „stop"-Tap auf TRACKING ruft
   `_end_tracking()` (`app.py:480–486`) auf, das `self._active` nur dann
   auf RADAR setzt, wenn `self._active` bereits `TRACKING` ist. Da der
   Tap-Handler ausschließlich im TRACKING-Zweig aufgerufen wird
   (`app.py:704–714`), ist diese Bedingung zum Aufrufzeitpunkt immer wahr
   — aktuell kein toter Code, aber eine implizite Kopplung zwischen
   Tap-Ort und Lifecycle-Methode, die bei einer künftigen Umstrukturierung
   (Schritt 3) leicht auseinanderfallen kann.
7. **Keinerlei Ortsanzeige**: Nirgends im UI ist erkennbar, wo man sich
   gerade befindet oder was als Nächstes kommt — belegt durch die
   vollständige Gesten-Tabelle in Abschnitt 2, die ausschließlich über
   auswendig gelernte Wischrichtungen navigierbar ist.

## 4. Screenshot-Harness

`flugradar/tools/screenshots.py`, aufrufbar per
`python -m flugradar.tools.screenshots [--theme amber|mono] [--out-dir docs/ui]`.

Baut **keine** `RadarApp`-Instanz und ruft nie `.run()` auf — das würde
echte Hintergrundarbeit anstoßen (ADS-B-/Wetter-Polling, Kachel-Fetches,
WLAN-Scan-/Connect-Threads). Stattdessen werden die einzelnen
Screen-Objekte direkt konstruiert, exakt wie `RadarApp.run()` es tut
(`app.py:131–166`), mit `DemoSource` für Flugzeugdaten und von Hand gebauten
Wetter-/Netzwerk-Demodaten für die übrigen Screens. Komposition
(Dim-Overlay + Kreismaske + Bezel) bildet `_compose_frame` +
`CircularViewport.apply(show_bezel=True)` nach — ohne Crossfade, da es in
einem Einzelbild-Lauf keinen Vorgängerframe gibt.

Erzeugte Screenshots unter `docs/ui/`:

| Datei | Zustand |
|---|---|
| `radar.png` | Radar mit 12 Demo-Flugzeugen |
| `detail.png` | Flugdetail, kein Tracking aktiv |
| `detail_tracked.png` | Flugdetail, Callsign getrackt (Footer zeigt „STOPP") |
| `clock.png` | Uhr-Screen mit Demo-Wetter |
| `about.png` | About-Screen |
| `settings.png` | Einstellungsmenü, Wurzelebene |
| `tracking.png` | Getrackter Flug, aktiv/in Reichweite |
| `tracking_no_flight.png` | Kein Flug getrackt (Fallback-Zustand) |
| `weather.png` | Wetter-Screen mit 5-Tage-Vorhersage |
| `wifi.png` | WLAN-Netzwerkliste (3 Demo-Netze, Scan-Thread umgangen) |

**Offener Punkt**: pygame ist in dieser Entwicklungsumgebung nicht
installiert — der Harness wurde geschrieben und gegen die tatsächlichen
Konstruktor-/Draw-Signaturen der Screens geprüft, aber ob er wirklich
fehlerfrei läuft und Maske/Bezel korrekt sitzen, muss auf deinem
Gerät/Entwicklungsrechner mit installiertem pygame verifiziert werden.

## Was in Schritt 0 nicht passiert ist

Kein `ui_icons.py`, keine `display/ui/`-Komponenten, keine
Navigations-Änderung, keine Änderung an `aircraft_icons.py` — nur diese
Dokumentation und der Screenshot-Harness. Schritt 1 beginnt erst nach
Rückmeldung zu Abschnitt 3.
