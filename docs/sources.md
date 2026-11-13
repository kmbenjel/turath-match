# Sources

| Scheme | What it reads | Network | Notes |
|---|---|---|---|
| `folder:` | a folder of PDF / EPUB / DjVu files | none | sizes from the file system; names parsed by a profile (`smart`, `warraq`, `title`, `pattern:{title} - {author}`) |
| `csv:` | a CSV or TSV (English or Arabic headers) | none | `title` required; `size` holds exact sizes (`;` between volumes) |
| `openiti:` | an OpenITI release metadata TSV | `fetch openiti` downloads it once from Zenodo | CC BY-NC-SA 4.0: cite the release |
| `archive:` | archive.org items with their files | `fetch archive --search "title|author"` | sizes, md5 and sha1 from `<id>_files.xml`; one item can hold several books |
| `waqfeya:` | a Waqfeya dump | `fetch waqfeya [--details]` | the public list API (100 a page); details from each book page |
| `shamela:` | your Shamela install | none | read-only; see [shamela.md](shamela.md) |
| `jsonl:` | records saved by `export` / `scan` | none | |

All network access goes through one client: a disk cache under `~/.cache/turath-match` (or `TURATH_MATCH_CACHE`),
at most one request per second per host by default (`--interval`), retries with back-off on 5xx and timeouts, no
retry on 4xx, `--offline` to use the cache only, and a User-Agent that names the tool
(`turath-match/0.1 (catalog reconciliation tool)`; set `TURATH_MATCH_USER_AGENT` to add your own contact if a
service asks for one).

## Writing an adapter

An adapter is any object with a `scheme` and a `records()` iterator of `Record`; register a `scheme:location`
opener with `@register("myscheme")` in `turath_match.sources.base`. Put what the source knows into the fields it
has (editor, publisher, volumes, files with exact sizes); leave the rest empty, never guess it.
