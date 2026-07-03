# Contributing

Thanks for considering a contribution — human or AI agent, both welcome (see
the [License](README.md#license) section of the README).

## Dev setup

```bash
git clone https://github.com/danyk20/autoscout24-scraper.git
cd autoscout24-scraper
pipenv install --dev
```

## Before opening a PR

```bash
pipenv run ruff check .          # lint
pipenv run ruff format .         # format
pipenv run mypy autoscout24_scraper.py  # type-check
pipenv run pytest                # unit tests, must stay at 100% coverage
```

If your change touches request/response handling against the real API,
also run the end-to-end suite (real network calls, ~10s):

```bash
pipenv run pytest -m e2e --no-cov
```

## Expectations

- **Every behavior change needs a test.** The unit suite mocks all HTTP
  (via `responses`) and enforces 100% coverage — a change without a test
  will fail CI on that basis alone.
- **Keep `verbose`/logging output backward compatible** unless the PR is
  specifically about changing it — other code (and the e2e/CLI tests)
  depends on the current message wording.
- If autoscout24.ch changes its API shape, prefer fixing the affected
  function directly over adding a workaround — the module docstring in
  `autoscout24_scraper.py` documents the current endpoint shapes.
- Keep the change minimal and focused; this is a small single-file utility
  by design (see the README's [Notes](README.md#notes) section for what's
  intentionally out of scope, e.g. concurrency, Docker, a database layer).

## Questions / bug reports

Open a GitHub issue using the bug report template — include the exact
command you ran and, if relevant, the raw API response you got back.
