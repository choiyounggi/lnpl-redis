import unittest
from unittest import mock

import redis

from lnpl.drivers import DriverError

from lnpl_redis.driver import RedisCacheDriver


def _driver_with_fake_client():
    driver = object.__new__(RedisCacheDriver)
    driver.url = "redis://fake/0"
    driver._pool = mock.Mock()
    driver._client = mock.Mock()
    return driver


class RedisCacheDriverContractTest(unittest.TestCase):
    """Driver-specific TTL/serialization contract (D7/D8) that the generic
    CacheDriverTCK does not cover: rejecting a missing TTL and proving the
    write is a single atomic SET...PX, never SET followed by EXPIRE."""

    def test_set_without_ttl_raises_driver_error(self):
        driver = _driver_with_fake_client()

        with self.assertRaises(DriverError):
            driver.set("k", "v", ttl_ms=None)
        driver._client.set.assert_not_called()

    def test_set_writes_value_and_ttl_in_a_single_atomic_call(self):
        driver = _driver_with_fake_client()

        driver.set("k", {"n": 1}, ttl_ms=60_000)

        driver._client.set.assert_called_once_with("k", '{"n": 1}', px=60_000)
        driver._client.expire.assert_not_called()
        driver._client.pexpire.assert_not_called()

    def test_set_with_non_serializable_value_raises_driver_error(self):
        driver = _driver_with_fake_client()

        with self.assertRaises(DriverError):
            driver.set("k", object(), ttl_ms=60_000)
        driver._client.set.assert_not_called()

    def test_set_with_ttl_ms_zero_deletes_instead_of_setting(self):
        driver = _driver_with_fake_client()

        driver.set("k", "v", ttl_ms=0)

        driver._client.delete.assert_called_once_with("k")
        driver._client.set.assert_not_called()

    def test_close_is_safe_to_call_more_than_once(self):
        driver = _driver_with_fake_client()
        pool = driver._pool

        driver.close()
        driver.close()

        pool.disconnect.assert_called_once()

    def test_get_wraps_redis_error_as_driver_error(self):
        driver = _driver_with_fake_client()
        driver._client.get.side_effect = redis.RedisError("boom")

        with self.assertRaises(DriverError):
            driver.get("k")

    def test_invalidate_wraps_redis_error_as_driver_error(self):
        driver = _driver_with_fake_client()
        driver._client.delete.side_effect = redis.RedisError("boom")

        with self.assertRaises(DriverError):
            driver.invalidate("k")


if __name__ == "__main__":
    unittest.main()
