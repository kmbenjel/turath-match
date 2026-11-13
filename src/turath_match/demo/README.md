# Demo data

A tiny, made-up library (`library.csv`, ten books described by title, author and exact file size) and a wish list
(`wishlist.csv`) of ten classical works, reconciled against two real copy sources:

- `archive.jsonl`: eleven archive.org items recorded with `turath-match fetch archive` on 2026-11-13
  (identifiers, titles, file names, exact sizes and checksums: metadata only, no books). Most are scans of
  public-domain prints held by the Bibliotheca Alexandrina.
- `openiti.tsv`: 27 rows of the OpenITI release 2025.1.9 metadata (selected columns), CC BY-NC-SA 4.0:
  Nigst, Romanov, Savant, Seydi, Verkinderen et al., *OpenITI: a Machine-Readable Corpus of Islamicate Texts*,
  Zenodo, doi:10.5281/zenodo.17767721.

Two of the library's sizes are the exact sizes of archive.org scans, so those books are identified byte for byte
even though they are named differently. The other sizes are invented.
