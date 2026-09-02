"""Redis CacheDriver — redis-py mirror of lnpl's CacheDriver contract.

TTL is store-delegated (CacheDriver docstring, `lnpl.drivers`): this driver
never reads a clock. `set()` hands `ttl_ms` straight to Redis as `PX` in a
single atomic `SET` call — never a separate `SET` followed by `EXPIRE`.
"""

import json

import redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from lnpl.drivers import CacheDriver, DriverError

_MAX_CONNECTIONS = 20
_SOCKET_TIMEOUT = 5.0
_SOCKET_CONNECT_TIMEOUT = 2.0
_HEALTH_CHECK_INTERVAL = 30
_RETRIES = 3


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class RedisCacheDriver(CacheDriver):
    """A Redis-backed cache. One shared connection pool per instance."""

    lnpl_enforcement = {"cache_scope": "shared"}

    def __init__(self, url):
        if not str(url).strip():
            raise ValueError(
                "--cache redis: needs a URL, got an empty one "
                "(e.g. --cache redis:redis://user:pass@host:6379/0)")
        self.url = url
        self._pool = redis.ConnectionPool.from_url(
            url,
            max_connections=_MAX_CONNECTIONS,
            socket_timeout=_SOCKET_TIMEOUT,
            socket_connect_timeout=_SOCKET_CONNECT_TIMEOUT,
            health_check_interval=_HEALTH_CHECK_INTERVAL,
            decode_responses=True,
        )
        self._client = redis.Redis(
            connection_pool=self._pool,
            retry=Retry(ExponentialBackoff(), _RETRIES))
        try:
            self._client.ping()
        except redis.RedisError as exc:
            raise DriverError(
                "cannot open the redis store at %r: %s" % (url, exc)) from exc

    # -- contract --------------------------------------------------------

    def get(self, key):
        try:
            found = self._client.get(key)
        except redis.RedisError as exc:
            raise DriverError("cannot get %r: %s" % (key, exc)) from exc
        if found is None:
            return None
        return json.loads(found)

    def set(self, key, value, ttl_ms):
        if ttl_ms is None:
            raise DriverError(
                "refusing set without a TTL — linkly core enforces a TTL "
                "budget on CacheAccess (ENFORCEMENT-MATRIX §B)")
        try:
            if ttl_ms <= 0:
                self._client.delete(key)
                return
            try:
                encoded = _encode(value)
            except TypeError as exc:
                raise DriverError(
                    "cannot set %r: value is not JSON-serializable: %s"
                    % (key, exc)) from exc
            self._client.set(key, encoded, px=int(ttl_ms))
        except redis.RedisError as exc:
            raise DriverError("cannot set %r: %s" % (key, exc)) from exc

    def invalidate(self, key):
        try:
            self._client.delete(key)
        except redis.RedisError as exc:
            raise DriverError("cannot invalidate %r: %s" % (key, exc)) from exc

    def close(self):
        client, self._client = getattr(self, "_client", None), None
        if client is not None:
            self._pool.disconnect()
