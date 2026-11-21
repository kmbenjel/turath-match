# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Candidates by author: a title made of words half the catalog holds («تاريخ الإسلام», «الأمالي», «السنة») is
  compared with the records that share one of its words and a distinctive word of its author's name.
- Titles: an edition written with no dash («البعث والنشور للبيهقي ت الشوامي», «التبيان ط عالم الفوائد») and a
  publisher after the dash with no «ط» («تفسير النسفي - دار النفائس») become editor and publisher hints; what a
  digital library says about its own copy («موافق للمطبوع», «مشكول», «نسخة أخرى», an alternative «= مقابل») is
  not part of the title.
- A death year given only in the Gregorian calendar («ت 1997 م») compares with a Hijri one.
- `turath-match explain --json`: the work and edition verdicts with their evidence, for scripts.
- `dups --plan`: a name marked as a second copy («- Copy», «(1)», «Copy of …», «نسخة ثانية») loses the tie, and
  the mark is not read as a name part.
- The OpenITI adapter decodes HTML entities and line marks in titles and authors.

### Changed
- Author agreement follows arabic-bib's current rules: old spellings of a name meet («إسحق» / «إسحاق»), the asides of
  long catalog forms are set aside, and a man named after a relative («سبط ابن الجوزي») is another author.
- With arabic-bib's faster keys and name parsing, comparing the same pairs takes about a third of the time (the
  237,812 pairs of the OpenITI benchmark: 154 s before, 53 s after, 14 workers on one server).
- Benchmarks of 2026-11-21 against those of 2026-11-13: work level on OpenITI (development) 0.984 precision and
  0.834 recall (0.984 and 0.812); held out, Wikidata records against OpenITI, 0.981 and 0.755 (0.980 and 0.727)
  with no more wrong pairs (28); the 500-book library finds 380 books (376) and leaves 82 items for a person (80).
- The crosswalk names a work cluster after its plainest full title («رسالة الغفران», not the title that carries
  an edition note).
- Command line: no command prints the whole help; `dups` on a path that is not a folder, an unknown source scheme
  and an offline fetch that is not in the cache are one-line errors; output is UTF-8 on consoles with a legacy code
  page.
- `[tool.uv.sources]` takes arabic-bib from its repository, so `uvx --from git+https://github.com/kmbenjel/turath-match
  turath-match` runs on a clean machine.

## [0.1.0] - 2026-11-13

### Added
- Work-level matching: title analysis (alternative titles, subtitles, edition tails, joined works, the author's
  name inside a title) and author agreement through arabic-bib; abridgements, commentaries, selections,
  continuations, recensions and parts are reported as *related*, never as the work.
- Edition-level matching: exact file size or checksum, else editor, publisher, volumes and year; theses,
  manuscripts and typed copies are never the printed edition.
- File-level provenance by exact byte size, with optional md5/sha1 verification.
- Duplicate proof by size and five sampled 64 KB windows, optional full SHA-256, and a planfs plan for the copies
  that keeps the best-named one (`dups --plan --profile`).
- Source adapters: folder (naming profiles), CSV/TSV (English or Arabic headers), OpenITI release metadata,
  archive.org (search and `_files.xml`), Waqfeya (list API and book pages), your own Shamela install (read-only),
  JSONL.
- Polite HTTP client: disk cache, per-host rate limit, retries, offline mode, a User-Agent naming the tool.
- `reconcile` with statuses have / partial / have_work / other_edition / related_only / review / missing,
  copies for what is missing, a review list whose decisions are kept, a work crosswalk, Markdown and HTML reports.
- `demo`, `explain`, `scan`, `export`, `provenance`, `dups`, `fetch`, `shamela-cards` commands.
- Benchmarks on public data (OpenITI), a held-out check on Wikidata records, an exact-title baseline and a
  head-to-head with OpenRefine 3.10.1.
