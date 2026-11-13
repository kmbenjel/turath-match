# Output schema

`turath-match reconcile … -o OUT/` writes seven files. The JSON Schemas are in
[`src/turath_match/schema/`](../src/turath_match/schema/); `turath-catalog` imports `matches.jsonl` and
`crosswalk.jsonl` directly.

| File | One row per | Use |
|---|---|---|
| `status.tsv` | target record | the answer: have / partial / have_work / other_edition / related_only / review / missing |
| `matches.jsonl` | compared pair at one level | every decision with its evidence (machine-readable) |
| `review.tsv` | uncertain pair | fill the `decision` column (`same`, `different`, `related`) and pass it back with `-d` |
| `copies.tsv` | target × copy | where a trustworthy copy of a missing work is, with exact sizes |
| `crosswalk.jsonl` | work cluster | every record of one work across all sources, with editions and files |
| `report.md`, `report.html` | — | the same, for people |

## `matches.jsonl`

| Field | Type | Meaning |
|---|---|---|
| `left_scheme`, `left_id` | string | the record checked (a catalog or wish-list record, or a library file at file level) |
| `right_scheme`, `right_id` | string | the record it was compared with |
| `level` | `work` · `edition` · `file` | what the verdict is about |
| `verdict` | `same` · `related` · `different` · `uncertain` | the decision |
| `relation` | string or null | for `related`: `abridgement`, `commentary`, `gloss`, `continuation`, `selection`, `versification`, `refutation`, `takhrij`, `index`, `study`, `rearrangement`, `part`, `recension` |
| `derived_side` | `left` · `right` · null | which record is the derived work (the commentary, the abridgement) |
| `method` | `exact_size` · `hash` · `sampled_bytes` · `exact_title_author` · `fuzzy_title_author` · `manual` | how |
| `score` | 0–1 | confidence in the verdict |
| `confidence` | `high` (≥ 0.85) · `medium` (≥ 0.6) · `low` | the score as a label |
| `status` | `match` · `review` · `no_match` | `match` = verdict `same` with score ≥ 0.85; every `uncertain` is `review` |
| `evidence` | list of `{kind, detail, weight}` | every reason, for (+) and against (−); a veto has weight −1 |
| `left_title`, `left_author`, `right_title`, `right_author`, `right_url` | string | for reading the file without the inputs |

Evidence kinds: `title`, `author`, `death`, `uri`, `derivation`, `editor`, `publisher`, `volumes`, `year`, `flag`,
`size`, `hash`, `edition`, `manual`.

**Importing into another catalog:** keep rows with `status = match` and `verdict = same`; each gives the external id
`right_scheme:right_id` for the left record.

## `crosswalk.jsonl`

| Field | Meaning |
|---|---|
| `cluster_id` | `w_` + the first 10 hex digits of `sha1(title_key + "|" + author_key)`, the same recipe as turath-catalog's `work_id` (NFC; tashkil and tatweel removed; أإآٱ→ا, ة→ه, ى→ي, ؤ→و, ئ→ي, ء dropped; digits to ASCII; everything outside the Arabic letters, digits and space becomes a space; `title_key` cuts at the first « - », « ط », « ت » and drops a leading «كتاب»; `author_key` keeps the part before «؛» and drops leading honorifics) |
| `title_ar`, `author_ar`, `death_ah` | from the best-described member |
| `openiti_uri` | the OpenITI book URI when a member is an OpenITI version |
| `ext_ids` | `scheme:id` of every non-library member, joined by `;` |
| `members[]` | `scheme`, `id`, `url`, `editors`, `publisher`, `place`, `year`, `volumes`, `size_bytes`, `files[]` (`name`, `size`, `url`, `md5`, `sha1`) |

A cluster joins records linked by `same` work matches with status `match`; `related` and `uncertain` pairs never
join a cluster.

## Input records

Every adapter yields the same `Record`: `scheme`, `id`, `title`, `author`, `death` (AH), `editor`, `publisher`,
`place`, `year`, `volumes`, `files[]` (`name`, `size`, `url`, `path`, `md5`, `sha1`, `format`), `url`, `work_uri`,
`flags` (`thesis`, `manuscript`, `typed`, `part`). `turath-match export` writes them as JSONL, and `jsonl:` reads
them back.
