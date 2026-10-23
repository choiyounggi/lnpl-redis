# lnpl-redis

Redis binding for [lnpl](https://github.com/choiyounggi/linkly)'s
`CacheDriver` SPI. Implements [linkly#143](https://github.com/choiyounggi/linkly/issues/143):
a real-Redis `CacheDriver`, verified against `lnpl.testing.CacheDriverTCK` in
CI via Testcontainers, and registered under the `lnpl.caches` entry-point
group as `redis`.

## Install

```
pip install lnpl-redis
```

This also installs a matching `lnpl` from PyPI. To try unreleased changes,
install from `main` instead:
`pip install git+https://github.com/choiyounggi/lnpl-redis@main`.

## Usage

Once installed, `lnpl` discovers this package's driver automatically through
the `lnpl.caches` entry-point. `--cache` splits on the first colon into
`<scheme>:<arg>`; for `redis`, `<arg>` is passed verbatim to `make_cache` as
a redis-py connection URL, e.g.:

```
--cache redis:redis://user:pass@host:6379/0
```

## Connection pool defaults

`RedisCacheDriver` opens one shared `redis.ConnectionPool` per instance
(`redis.ConnectionPool.from_url`), not a connection per call:

| Setting | Value |
|---|---|
| `max_connections` | 20 |
| `socket_timeout` | 5.0s |
| `socket_connect_timeout` | 2.0s |
| `health_check_interval` | 30s |
| `decode_responses` | `True` |
| retry | `redis.retry.Retry(redis.backoff.ExponentialBackoff(), 3)` on the default `supported_errors` (`ConnectionError`/`TimeoutError`) |

`retry_on_timeout` is intentionally not set — it is deprecated in redis-py
8.x, and `Retry`'s own default `supported_errors` already covers the same
transient-failure cases.

## TTL contract

TTL is **store-delegated**: the driver never reads a clock and never
separates `SET` from `EXPIRE`. `set(key, value, ttl_ms)`:

- `ttl_ms is None` → rejected with `DriverError` — linkly core already
  enforces a TTL budget on `CacheAccess` (`docs/ENFORCEMENT-MATRIX.md` §B),
  so a set without one is a bug, not a default to paper over.
- `ttl_ms <= 0` → the key is deleted (immediate expiry). Redis rejects a
  non-positive `PX`, so a delete is the contract-equivalent no-op.
- `ttl_ms > 0` → a single atomic call, `client.set(key, encoded, px=ttl_ms)`.
  Never `SET` then `EXPIRE` as two round trips.

## `cache_scope` self-report

`RedisCacheDriver.lnpl_enforcement = {"cache_scope": "shared"}` (RFC-0043).
Redis is a store external to the process, so cached values are visible to
every process pointed at the same Redis instance — the opposite of a
process-local fake cache, where each process sees only its own state. Code
that assumes cache entries are private to one process should check this
report before relying on `--cache redis:...`.

## JSON value constraint

Values are serialized with `json.dumps(value, ensure_ascii=False,
sort_keys=True)` and restored with `json.loads`. Only JSON-serializable
values may be cached; a non-serializable value raises `DriverError` at
`set()` time rather than failing silently or storing a `repr()`.

## Local testing

Requires Docker (used by Testcontainers to spin up a real Redis instance).

```
.venv/bin/pip install -e ".[test]"
TESTCONTAINERS_RYUK_DISABLED=true .venv/bin/python -m unittest discover -s tests -v
```

On macOS with Docker Desktop, Testcontainers' Ryuk reaper container can fail
to start with a socket-mount error (`mount source path
'.../.docker/run/docker.sock'`). If you hit that, disable Ryuk for the run
(CI's `ubuntu-latest` runners don't need this) — the command above already
does.

## Supported lnpl versions

This package depends on `lnpl>=0.9,<0.10` from PyPI, so any lnpl 0.9.x
release works.

The `linkly-sync` workflow checks two things on every PR:

- `latest-release` fails when PyPI has a newer lnpl that this range excludes
  (for example 0.10.0). Then widen the upper bound, run the suite, and release.
- `latest-main` runs the suite against linkly's `main`, so a break shows up
  before linkly releases it.

## Releasing

1. Set `version` in `pyproject.toml` and merge that to `main`.
2. Tag the merge commit `v<version>` and push the tag.
3. `release.yml` runs the suite, builds the sdist and wheel, and publishes them
   to PyPI through Trusted Publishing. The PyPI publisher is: project
   `lnpl-redis`, owner `choiyounggi`, repository `lnpl-redis`, workflow
   `release.yml`, environment `pypi`.

PyPI never accepts the same version twice. If the publish job fails for an
outside reason (PyPI outage, publisher not registered), re-run only that job
with `gh run rerun <run-id> --failed`. If the cause is in this repo, fix it on
`main` and release the next patch version. Never delete or re-push a tag.
