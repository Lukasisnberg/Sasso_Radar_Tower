"""Baut die gedruckte Bedienungsanleitung: Screenshots -> HTML -> PDF.

    python -m anleitung.build                 # kompletter Lauf
    python -m anleitung.build --ohne-bilder    # Screenshots überspringen,
                                                # vorhandene PNGs in bilder/
                                                # wiederverwenden
    python -m anleitung.build --vorschau       # nur den HTML-Pfad ausgeben,
                                                # zum Ansehen im Browser
    python -m anleitung.build --seiten-png     # zusätzlich jede PDF-Seite
                                                # als PNG zur Sichtprüfung
                                                # rendern (braucht PyMuPDF)

Chromiums Druckpfad kennt weder @page-Margin-Boxen (@top-center) noch
string-set/target-counter -- das Buch ist deshalb explizit paginiert
(anleitung/buch/anleitung.html: 36 einzelne .seite-Sections), nicht als
fließender Text. Siehe anleitung/README.md.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).parent
BUCH_DIR = HIER / "buch"
BILDER_DIR = HIER / "bilder"
OUT_DIR = HIER / "out"
HTML_QUELLE = BUCH_DIR / "anleitung.html"
WISCHKARTE_SVG = BUCH_DIR / "wischkarte.svg"
PDF_ZIEL = OUT_DIR / "Sasso-Radar-Tower-Anleitung.pdf"

CHROMIUM_KANDIDATEN = (
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
)

ERWARTETE_SEITEN = 36


def _find_chromium() -> str:
    for kandidat in CHROMIUM_KANDIDATEN:
        if Path(kandidat).exists():
            return kandidat
    raise SystemExit(
        "Kein headless Chromium gefunden (geprüft: "
        f"{', '.join(CHROMIUM_KANDIDATEN)}). PLAYWRIGHT_BROWSERS_PATH prüfen."
    )


def _render_screenshots() -> None:
    from anleitung import portal_shots, screenshots

    print("Geräte-Screenshots werden gerendert …", file=sys.stderr)
    geraet = screenshots.render_all(BILDER_DIR)
    print(f"  {len(geraet)} Geräte-Bilder", file=sys.stderr)

    print("Portal-Screenshots werden gerendert …", file=sys.stderr)
    portal = portal_shots.render_all(BILDER_DIR)
    print(f"  {len(portal)} Portal-Bilder", file=sys.stderr)


def _inline_wischkarte(html: str) -> str:
    """Ersetzt den {{WISCHKARTE_SVG}}-Platzhalter durch den tatsächlichen
    Inhalt von wischkarte.svg.

    Nicht per <img src="wischkarte.svg">: das hier verwendete gepackte,
    headless Chromium lädt lokale SVG-Dateien als <img>-Subressource über
    file:// nicht zuverlässig (leeres "gebrochenes Bild"-Icon, per Test
    bestätigt -- PNG-<img> aus demselben Verzeichnis funktioniert dagegen
    einwandfrei). Inline-SVG direkt im Dokument rendert zuverlässig.
    """
    svg = WISCHKARTE_SVG.read_text(encoding="utf-8")
    if "{{WISCHKARTE_SVG}}" not in html:
        raise SystemExit("Platzhalter {{WISCHKARTE_SVG}} nicht in anleitung.html gefunden")
    return html.replace("{{WISCHKARTE_SVG}}", svg)


def _build_html() -> Path:
    html = HTML_QUELLE.read_text(encoding="utf-8")
    html = _inline_wischkarte(html)
    gebaut = BUCH_DIR / "_gebaut.html"
    gebaut.write_text(html, encoding="utf-8")
    return gebaut


def _drucken(html_pfad: Path, pdf_pfad: Path) -> None:
    chromium = _find_chromium()
    pdf_pfad.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        chromium, "--headless", "--disable-gpu", "--no-sandbox",
        f"--print-to-pdf={pdf_pfad}", "--no-pdf-header-footer",
        "--virtual-time-budget=10000",
        f"file://{html_pfad.resolve()}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not pdf_pfad.exists():
        raise RuntimeError(f"Chromium-Druck fehlgeschlagen:\n{result.stderr}")


def _pdf_kennzahlen(pdf_pfad: Path) -> tuple[int, tuple[float, float]]:
    """Seitenzahl + MediaBox (mm) direkt aus den PDF-Bytes lesen -- kein
    PDF-Toolkit als Abhängigkeit nötig, dieselbe Methode wie bei der
    Vorprüfung dieses Plans."""
    daten = pdf_pfad.read_bytes()
    seiten = len(re.findall(rb"/Type\s*/Page[^s]", daten))
    m = re.search(rb"/MediaBox\s*\[([^\]]*)\]", daten)
    if not m:
        raise RuntimeError("Keine /MediaBox im PDF gefunden")
    box = [float(x) for x in m.group(1).split()]
    breite_mm = box[2] / 72 * 25.4
    hoehe_mm = box[3] / 72 * 25.4
    return seiten, (breite_mm, hoehe_mm)


def _pruefen(pdf_pfad: Path) -> None:
    seiten, (breite_mm, hoehe_mm) = _pdf_kennzahlen(pdf_pfad)
    print(f"Seiten: {seiten}", file=sys.stderr)
    print(f"Format: {breite_mm:.1f} × {hoehe_mm:.1f} mm", file=sys.stderr)

    if seiten != ERWARTETE_SEITEN:
        raise SystemExit(
            f"Erwartet {ERWARTETE_SEITEN} Seiten, PDF hat {seiten} -- "
            "Seitenzahl in anleitung.html geändert, ohne den Seitenplan "
            "(anleitung/README.md) nachzuziehen?"
        )
    if seiten % 4 != 0:
        raise SystemExit(f"{seiten} Seiten ist nicht durch 4 teilbar -- als Broschüre nicht heftbar")
    if abs(breite_mm - 148.0) > 1.0 or abs(hoehe_mm - 210.0) > 1.0:
        raise SystemExit(f"Format {breite_mm:.1f}×{hoehe_mm:.1f} mm weicht von A5 (148×210 mm) ab")


def _seiten_png(pdf_pfad: Path) -> None:
    try:
        import fitz  # PyMuPDF -- nur für diese optionale Sichtprüfung
    except ImportError:
        raise SystemExit("--seiten-png braucht PyMuPDF: pip install pymupdf")
    ziel = OUT_DIR / "seiten"
    ziel.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_pfad)
    for i, seite in enumerate(doc, start=1):
        pix = seite.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        pix.save(ziel / f"seite_{i:02d}.png")
    print(f"{len(doc)} Seiten-PNGs in {ziel}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ohne-bilder", action="store_true", help="Screenshot-Schritt überspringen")
    ap.add_argument("--vorschau", action="store_true", help="nur den HTML-Pfad ausgeben, nicht drucken")
    ap.add_argument("--seiten-png", action="store_true", help="jede PDF-Seite zusätzlich als PNG speichern")
    args = ap.parse_args()

    if not args.ohne_bilder:
        _render_screenshots()
    else:
        print("Screenshot-Schritt übersprungen (--ohne-bilder)", file=sys.stderr)

    html_pfad = _build_html()

    if args.vorschau:
        print(html_pfad)
        return

    _drucken(html_pfad, PDF_ZIEL)
    _pruefen(PDF_ZIEL)
    print(f"Fertig: {PDF_ZIEL}", file=sys.stderr)

    if args.seiten_png:
        _seiten_png(PDF_ZIEL)


if __name__ == "__main__":
    main()
