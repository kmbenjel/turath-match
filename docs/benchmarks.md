# Benchmarks

All numbers come from `bash bench/compare.sh` (2026-11-13, a 32-vCPU server, Python 3.12, arabic-bib at its
current commit). The raw results are in [`bench/results/`](../bench/results/).

## 1. Work level on OpenITI ([`bench/openiti_works.py`](../bench/openiti_works.py))

- **Data:** OpenITI release 2025.1.9 metadata (Zenodo, CC BY-NC-SA 4.0), every Arabic text version with a title and
  an author: {OW_RECORDS:,} versions of {OW_BOOKS:,} works.
- **Truth:** two versions are one work when OpenITI files them under one book URI ({OW_POS:,} such pairs). The
  matcher sees titles, authors and death years only.
- **Procedure:** the token index proposes candidates ({OW_PAIRS:,} pairs); `match_work` decides each.

| | turath-match |
|---|---:|
| pairs called «same work» (status match) | {OW_TPFP:,} |
| of which right | {OW_TP:,} |
| precision | **{OW_P}** |
| recall | **{OW_R}** |
| true pairs on the review list | {OW_REV_POS:,} |
| other pairs on the review list | {OW_REV_NEG:,} |
| decisions with evidence | 100 % |

Most «wrong» pairs are OpenITI's own splits: the same title filed twice («كتاب الضعفاء الصغير» under two URIs),
volumes of one *Sunan* filed as separate books, or the *Masāʾil* of Aḥmad in two recensions whose alternative
titles are identical.

## 2. OpenRefine 3.10.1 on the same records ([`bench/openrefine_compare.py`](../bench/openrefine_compare.py))

OpenRefine is started headless and driven through its HTTP API: a project is made from the same records (one
column with the title, one with title + author), the clusterers are run, and every cluster is merged, as a user
would do. Pairs are scored by the same rule.

| Column · clusterer | Precision | Recall | Clusters |
|---|---:|---:|---:|
{OR_ROWS}

## 3. Work and edition level against your Shamela ([`bench/shamela_openiti.py`](../bench/shamela_openiti.py))

OpenITI versions made from Shamela carry the Shamela book id in their URI (`…Shamela0001681-ara1`). For each such
version and each Shamela book that is itself the source of an OpenITI version, OpenITI says whether they are one
work (same book URI), and the version's own source id says which Shamela book is the same *edition*. Run on a local
Shamela install with its book cards exported by `turath-match shamela-cards`; only counts are printed.

| | Work | Edition |
|---|---:|---:|
| OpenITI versions × labelled Shamela books | {SO_V:,} × {SO_S:,} | |
| precision | {SO_W_P} | {SO_E_P} |
| recall | {SO_W_R} | {SO_E_R} |
| other editions of the same work rejected outright | | {SO_E_REJ} |

Edition recall is low on purpose: when one side gives no editor and no publisher, the pair is `have_work`
(«edition not proven»), never «same edition».

## 4. A 500-book library ([`bench/library500.py`](../bench/library500.py))

500 OpenITI works, each described by the title and author of a *secondary* version (other spellings, as a file name
would carry them), reconciled against the primary versions of all {L5_TARGETS:,} works.

| | |
|---|---:|
| time (one process) | {L5_SECS} s |
| works found (have, have_work, other_edition, partial) | {L5_FOUND} of 500 |
| wrongly found | {L5_WRONG} |
| precision · recall | {L5_P} · {L5_R} |
| left for a person (review list) | {L5_REVIEW} |
| the same library checked by hand at an assumed 3 minutes a book | {L5_MANUAL_H} hours |
