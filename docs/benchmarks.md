# Benchmarks

All numbers come from `bash bench/compare.sh` (2026-11-13, a 32-vCPU server, Python 3.12, arabic-bib at its
current commit). The raw results are in [`bench/results/`](../bench/results/).

**Development and held-out data.** The matching rules were developed on OpenITI release 2025.1.9: benchmarks 1, 3
and 4 below all draw on it, and their numbers are on the set the rules were tuned on. Benchmark 5 puts on one side
records the rules never saw (Wikidata's own labels) and is the held-out result.

## 1. Work level on OpenITI ([`bench/openiti_works.py`](../bench/openiti_works.py))

- **Data:** OpenITI release 2025.1.9 metadata (Zenodo, CC BY-NC-SA 4.0), every Arabic text version with a title and
  an author: 12,688 versions of 8,233 works.
- **Truth:** two versions are one work when OpenITI files them under one book URI (7,254 such pairs). The
  matcher sees titles, authors and death years only.
- **Procedure:** the token index proposes candidates (237,811 pairs); `match_work` decides each.

| | turath-match |
|---|---:|
| pairs called «same work» (status match) | 5,987 |
| of which right | 5,892 |
| precision | **0.984** |
| recall | **0.812** |
| true pairs on the review list | 332 |
| other pairs on the review list | 1,509 |
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
| title | identical values (baseline, no clustering) | 0.648 | 0.556 | |
| title + author | identical values (baseline, no clustering) | 0.738 | 0.432 | |
| title | fingerprint | 0.648 | 0.559 | 19 |
| title | ngram-fingerprint (2) | 0.649 | 0.562 | 40 |
| title | levenshtein (radius 2) | 0.619 | 0.578 | 350 |
| title + author | fingerprint | 0.741 | 0.439 | 49 |
| title + author | ngram-fingerprint (2) | 0.741 | 0.441 | 62 |

The baseline rows put together only records whose value is character for character the same
(`bench/openrefine_compare.py --baseline-only`, no OpenRefine needed): on the title, fingerprint clustering adds
16 true pairs and 4 wrong ones to it. The Levenshtein clusterer on the title + author column was stopped after 20
minutes without a result; on the title column it finished in 39 s.

## 3. Work and edition level against your Shamela ([`bench/shamela_openiti.py`](../bench/shamela_openiti.py))

OpenITI versions made from Shamela carry the Shamela book id in their URI (`…Shamela0001681-ara1`). For each such
version and each Shamela book that is itself the source of an OpenITI version, OpenITI says whether they are one
work (same book URI), and the version's own source id says which Shamela book is the same *edition*. Run on a local
Shamela install with its book cards exported by `turath-match shamela-cards`; only counts are printed.

| | Work | Edition |
|---|---:|---:|
| OpenITI versions × labelled Shamela books | 3,566 × 3,557 | |
| precision | 0.996 | 0.993 |
| recall | 0.716 | 0.498 |
| other editions of the same work rejected outright | | 0.726 |

Edition recall is low on purpose: when one side gives no editor and no publisher, the pair is `have_work`
(«edition not proven»), never «same edition».

## 4. A 500-book library ([`bench/library500.py`](../bench/library500.py))

500 OpenITI works, each described by the title and author of a *secondary* version (other spellings, as a file name
would carry them), reconciled against the primary versions of all 8,233 works.

| | |
|---|---:|
| time (one process) | 154 s |
| works found (have, have_work, other_edition, partial) | 376 of 500 |
| wrongly found | 2 |
| precision · recall | 0.995 · 0.752 |
| left for a person (review list) | 80 |
| the same library checked by hand at an assumed 3 minutes a book | 25 hours |

## 5. Held out: Wikidata records against OpenITI ([`bench/wikidata_heldout.py`](../bench/wikidata_heldout.py))

- **Data:** the Wikidata items that carry a Shamela book edition id (P12239), queried on 2026-11-13: 1,054
  items. Each is described by its Arabic label and the Arabic label of its author (the item's P50, else its
  work's), as Wikidata's editors wrote them, often with the edition in brackets («السلوك لمعرفة دول الملوك (دار
  الكتب العلمية، 1997م)»). These records were not used while the rules were developed. The other side is the
  12,688 OpenITI 2025.1.9 versions of benchmark 1.
- **Truth, labelled automatically:** an OpenITI version made from a Shamela book carries its id in the version URI
  (`…Shamela0001681-ara1`). A Wikidata item and the versions of the OpenITI book that holds its Shamela id are one
  work; the item and the versions of any other book are not. Left out because the answer is not known: 382 items
  whose Shamela id is in no OpenITI version, 15 with no Arabic author label. 657 items remain.
- **Procedure:** the token index proposes OpenITI candidates for each item (20,715 pairs); `match_work` decides
  each; scoring as in benchmark 1.

| | All pairs | Without the version made from the same Shamela book |
|---|---:|---:|
| true pairs | 1,927 | 1,270 |
| pairs called «same work» | 1,428 | 916 |
| precision | **0.980** | **0.969** |
| recall | **0.727** | **0.699** |
| true pairs on the review list | 148 | 104 |
| other pairs on the review list | 59 | 59 |
| decisions with evidence | 100 % | |

The second column leaves out the one OpenITI version made from the same Shamela book as the Wikidata item, so it
measures the item against the versions OpenITI took from other sources. 14 of the 657 Wikidata titles are, after
normalisation, identical to the title of that version.
