# UI-Icons — Quelle

**Set**: [Lucide](https://lucide.dev) (ISC-Lizenz, Fork von
[Feather Icons](https://feathericons.com), MIT). Siehe `LICENSE.txt` —
enthält den vollständigen Lucide-ISC-Text sowie, für die davon abgeleiteten
Feather-Icons, zusätzlich den Feather-MIT-Text mit der Liste der
betroffenen Icon-Namen (darunter `chevron-left`, `chevron-right`, `lock` —
diese drei stehen zusätzlich unter der Feather-MIT-Lizenz).

**Bezogen von**: `https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/<name>.svg`
(GitHub, Branch `main`).

**Abrufdatum**: 2026-08-22.

**Version**: entspricht `lucide-static@1.33.0` (npm-Registry-Abfrage zum
Abrufdatum — die Icon-SVGs selbst sind zwischen `lucide` und
`lucide-static` identisch, nur das Vertriebspaket unterscheidet sich).

Nur die tatsächlich im UI verwendeten Dateien liegen hier, nicht das
komplette Set (Lucide hat >1000 Icons).

## Übernommene Dateien und Verwendung

| Datei | Verwendet für |
|---|---|
| `chevron-left.svg` | Zurück-Navigation (Menü-/WLAN-Header), Footer-Button „Zurück" |
| `chevron-right.svg` | Footer-Button „Weiter" |
| `radar.svg` | Footer-Button „Radar" |
| `lock.svg` | Gesichertes Netzwerk in der WLAN-Liste |
| `eye.svg` | Passwort sichtbar (WLAN-Einrichtung) |
| `eye-off.svg` | Passwort verborgen (WLAN-Einrichtung) |
| `refresh-cw.svg` | WLAN-Netzwerkliste neu scannen (rotiert während des Scans) |
| `loader-circle.svg` | Verbindungsaufbau-Spinner (WLAN, rotiert während des Aufbaus) |
| `signal.svg` | WLAN-Signalstärke, volle Stärke (Bucket 4/4) |
| `signal-high.svg` | WLAN-Signalstärke, stark (Bucket 3/4) |
| `signal-medium.svg` | WLAN-Signalstärke, mittel (Bucket 2/4) |
| `signal-low.svg` | WLAN-Signalstärke, schwach (Bucket 1/4) |

Geladen und eingefärbt über `flugradar/display/ui_icons.py` — siehe dessen
Modul-Docstring für die Details zur `currentColor`-Ersetzung und zum
Rastern in Zielgröße.
