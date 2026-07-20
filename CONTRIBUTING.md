# Contributing

This is the developer-facing companion to [README.md](README.md), which covers
what the pipeline extracts and what it writes. This doc covers running it,
testing it, extending it, and releasing it.

## Directory structure

```bash
.
├── src/
│   ├── main.py          # Entrypoint: resolves paths, walks the days, writes Parquet
│   ├── config.py        # All env-var config + bucket/path resolution
│   ├── dates.py         # BACKFILL_RANGE -> the list of days to process
│   ├── download.py      # Copilot users-1-day metrics report -> DataFrame (in memory)
│   ├── credits.py       # DataFrame -> per-user credit rows
│   ├── billing.py       # Enterprise ai_credit/usage billing API -> usageItems
│   └── models.py        # usageItems -> per-model rows (family + routed tags)
├── tests/               # pytest suite, one module per src module
├── .github/workflows/   # Shared AP workflows
├── Dockerfile           # Built on the AP Airflow Python base image
├── pytest.ini           # pythonpath=src, testpaths=tests
├── requirements.txt     # Runtime deps (awswrangler, pandas, requests)
└── requirements-dev.txt # pytest
```

The shape to keep in mind: **I/O lives at the edges, the middle is pure.**
`download.py` and `billing.py` are the only modules that talk to GitHub,
`main._write` is the only thing that talks to S3, and everything between them
(`dates`, `credits`, `models`) is pure functions over plain data. That's why the
suite needs no AWS credentials and no network.

## Secrets

This repository contains no credentials, and nothing in it — including the
examples below — should ever be pasted over with a real one. The pipeline takes
its token from `SECRET_ENTERPRISE_BILLING_TOKEN` in the environment: injected by
Analytical Platform Airflow from the `enterprise-billing-token` secret when
deployed, and read from your own secret store (or an untracked shell profile)
when running locally. Never write a token into a file in this tree, a commit
message, or a log line.

## Running locally

There is no `make` target or compose file here — it's a single container with one
entrypoint. Run it natively:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Pull the token from your secret store; don't paste it and don't echo it.
export SECRET_ENTERPRISE_BILLING_TOKEN="$(your-secret-manager read copilot-billing-token)"
export DEV_BUCKET=your-dev-bucket     # no default; unset fails at startup
export REPORT_DAY=2026-07-15          # default: yesterday (UTC)
python src/main.py
```

You need AWS credentials your shell can already use for the write (a named
profile via SSO is preferable to static keys), and a token with Copilot metrics
read **and** `manage_billing:enterprise`. A run with `MODE` unset is a dev run and
writes to `DEV_BUCKET`.

> **A local run is a real write.** `mode="overwrite_partitions"` means re-running
> a day replaces that day's partition rather than appending — idempotent, but it
> does overwrite. Point `DEV_BUCKET` at a bucket you own before you run it.

To exercise the code without writing anything, run the test suite — it covers the
whole path with the HTTP and S3 calls stubbed.

### Container

`docker build -t copilot-usage-pipeline .` builds the image the Airflow task
runs; the entrypoint is `python3 main.py`, so it needs no arguments. Pass config
through by variable name rather than by value, so no secret ends up in your shell
history:

```bash
docker run --rm \
  -e SECRET_ENTERPRISE_BILLING_TOKEN -e DEV_BUCKET -e REPORT_DAY \
  copilot-usage-pipeline
```

The container still needs AWS credentials to write. In Airflow those come from
the platform's role; locally, supply them however your setup normally does for a
container — that plumbing is yours to choose and deliberately isn't baked into
the image.

## Configuration

Every knob is an environment variable read in `src/config.py`, and the table of
them lives in the [README](README.md#configuration-environment-variables) — it is
the reference, not this file. Two rules worth repeating here:

* **No bucket names are hardcoded.** `MODE` picks between `DEV_BUCKET` and
  `PROD_BUCKET`; whichever one is active must be set or `resolve_paths()` raises
  at startup, before any API call.
* **Config is read at import time.** `src/config.py` evaluates `os.environ` on
  import, so tests set values with `monkeypatch.setattr(main.config, ...)` rather
  than by editing the environment. Follow that pattern if you add config.

## Testing

```bash
python -m pytest          # pytest.ini already puts src/ on the path
python -m pytest -q tests/test_dates.py
```

The suite is offline by construction: `requests.get` and `wr.s3.to_parquet` are
monkeypatched, so there's nothing to mock at the network level and no AWS calls.
When you add a fetch, keep it in `download.py`/`billing.py` so the module you're
testing stays pure.

## Failure policy

Two deliberate behaviours you should preserve if you touch `main.py`:

* **Order matters.** Per-user is written *before* per-model, so that a per-model
  failure (typically a token missing `manage_billing:enterprise`) can't discard a
  per-user write that already succeeded.
* **Skip vs. fail.** A day whose report isn't ready yet, or that has no credits,
  or that has no billing `usageItems`, is logged and skipped — that's normal, not
  an error. A non-2xx HTTP response is *not* skipped: it propagates, the job exits
  non-zero, and Airflow flags the run. Don't quietly `try/except` these into a
  green run.

## Deployment

The container is built and pushed by the shared Analytical Platform workflow in
`.github/workflows/release-container.yml`, which triggers **on a pushed tag**. The
image is then referenced by a task in the
[analytical-platform-airflow](https://github.com/ministryofjustice/analytical-platform-airflow)
manifest, which is where the schedule, the per-task `env_vars` (including the
buckets), and the injection of the `enterprise-billing-token` secret are defined.
That manifest lives in the Airflow repo, not here.

PRs are gated by the shared test-container, scan-container, and dependency-review
workflows.

## Contributions, forks, and governance

This pipeline is built and maintained for the Ministry of Justice's own use, and
its direction is set by our internal roadmap and governance plans. It exists to
feed our Athena tables and the
[Copilot AI credits dashboard](https://github.com/ministryofjustice/moj-copilot-ai-credits-dashboard).
That shapes what we can take from outside:

* **Issues are always welcome.** Bug reports, questions, and "have you
  considered…" are useful to us regardless of whether we act on them.
* **Pull requests are welcome, but we can only merge what coincides with our
  roadmap.** Every line we merge is a line we maintain and run daily against a
  live billing API, so a PR is judged on whether it fits where we're already
  going — not just on whether it's good work. If you're planning anything beyond
  a small fix, **open an issue first** and let's check the fit before you spend
  the effort. We'd rather say "not for us" early than after you've written it.
* **Fork it.** It's [MIT](LICENSE) — you're free to take it, run it, and change
  it, and you don't need our permission or our agreement. If your needs diverge
  from ours, forking is a legitimate answer rather than a consolation prize.

### Diverging without pain

Most of what a fork needs is already an environment variable, not a code change.
Your org, your enterprise slug, your buckets, and your prefix are all config:

```bash
ORG=your-org ENTERPRISE_SLUG=your-enterprise \
DEV_BUCKET=your-bucket OUTPUT_PREFIX=your/prefix python src/main.py
```

Setting `ORG` narrows the metrics report to that single org. Leave it unset to
fetch enterprise-wide (every org in `ENTERPRISE_SLUG`), which is what the MoJ
deployment does — it needs a token with enterprise-level metrics read. If your
token only carries org-level access, set `ORG` and the pipeline uses the
org-scoped endpoint instead.

If you need a code change, the seams — in rough order of how likely you are to
need them — are:

* **Somewhere other than S3 Parquet.** `main._write()` is the single function
  that persists anything; it takes a DataFrame and a path. A different sink
  (Postgres via `df.to_sql`, local Parquet, GCS) is a change to that one
  function, and nothing upstream of it needs to know. Keep the
  overwrite-by-partition semantics if you can — that idempotency is what makes
  re-running a day safe.
* **A different model taxonomy.** `models.model_family()` is a small pure
  function over the model name, and `routed` is an `Auto:` prefix check. Both are
  a couple of lines in `models.py` and fully covered by `tests/test_models.py`.
* **A different backfill window.** `dates.report_days()` maps a range name to a
  list of ISO day strings and is pure — a new range is a branch plus a test, with
  no other module affected.
* **A different upstream API.** Replace `download.read_report()` (return a
  DataFrame or `None`) or `billing.fetch_billing()` (return a list of
  `usageItems`-shaped dicts). Keep those return shapes and `credits.py`,
  `models.py`, and `main.py` work unchanged.

Keeping your changes behind those seams is the difference between a fork you can
rebase and a fork you can't — the output row shapes documented in the
[README](README.md#output-datasets) are the contract, and changes scattered
through `main.py` will fight every upstream pull.

And if you build something you think we'd want, the roadmap caveat still applies
— but a self-contained change behind one of those seams is about the most
mergeable thing you could send us, so do open that issue.
