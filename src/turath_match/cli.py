"""Command line: ``turath-match <command> --help`` explains each command with an example."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from importlib import resources
from pathlib import Path

from . import __version__
from .dups import find_duplicates, scan_sizes
from .edition import match_edition
from .models import Record
from .provenance import SizeIndex, trace
from .reconcile import load_decisions, reconcile
from .report import write_reports
from .sources import open_source, save_jsonl, schemes
from .sources.archive import ArchiveOrg
from .text import BACKEND
from .work import match_work

EPILOG = """\
sources are written scheme:location —
  csv:my-books.csv           a CSV/TSV inventory or wish list (title, author, editor, publisher, volumes, size …)
  folder:~/Books             a folder of PDFs/EPUBs (names read as «title - author - ت editor - ط publisher»)
  folder:~/Books::warraq     the same with a naming profile (smart, warraq, title, pattern:{title} - {author})
  openiti:meta.tsv           an OpenITI release metadata file (turath-match fetch openiti)
  archive:items.jsonl        archive.org items with exact file sizes (turath-match fetch archive)
  waqfeya:dump.jsonl         a Waqfeya dump (turath-match fetch waqfeya)
  shamela:~/shamela          the catalog of YOUR local Shamela install, read-only
  jsonl:records.jsonl        records saved by turath-match scan/export

start with:  turath-match demo
"""


def _load(specs: list[str]) -> list[Record]:
    out: list[Record] = []
    for s in specs:
        out.extend(open_source(s).records())
    return out


def _http(args: argparse.Namespace):
    from .net import Http

    return Http(
        getattr(args, "cache", None),
        min_interval=getattr(args, "interval", 1.0),
        offline=getattr(args, "offline", False),
    )


def _record_from(arg: str, scheme: str) -> Record:
    parts = [p.strip() for p in arg.split("|")]
    keys = ["title", "author", "editor", "publisher", "year"]
    d = dict(zip(keys, parts[: len(keys)], strict=False))
    return Record(
        scheme,
        scheme[0].upper(),
        d.get("title", ""),
        d.get("author", ""),
        editor=d.get("editor", ""),
        publisher=d.get("publisher", ""),
        year=d.get("year", ""),
    )


def cmd_explain(a: argparse.Namespace) -> int:
    left, right = _record_from(a.left, "left"), _record_from(a.right, "right")
    m = match_work(left, right)
    print(m.explain())
    if a.edition or left.editor or right.editor or left.publisher or right.publisher:
        print()
        print(match_edition(left, right).explain())
    return 0


def _run(
    library: list[Record],
    targets: list[Record],
    copies: list[Record],
    out: Path,
    *,
    title: str,
    decisions: str | None = None,
    online: bool = False,
    args: argparse.Namespace | None = None,
) -> int:
    t0 = time.perf_counter()
    rec = reconcile(
        library,
        targets,
        copies,
        decisions=load_decisions(decisions) if decisions else None,
        online=ArchiveOrg(_http(args)) if online and args else None,
    )
    secs = time.perf_counter() - t0
    paths = rec.write(out)
    md, ht = write_reports(rec, out, title)
    c = rec.counts()
    print(f"{len(targets)} records checked against {len(library)} library books in {secs:.2f} s")
    print("  " + "  ".join(f"{k}: {v}" for k, v in c.items()))
    ev = sum(1 for m in rec.matches if m.evidence)
    print(f"  {len(rec.matches)} matches written, {ev} with evidence; {len(rec.review())} on the review list")
    for p in (*paths.values(), md, ht):
        print(f"  {p}")
    return 0


def cmd_reconcile(a: argparse.Namespace) -> int:
    lib = _load(a.library)
    targets = _load(a.targets)
    copies = _load(a.copies or [])
    return _run(
        lib, targets, copies, Path(a.out), title=a.title, decisions=a.decisions, online=a.online, args=a
    )


def cmd_demo(a: argparse.Namespace) -> int:
    d = resources.files("turath_match") / "demo"
    with resources.as_file(d) as p:
        lib = _load([f"csv:{p / 'library.csv'}"])
        for r in lib:
            r.scheme = "library"
        wl = _load([f"csv:{p / 'wishlist.csv'}"])
        for r in wl:
            r.scheme = "wishlist"
        copies = _load([f"archive:{p / 'archive.jsonl'}", f"openiti:{p / 'openiti.tsv'}"])
    print(
        "demo: a 10-book library and a 10-work wish list, against 11 archive.org items and 27 OpenITI texts\n"
    )
    rc = _run(lib, wl, copies, Path(a.out), title="turath-match demo")
    if a.open:
        import webbrowser

        webbrowser.open((Path(a.out) / "report.html").resolve().as_uri())
    return rc


def cmd_scan(a: argparse.Namespace) -> int:
    from .sources.folder import FolderSource

    n = save_jsonl(FolderSource(a.folder, a.profile).records(), a.out)
    print(f"{n} books -> {a.out}")
    return 0


def cmd_export(a: argparse.Namespace) -> int:
    n = save_jsonl(_load(a.source), a.out)
    print(f"{n} records -> {a.out}")
    return 0


def cmd_provenance(a: argparse.Namespace) -> int:
    lib = _load(a.library)
    idx = SizeIndex(_load(a.source))
    ms = trace(lib, idx, verify=a.verify)
    fh = open(a.out, "w", encoding="utf-8", newline="") if a.out else sys.stdout  # noqa: SIM115
    try:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(
            [
                "library",
                "file",
                "size",
                "verdict",
                "method",
                "score",
                "source",
                "source_file",
                "url",
                "evidence",
            ]
        )
        for m in ms:
            lf, sf = m.left.files[0], m.right.files[0]
            w.writerow(
                [
                    m.left.key,
                    lf.name,
                    lf.size,
                    m.verdict,
                    m.method,
                    f"{m.score:.2f}",
                    m.right.key,
                    sf.name,
                    sf.url or m.right.url,
                    " | ".join(e.detail for e in m.evidence),
                ]
            )
    finally:
        if fh is not sys.stdout:
            fh.close()
    n_files = sum(len(r.files) for r in lib)
    print(
        f"{len(ms)} of {n_files} files traced to a source file ({len(idx)} source files indexed)",
        file=sys.stderr,
    )
    return 0


def cmd_dups(a: argparse.Namespace) -> int:
    entries = scan_sizes(a.folder)
    groups = find_duplicates(entries, deep=a.deep, workers=a.workers)
    for g in groups:
        print(f"{g.size:>12,}  {g.method:<13} {len(g.paths)} copies")
        for p in g.paths:
            print(f"              {p}")
    if a.plan:
        root = Path(a.folder)
        with open(a.plan, "w", encoding="utf-8", newline="") as fh:
            fh.write(f"#planfs name dedupe-{time.strftime('%Y%m%d')}\naction\tfrom\tto\treason\n")
            for g in groups:
                keep, *rest = sorted(g.paths, key=lambda p: (len(p), p))
                for p in rest:
                    why = "same SHA-256" if g.method == "hash" else "same size and five sampled 64 KB windows"
                    fh.write(
                        f"delete\t{Path(p).relative_to(root)}\t\tduplicate of {Path(keep).relative_to(root)} "
                        f"({g.size} bytes, {why})\n"
                    )
        print(
            f"planfs plan -> {a.plan} (preview: planfs plan {a.plan}; deletes go to quarantine)",
            file=sys.stderr,
        )
    if a.json:
        Path(a.json).write_text(
            json.dumps([g.to_dict() for g in groups], ensure_ascii=False, indent=1), "utf-8"
        )
    print(f"{len(groups)} duplicate group(s) among {len(entries)} files", file=sys.stderr)
    return 0


def cmd_fetch(a: argparse.Namespace) -> int:
    http = _http(a)
    if a.what == "openiti":
        from .sources.openiti import CITATION, METADATA_URL, fetch_metadata

        p = fetch_metadata(http, a.url or METADATA_URL, a.out)
        print(f"OpenITI metadata -> {p}\ncite: {CITATION}")
    elif a.what == "archive":
        arch = ArchiveOrg(http, rows=a.rows)
        recs: list[Record] = []
        for q in a.search or []:
            t, _, au = q.partition("|")
            recs += arch.search(t.strip(), au.strip())
        if a.ids:
            recs += list(arch.items(i.strip() for i in Path(a.ids).read_text().split() if i.strip()))
        with open(a.out, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(
                    json.dumps(
                        {
                            "identifier": r.id,
                            "title": r.title,
                            "creator": r.author,
                            "date": r.year,
                            "files": [f.to_dict() for f in r.files],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        print(f"{len(recs)} archive.org items -> {a.out} ({http.requests} requests)")
    elif a.what == "waqfeya":
        from .sources.waqfeya import Waqfeya

        wq = Waqfeya(http)
        n = 0
        with open(a.out, "w", encoding="utf-8") as fh:
            for raw in wq.fetch_catalog(a.max_pages):
                if a.details:
                    raw = wq.fetch_detail(raw)
                fh.write(json.dumps(raw, ensure_ascii=False) + "\n")
                n += 1
        print(f"{n} Waqfeya records -> {a.out} ({http.requests} requests)")
    return 0


def cmd_shamela_cards(a: argparse.Namespace) -> int:
    """Export your Shamela's book cards with Shamela's own Java and Lucene jars (read-only, on a copy)."""
    import glob
    import tempfile

    home = Path(a.path).expanduser()
    java = (
        a.java
        or next((j for j in sorted(glob.glob(str(home / "app/*/*/jre/*/bin/java")), reverse=True)), None)
        or shutil.which("java")
    )
    jars = sorted(glob.glob(str(home / "app/lucene/*/*.jar")))
    tool = Path(a.tool)
    store = home / "database/store/book"
    if not (java and jars and store.is_dir() and (tool / "Dump.class").exists()):
        print(
            "needs: Shamela's database/store/book, its app/lucene jars, Java >= 21, and tools/shamela-dump/Dump.class "
            "(javac tools/shamela-dump/Dump.java)",
            file=sys.stderr,
        )
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        cp = Path(tmp) / "idx"
        shutil.copytree(store, cp)
        (cp / "write.lock").unlink(missing_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            subprocess.run([java, "-cp", f"{tool}:{':'.join(jars)}", "Dump", str(cp)], stdout=fh, check=True)
    print(f"cards -> {a.out}  (use: shamela:{home}::{a.out})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="turath-match",
        description="Which of these works and editions do I already have, which are missing, and where is a "
        "trustworthy copy? Every answer comes with its evidence.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"turath-match {__version__} (text: {BACKEND})")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")

    def add(name: str, fn, help_: str, example: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(
            name,
            help=help_,
            description=help_,
            epilog="example:\n  " + example,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        sp.set_defaults(fn=fn)
        return sp

    sp = add(
        "demo", cmd_demo, "run on the bundled demo library and write a report", "turath-match demo --open"
    )
    sp.add_argument("-o", "--out", default="turath-demo")
    sp.add_argument("--open", action="store_true", help="open report.html in the browser")

    sp = add(
        "reconcile",
        cmd_reconcile,
        "reconcile a library with catalogs and find copies of what is missing",
        "turath-match reconcile -l folder:~/Books -t csv:wishlist.csv -c archive:items.jsonl -o out/",
    )
    sp.add_argument("-l", "--library", action="append", required=True, help="your books (repeatable)")
    sp.add_argument(
        "-t",
        "--targets",
        action="append",
        required=True,
        help="what to check: a wish list or a whole catalog (repeatable)",
    )
    sp.add_argument("-c", "--copies", action="append", help="where to look for copies (repeatable)")
    sp.add_argument(
        "-d", "--decisions", help="review.tsv with a filled «decision» column (same/different/related)"
    )
    sp.add_argument(
        "--online", action="store_true", help="also search archive.org for missing works (cached)"
    )
    sp.add_argument("--cache", help="HTTP cache folder (default ~/.cache/turath-match)")
    sp.add_argument("--title", default="turath-match report")
    sp.add_argument("-o", "--out", default="turath-out")

    sp = add(
        "explain",
        cmd_explain,
        "compare two records and print every reason",
        'turath-match explain "فتح الباري|ابن حجر" "صحيح البخاري|البخاري"',
    )
    sp.add_argument("left", help="title|author|editor|publisher|year")
    sp.add_argument("right")
    sp.add_argument("--edition", action="store_true", help="also compare editions")

    sp = add(
        "scan",
        cmd_scan,
        "read a folder of books into records (sizes only; nothing is opened)",
        "turath-match scan ~/Books --profile warraq -o library.jsonl",
    )
    sp.add_argument("folder")
    sp.add_argument("--profile", default="smart")
    sp.add_argument("-o", "--out", default="library.jsonl")

    sp = add(
        "export",
        cmd_export,
        "save any source as JSONL records",
        "turath-match export shamela:~/shamela -o sh.jsonl",
    )
    sp.add_argument("source", nargs="+")
    sp.add_argument("-o", "--out", required=True)

    sp = add(
        "provenance",
        cmd_provenance,
        "trace each local file to its source file by exact size",
        "turath-match provenance -l folder:~/Books -s archive:items.jsonl --verify -o prov.tsv",
    )
    sp.add_argument("-l", "--library", action="append", required=True)
    sp.add_argument("-s", "--source", action="append", required=True)
    sp.add_argument("--verify", action="store_true", help="hash local files where the source gives md5/sha1")
    sp.add_argument("-o", "--out")

    sp = add(
        "dups",
        cmd_dups,
        "prove duplicate files by size and five sampled 64 KB windows",
        "turath-match dups ~/Books --deep",
    )
    sp.add_argument("folder")
    sp.add_argument("--deep", action="store_true", help="confirm each group with a full SHA-256")
    sp.add_argument("--workers", type=int, default=4)
    sp.add_argument("--json")
    sp.add_argument(
        "--plan", help="write a planfs plan that deletes every copy but one (nothing is deleted here)"
    )

    sp = add(
        "fetch",
        cmd_fetch,
        "download catalog metadata politely (cached, rate-limited)",
        'turath-match fetch archive --search "طوق الحمامة|ابن حزم" -o items.jsonl',
    )
    sp.add_argument("what", choices=["openiti", "archive", "waqfeya"])
    sp.add_argument("-o", "--out", required=True)
    sp.add_argument("--search", action="append", help='archive: "title|author" (repeatable)')
    sp.add_argument("--ids", help="archive: a file of item identifiers")
    sp.add_argument("--rows", type=int, default=25)
    sp.add_argument("--max-pages", type=int, help="waqfeya: stop after N pages of 100")
    sp.add_argument("--details", action="store_true", help="waqfeya: also read each book page (slow)")
    sp.add_argument("--url", help="openiti: another release's metadata URL")
    sp.add_argument("--cache")
    sp.add_argument("--interval", type=float, default=1.0, help="seconds between requests to one host")
    sp.add_argument("--offline", action="store_true", help="use the cache only")

    sp = add(
        "shamela-cards",
        cmd_shamela_cards,
        "export the book cards of your own Shamela install",
        "turath-match shamela-cards --path ~/.local/share/shamela -o cards.jsonl",
    )
    sp.add_argument("--path", required=True)
    sp.add_argument("--java")
    sp.add_argument("--tool", default="tools/shamela-dump")
    sp.add_argument("-o", "--out", default="shamela-cards.jsonl")

    sp = add(
        "sources",
        lambda a: print("\n".join(schemes())) or 0,
        "list the source schemes",
        "turath-match sources",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except (ValueError, FileNotFoundError) as e:
        print(f"turath-match: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
