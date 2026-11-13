# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
- Benchmarks on public data (OpenITI) and a head-to-head with OpenRefine 3.10.1.
