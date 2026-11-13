# Shamela: reading your own copy

turath-match reads the catalog of a Shamela (المكتبة الشاملة) desktop installation that **you already have**. It
ships no Shamela data, downloads nothing from Shamela's servers, and never modifies the installation:

- `shamela:/path/to/shamela` opens `database/master.db` read-only (SQLite `mode=ro`) and yields one record per
  book: title, author, death year, category, and the file name and byte size of the PDF Shamela links to.
- `turath-match shamela-cards` exports the book cards («بطاقة الكتاب»: editor, publisher, edition, year, volumes)
  from Shamela's Lucene store, using Shamela's own Java and Lucene jars on a **copy** of the index. The small reader
  is `tools/shamela-dump/Dump.java` (compile it once with `javac`). Then pass the export as
  `shamela:/path/to/shamela::cards.jsonl`.

Where an install lives: Linux `~/.local/share/shamela`, or wherever you unpacked it; set `SHAMELA_HOME` or pass the
folder.

## The legal position, briefly (not legal advice)

- **What the tool does:** it is a reader, like a spreadsheet opening a file on your disk. Reading the metadata of
  software you lawfully installed, on your own machine, for your own catalog work, is the use the software was
  made for.
- **What it does not do:** it does not redistribute the Shamela database, its book texts or its cards, and the
  project's repository, tests and demo contain no Shamela data (the tests build a tiny synthetic `master.db`).
  Results you publish (for example a list of which works you hold) are your own facts about your library; book
  titles and author names are bibliographic facts, but a bulk copy of Shamela's catalog fields is a different
  matter, so do not publish exports wholesale.
- **Benchmarks:** `bench/shamela_openiti.py` runs on your install and prints counts only.
- **Identifiers:** the Shamela book ids that turath-match finds go only into the files you produce on your own
  machine (`matches.jsonl`, `crosswalk.jsonl`, the reports). OpenITI's own version URIs carry Shamela ids
  (`…Shamela0001681-ara1`); turath-match reads them there like any other field of the OpenITI metadata, and those
  URIs are the only Shamela ids in the package (in the demo's OpenITI rows).
