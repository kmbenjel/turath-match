# Contributing

Thank you for helping. Bug reports with a *pair of records* are the most useful thing you can send: two titles and
authors that turath-match got wrong, and what the right answer is. `turath-match explain "title|author" "title|author"`
prints the evidence; paste it in the issue.

## Setup

```bash
git clone https://github.com/kmbenjel/turath-match && cd turath-match
uv venv && uv pip install -e ".[dev]"
pytest -q            # about 110 tests, a few seconds, no network
ruff check src tests && ruff format --check src tests
```

turath-match depends on [arabic-bib](https://github.com/kmbenjel/arabic-bib) for Arabic normalisation and author
agreement. A fix that is about *names* (a nisba, a kunya, a spelling) belongs there; a fix about *titles, editions,
files or catalogs* belongs here.

## Rules for matching changes

- Precision first: a wrong «same» is worse than a «review». Every new rule needs a test with a real-world pair that
  it fixes **and** one it must not break.
- Run the public benchmark before and after (`bash bench/compare.sh` on a server; it downloads the OpenITI
  metadata once) and put both numbers in the pull request.
- Tests never touch the network: record a small fixture in `tests/fixtures/` (hand-made, a few records) and use the
  `fake_http` fixture.
- No catalog dumps in the repository: Shamela, Waqfeya and archive.org data stay on the user's machine.

## Releases

Semantic versioning; every change goes in `CHANGELOG.md` under *Unreleased*.
