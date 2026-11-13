"""Make the README media from real runs: the demo report, a terminal card of `explain`, the evidence diagram.

python bench/make_media.py            # writes docs/media/*.svg and examples/demo-report/*
(screenshots of the HTML report: bench/screenshots.sh, on a machine with Chrome)
"""

from __future__ import annotations

import html
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "docs" / "media"
PY = sys.executable

TERM_BG, TERM_FG, DIM, GREEN, RED, BLUE = "#14161a", "#e6e6e6", "#8b949e", "#3fb950", "#f85149", "#79c0ff"


def run(*args: str) -> str:
    return subprocess.run(
        [PY, "-m", "turath_match.cli", *args], capture_output=True, text=True, check=True, cwd=ROOT
    ).stdout


def terminal_svg(blocks: list[tuple[str, str]], path: Path, width: int = 1180) -> None:
    lines: list[tuple[str, str]] = []
    for cmd, out in blocks:
        lines.append(("cmd", "$ " + cmd))
        lines += [("out", x if len(x) <= 128 else x[:126] + " …") for x in out.rstrip("\n").split("\n")]
        lines.append(("out", ""))
    lh, top = 22, 46
    h = top + lh * len(lines) + 10
    rows = []
    for i, (kind, text) in enumerate(lines):
        y = top + i * lh
        color = BLUE if kind == "cmd" else TERM_FG
        s = text.lstrip()
        if kind == "out" and s.startswith("+ "):
            color = GREEN
        elif kind == "out" and s.startswith("- "):
            color = RED
        elif kind == "out" and s.startswith("· "):
            color = DIM
        rows.append(
            f'<text x="22" y="{y}" fill="{color}" xml:space="preserve" direction="ltr" '
            f'unicode-bidi="plaintext">{html.escape(text)}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h}" viewBox="0 0 {width} {h}" '
        f'font-family="DejaVu Sans Mono, Menlo, Consolas, monospace" font-size="14.5">'
        f'<rect width="100%" height="100%" rx="10" fill="{TERM_BG}"/>'
        f'<circle cx="22" cy="18" r="6" fill="#f85149"/><circle cx="42" cy="18" r="6" fill="#d29922"/>'
        f'<circle cx="62" cy="18" r="6" fill="#3fb950"/>' + "".join(rows) + "</svg>"
    )
    path.write_text(svg, "utf-8")


def evidence_svg(path: Path) -> None:
    """The three levels and what each one needs, as a static diagram (README and docs)."""
    W, H = 1180, 430

    def box(x: int, y: int, w: int, h: int, fill: str, stroke: str) -> str:
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )

    def t(x: int, y: int, s: str, size: float = 15, weight: str = "400", fill: str = "#1f2328") -> str:
        return (
            f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}">'
            f"{html.escape(s)}</text>"
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="Noto Naskh Arabic, Noto Sans, DejaVu Sans, sans-serif">',
        '<rect width="100%" height="100%" fill="#fbfaf7"/>',
        t(30, 40, "Every verdict carries its evidence", 22, "700"),
        t(
            30,
            66,
            "work → edition → file: each level needs its own proof; what cannot be proven goes to review",
            15,
            fill="#59636e",
        ),
    ]
    cols = [
        (
            "WORK",
            "same title AND same author",
            [
                "title words agree (alternative titles, subtitles)",
                "author: shuhra / nasab / nisba (arabic-bib)",
                "a common name alone proves nothing",
                "death years within 2 (12 with full names)",
                "مختصر · شرح · ذيل · رواية → related",
            ],
            "#2f6f9f",
            "#e8f1f8",
        ),
        (
            "EDITION",
            "same imprint, or the same bytes",
            [
                "exact file size or md5/sha1",
                "editor + publisher (or volumes) agree",
                "any field disagreeing → other edition",
                "a thesis or typed copy is not the print",
                "some volumes only → partial",
            ],
            "#8250df",
            "#f3eefc",
        ),
        (
            "FILE",
            "this file IS that source file",
            [
                "exact byte size, ≥ 100 KB",
                "several candidates → title decides",
                "--verify: md5/sha1 of the local file",
                "duplicates: size + 5 × 64 KB windows",
                "--deep: full SHA-256",
            ],
            "#1a7f37",
            "#eaf5ec",
        ),
    ]
    x = 30
    for name, head, items, stroke, fill in cols:
        parts.append(box(x, 92, 360, 260, fill, stroke))
        parts.append(t(x + 18, 124, name, 17, "700", stroke))
        parts.append(t(x + 18, 150, head, 15, "600"))
        for i, it in enumerate(items):
            parts.append(t(x + 18, 184 + i * 32, "• " + it, 14.5))
        x += 380
    parts += [
        box(30, 368, 1120, 44, "#fff4e5", "#bc4c00"),
        t(
            48,
            396,
            "uncertain → review.tsv with every reason · fill «decision» (same / different / related) · "
            "rerun with -d: your decisions are kept",
            15,
            "600",
            "#bc4c00",
        ),
    ]
    for x0 in (390, 770):
        parts.append(
            f'<path d="M{x0 + 2} 222 l16 0" stroke="#59636e" stroke-width="2"/>'
            f'<path d="M{x0 + 12} 216 l7 6 l-7 6" fill="none" stroke="#59636e" stroke-width="2"/>'
        )
    parts.append("</svg>")
    path.write_text("".join(parts), "utf-8")


def main() -> int:
    MEDIA.mkdir(parents=True, exist_ok=True)
    explain = [
        (
            'turath-match explain "فتح الباري|ابن حجر" "فتح الباري بشرح صحيح البخاري|ابن حجر العسقلاني"',
            run("explain", "فتح الباري|ابن حجر", "فتح الباري بشرح صحيح البخاري|ابن حجر العسقلاني"),
        ),
        (
            'turath-match explain "شرح صحيح مسلم|النووي" "صحيح مسلم|مسلم بن الحجاج"',
            run("explain", "شرح صحيح مسلم|النووي", "صحيح مسلم|مسلم بن الحجاج"),
        ),
        (
            'turath-match explain "الزهد|أحمد بن محمد بن حنبل" "الزهد|عبد الله بن المبارك"',
            run("explain", "الزهد|أحمد بن محمد بن حنبل", "الزهد|عبد الله بن المبارك"),
        ),
        (
            'turath-match explain "الرسالة|محمد" "الرسالة|محمد بن إدريس الشافعي"',
            run("explain", "الرسالة|محمد", "الرسالة|محمد بن إدريس الشافعي"),
        ),
    ]
    terminal_svg(explain, MEDIA / "explain.svg")
    out = ROOT / "examples" / "demo-report"
    if out.exists():
        shutil.rmtree(out)
    demo = run("demo", "-o", str(out))
    terminal_svg([("turath-match demo", demo.replace(str(out), "turath-demo"))], MEDIA / "demo.svg")
    evidence_svg(MEDIA / "evidence.svg")
    print("media:", *sorted(p.name for p in MEDIA.iterdir()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
