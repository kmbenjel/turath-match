"""The reconciliation report: Markdown (for a repository or an issue) and one self-contained HTML page."""

from __future__ import annotations

import html
from pathlib import Path

from .models import Match
from .reconcile import NEEDS_COPY, STATUSES, Reconciliation, TargetStatus

LABELS = {
    "have": ("Have", "موجود"),
    "partial": ("Partial", "ناقص الأجزاء"),
    "have_work": ("Have the work", "الكتاب موجود والطبعة غير مؤكدة"),
    "other_edition": ("Other edition", "طبعة أخرى"),
    "related_only": ("Related work only", "عمل متصل به فقط"),
    "review": ("Review", "للمراجعة"),
    "missing": ("Missing", "مفقود"),
}
COLORS = {
    "have": "#1a7f37",
    "partial": "#7d6b00",
    "have_work": "#2f6f9f",
    "other_edition": "#8250df",
    "related_only": "#9a6700",
    "review": "#bc4c00",
    "missing": "#cf222e",
}


def _ev_line(m: Match) -> str:
    return "; ".join(e.detail for e in m.evidence)


def _main(t: TargetStatus) -> Match | None:
    return (
        t.edition
        if t.edition is not None
        else t.work
        if t.work is not None
        else (t.files[0] if t.files else None)
    )


def to_markdown(rec: Reconciliation, title: str = "turath-match report") -> str:
    c = rec.counts()
    out = [
        f"# {title}",
        "",
        f"{len(rec.targets)} catalog records checked against {len(rec.library)} library books.",
        "",
    ]
    out += ["| Status | الحالة | Records |", "|---|---|---:|"]
    out += [f"| {LABELS[s][0]} | {LABELS[s][1]} | {c[s]} |" for s in STATUSES]
    for s in STATUSES:
        rows = [t for t in rec.targets if t.status == s]
        if not rows:
            continue
        out += ["", f"## {LABELS[s][0]} · {LABELS[s][1]} ({len(rows)})", ""]
        for t in rows:
            m = _main(t)
            lib = t.library
            line = f"- **{t.target.title}** — {t.target.author or '?'} `{t.target.key}`"
            if lib is not None:
                line += f"  \n  library: {lib.title} ({lib.author or '?'})"
            if m is not None:
                line += f"  \n  {m.level} · {m.verdict} · {m.confidence} ({m.score:.2f}) via `{m.method}`: {_ev_line(m)}"
            for pm in t.provenance[:2]:
                line += f"  \n  file: {pm.left.files[0].name} is `{pm.right.key}` ({pm.right.files[0].name}, exact size)"
            for r in t.related[:2]:
                line += f"  \n  related: {r.right.title} — {r.relation}"
            for cp in t.copies[:3] if t.status in NEEDS_COPY else []:
                sz = cp.record.total_size
                line += (
                    f"  \n  copy: [{cp.record.title}]({cp.record.url}) `{cp.record.key}`"
                    + (f", {len(cp.record.files)} file(s), {sz:,} bytes" if sz else "")
                    + (" — same edition" if cp.edition and cp.edition.verdict == "same" else "")
                )
            out.append(line)
    rv = rec.review()
    if rv:
        out += ["", f"## Review list ({len(rv)})", "", "| left | right | score | why |", "|---|---|---:|---|"]
        for m in rv[:200]:
            why = _ev_line(m).replace("|", "/")
            out.append(f"| {m.left.title} | {m.right.title} | {m.score:.2f} | {why} |")
    if rec.identified_by_bytes:
        out += ["", f"## Library files identified by their bytes only ({len(rec.identified_by_bytes)})", ""]
        out += [
            f"- {m.left.title} — {m.left.author or '?'}: `{m.left.files[0].name}` is `{m.right.key}` "
            f"«{m.right.title}» {m.right.author or ''} ({m.method}, {m.score:.2f})"
            for m in rec.identified_by_bytes
        ]
    if rec.unidentified:
        out += ["", f"## Library books not found in any catalog ({len(rec.unidentified)})", ""]
        out += [f"- {r.title} — {r.author or '?'}" for r in rec.unidentified]
    return "\n".join(out) + "\n"


CSS = """
:root{--bg:#fbfaf7;--fg:#1f2328;--mut:#59636e;--card:#fff;--line:#e3e0d8;--pos:#1a7f37;--neg:#cf222e;--neu:#6e7781}
@media (prefers-color-scheme:dark){:root{--bg:#14161a;--fg:#e6e6e6;--mut:#9aa4ae;--card:#1c1f24;--line:#30353c;
--pos:#3fb950;--neg:#f85149;--neu:#8b949e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 "Noto Naskh Arabic","Amiri","Segoe UI",system-ui,sans-serif}
main{max-width:1060px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:32px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.sub{color:var(--mut);margin:0 0 18px}
.bar{display:flex;height:14px;border-radius:7px;overflow:hidden;margin:10px 0 6px}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--mut)}
.legend b{display:inline-block;width:10px;height:10px;border-radius:2px;margin-inline-end:5px;vertical-align:-1px}
.card{background:var(--card);border:1px solid var(--line);border-inline-start:4px solid var(--c);border-radius:8px;
padding:10px 14px;margin:8px 0}
.t{font-size:17px;font-weight:600}.a{color:var(--mut)}.k{font:12px ui-monospace,monospace;color:var(--mut)}
.row{margin-top:4px;font-size:14px}.tag{display:inline-block;font:12px ui-monospace,monospace;padding:1px 6px;
border-radius:10px;border:1px solid var(--line);margin-inline-end:4px}
ul.ev{list-style:none;margin:6px 0 0;padding:0;font-size:13.5px}ul.ev li{padding:1px 0}
ul.ev li:before{display:inline-block;width:1.2em;font-weight:700}
ul.ev li.p:before{content:"+";color:var(--pos)}ul.ev li.n:before{content:"−";color:var(--neg)}
ul.ev li.z:before{content:"·";color:var(--neu)}
.copy{font-size:13.5px;margin-top:3px}a{color:inherit}
"""


def _ev_html(m: Match) -> str:
    items = []
    for e in m.evidence:
        cls = "p" if e.weight > 0 else "n" if e.weight < 0 else "z"
        items.append(
            f'<li class="{cls}"><span class="k">{html.escape(e.kind)}</span> <bdi>{html.escape(e.detail)}</bdi></li>'
        )
    return '<ul class="ev">' + "".join(items) + "</ul>"


def to_html(rec: Reconciliation, title: str = "turath-match report") -> str:
    c = rec.counts()
    n = max(1, len(rec.targets))
    bar = "".join(
        f'<span style="width:{100 * c[s] / n:.2f}%;background:{COLORS[s]}" title="{LABELS[s][0]}: {c[s]}"></span>'
        for s in STATUSES
        if c[s]
    )
    legend = "".join(
        f'<span><b style="background:{COLORS[s]}"></b>{LABELS[s][0]} · {LABELS[s][1]}: {c[s]}</span>'
        for s in STATUSES
    )
    parts = [
        f'<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style>'
        f'</head><body><main dir="auto"><h1>{html.escape(title)}</h1>'
        f'<p class="sub">{len(rec.targets)} catalog records · {len(rec.library)} library books · '
        f"{sum(1 for m in rec.matches if m.evidence)} of {len(rec.matches)} matches carry evidence</p>"
        f'<div class="bar">{bar}</div><div class="legend">{legend}</div>'
    ]
    for s in STATUSES:
        rows = [t for t in rec.targets if t.status == s]
        if not rows:
            continue
        parts.append(f"<h2>{LABELS[s][0]} · {LABELS[s][1]} ({len(rows)})</h2>")
        for t in rows:
            m = _main(t)
            lib = t.library
            body = [
                f'<div class="t" dir="rtl">{html.escape(t.target.title)}</div>'
                f'<div class="a" dir="rtl">{html.escape(t.target.author or "?")} '
                f'<span class="k">{html.escape(t.target.key)}</span></div>'
            ]
            if lib is not None:
                body.append(f'<div class="row">library: <bdi>{html.escape(lib.title)}</bdi></div>')
            if m is not None:
                body.append(
                    f'<div class="row"><span class="tag">{m.level}</span><span class="tag">{m.verdict}</span>'
                    f'<span class="tag">{m.confidence} {m.score:.2f}</span><span class="tag">{m.method}</span></div>'
                )
                body.append(_ev_html(m))
            for pm in t.provenance[:2]:
                body.append(
                    f'<div class="copy">file: <bdi>{html.escape(pm.left.files[0].name)}</bdi> is '
                    f'<a href="{html.escape(pm.right.url)}"><span class="k">{html.escape(pm.right.key)}</span></a>'
                    f' <span class="k">exact size {pm.left.files[0].size:,} bytes</span></div>'
                )
            for r in t.related[:2]:
                body.append(
                    f'<div class="row">related: <bdi>{html.escape(r.right.title)}</bdi> '
                    f'<span class="tag">{html.escape(r.relation or "")}</span></div>'
                )
            for cp in t.copies[:3] if t.status in NEEDS_COPY else []:
                sz = cp.record.total_size
                same = " · same edition" if cp.edition and cp.edition.verdict == "same" else ""
                body.append(
                    f'<div class="copy">copy: <a href="{html.escape(cp.record.url)}"><bdi>'
                    f'{html.escape(cp.record.title)}</bdi></a> <span class="k">{html.escape(cp.record.key)}'
                    f"{f' · {sz:,} bytes' if sz else ''}{same}</span></div>"
                )
            parts.append(f'<div class="card" style="--c:{COLORS[s]}">{"".join(body)}</div>')
    if rec.identified_by_bytes:
        parts.append(f"<h2>Identified by their bytes · عُرفت بحجمها ({len(rec.identified_by_bytes)})</h2>")
        for m in rec.identified_by_bytes:
            parts.append(
                f'<div class="card" style="--c:#2f6f9f"><div class="t" dir="rtl">{html.escape(m.left.title)}'
                f'</div><div class="row">is <a href="{html.escape(m.right.url)}"><bdi>{html.escape(m.right.title)}'
                f'</bdi></a> <span class="k">{html.escape(m.right.key)}</span></div>{_ev_html(m)}</div>'
            )
    if rec.unidentified:
        parts.append(f"<h2>Not found in any catalog · لم يعثر عليه ({len(rec.unidentified)})</h2>")
        parts.append(
            "<ul>"
            + "".join(
                f'<li dir="rtl">{html.escape(r.title)} — {html.escape(r.author or "?")}</li>'
                for r in rec.unidentified
            )
            + "</ul>"
        )
    parts.append("</main></body></html>")
    return "".join(parts)


def write_reports(
    rec: Reconciliation, out: str | Path, title: str = "turath-match report"
) -> tuple[Path, Path]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    md, ht = out / "report.md", out / "report.html"
    md.write_text(to_markdown(rec, title), encoding="utf-8")
    ht.write_text(to_html(rec, title), encoding="utf-8")
    return md, ht
