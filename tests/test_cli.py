import json

import pytest

from turath_match import cli


def test_help_teaches(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert "scheme:location" in out and "turath-match demo" in out


def test_demo(tmp_path, capsys):
    assert cli.main(["demo", "-o", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "have: 4" in out and (tmp_path / "report.html").exists()


def test_explain(capsys):
    assert cli.main(["explain", "فتح الباري بشرح صحيح البخاري|ابن حجر", "صحيح البخاري|البخاري"]) == 0
    assert "commentary" in capsys.readouterr().out
    assert cli.main(["explain", "الرسالة|الشافعي|أحمد شاكر", "الرسالة|الشافعي|رفعت فوزي"]) == 0
    assert "edition: different" in capsys.readouterr().out


def test_reconcile_scan_export_provenance(tmp_path, capsys):
    lib = tmp_path / "Books"
    lib.mkdir()
    (lib / "كليلة ودمنة - ابن المقفع.pdf").write_bytes(b"%PDF" + b"0" * 200_000)
    (lib / "copy.pdf").write_bytes(b"%PDF" + b"0" * 200_000)
    items = tmp_path / "items.jsonl"
    items.write_text(
        json.dumps(
            {
                "identifier": "k1",
                "title": "كليلة ودمنة",
                "creator": "ابن المقفع",
                "files": [{"name": "k.pdf", "size": 200_004}],
            },
            ensure_ascii=False,
        )
        + "\n",
        "utf-8",
    )
    wl = tmp_path / "w.csv"
    wl.write_text("title,author\nكليلة ودمنة,عبد الله بن المقفع\nالأدب الكبير,ابن المقفع\n", "utf-8")
    out = tmp_path / "out"
    assert (
        cli.main(
            ["reconcile", "-l", f"folder:{lib}", "-t", f"csv:{wl}", "-c", f"archive:{items}", "-o", str(out)]
        )
        == 0
    )
    assert "have: 1" in capsys.readouterr().out
    assert cli.main(["scan", str(lib), "-o", str(tmp_path / "lib.jsonl")]) == 0
    assert cli.main(["export", f"csv:{wl}", "-o", str(tmp_path / "w.jsonl")]) == 0
    assert (
        cli.main(
            [
                "provenance",
                "-l",
                f"jsonl:{tmp_path / 'lib.jsonl'}",
                "-s",
                f"archive:{items}",
                "-o",
                str(tmp_path / "p.tsv"),
            ]
        )
        == 0
    )
    assert (tmp_path / "p.tsv").read_text("utf-8").count("archive:k1") == 2
    plan = tmp_path / "dedupe.tsv"
    assert cli.main(["dups", str(lib), "--json", str(tmp_path / "d.json"), "--plan", str(plan)]) == 0
    rows = plan.read_text("utf-8").splitlines()
    assert rows[1] == f"#planfs target {lib.resolve()}"  # planfs finds the folder without -t
    assert rows[2] == "action\tfrom\tto\treason" and rows[3].startswith("delete\t")
    assert "duplicate of" in rows[3] and len(rows) == 4
    assert len(json.loads((tmp_path / "d.json").read_text())[0]["paths"]) == 2


def test_errors_are_friendly(tmp_path, capsys):
    assert cli.main(["reconcile", "-l", str(tmp_path / "nope.bin"), "-t", "csv:x.csv"]) == 2
    assert "scheme:path" in capsys.readouterr().err


def test_fetch_uses_polite_cache(tmp_path, monkeypatch, capsys):
    from turath_match import net

    from .conftest import FakeTransport

    t = FakeTransport(
        {
            "advancedsearch": "archive_search.json",
            "_files.xml": "archive_files.xml",
            "page=1&": "waqfeya_page1.json",
            "page=2&": "waqfeya_page2.json",
            "zenodo.org": b"version_uri\tbook\n",
        }
    )
    monkeypatch.setattr(net, "urllib_transport", t)
    monkeypatch.setattr(net.Http, "__init__.__defaults__", None, raising=False)
    common = ["--cache", str(tmp_path / "c"), "--interval", "0"]
    assert (
        cli.main(["fetch", "archive", "--search", "كليلة ودمنة|", "-o", str(tmp_path / "a.jsonl"), *common])
        == 0
    )
    assert cli.main(["fetch", "waqfeya", "--max-pages", "1", "-o", str(tmp_path / "w.jsonl"), *common]) == 0
    assert len((tmp_path / "w.jsonl").read_text("utf-8").splitlines()) == 2
    assert cli.main(["fetch", "openiti", "-o", str(tmp_path / "o.tsv"), *common]) == 0
    assert (tmp_path / "o.tsv").read_bytes().startswith(b"version_uri")
    assert "cite:" in capsys.readouterr().out


def test_shamela_cards_explains_requirements(tmp_path, capsys):
    assert cli.main(["shamela-cards", "--path", str(tmp_path), "-o", str(tmp_path / "c.jsonl")]) == 2
    assert "Java" in capsys.readouterr().err
