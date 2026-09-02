# lnpl-redis

Redis binding for [lnpl](https://github.com/choiyounggi/linkly)'s
`CacheDriver` SPI. Implements [linkly#143](https://github.com/choiyounggi/linkly/issues/143):
a real-Redis `CacheDriver`, verified against `lnpl.testing.CacheDriverTCK` in
CI via Testcontainers, and registered under the `lnpl.caches` entry-point
group as `redis`.

## Install

This package is GitHub-only (not published to PyPI) because it pins `lnpl`
via a PEP 508 direct reference to a specific commit SHA, which PyPI rejects.

```
pip install git+https://github.com/choiyounggi/lnpl-redis@main
```

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

## Bumping the pinned lnpl commit

This package depends on `lnpl` via a commit-SHA-pinned direct reference in
`pyproject.toml` (`lnpl @ git+https://github.com/choiyounggi/linkly@<sha>`)
rather than `@main`, since linkly's `main` branch moves frequently across
parallel sessions and an unpinned dependency could break CI without warning.
To pick up a newer `lnpl`, replace `<sha>` in the `dependencies` entry with
the target commit SHA from the `linkly` repository and re-run the test suite.
