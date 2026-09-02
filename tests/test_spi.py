import unittest

from lnpl.drivers import DriverError, open_cache
from testcontainers.community.redis import RedisContainer

from lnpl_redis import make_cache
from lnpl_redis.driver import RedisCacheDriver


class RedisSPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._container = RedisContainer("redis:7")
        cls._container.start()
        cls._url = "redis://%s:%s/0" % (
            cls._container.get_container_host_ip(),
            cls._container.get_exposed_port(cls._container.port),
        )

    @classmethod
    def tearDownClass(cls):
        cls._container.stop()

    def test_open_cache_resolves_to_redis_driver(self):
        driver = open_cache("redis:" + self._url)
        self.addCleanup(driver.close)

        self.assertIsInstance(driver, RedisCacheDriver)

    def test_empty_url_raises_value_error(self):
        with self.assertRaises(ValueError):
            make_cache("")

    def test_unreachable_url_raises_driver_error(self):
        with self.assertRaises(DriverError):
            make_cache("redis://nope.invalid:6399/0")

    def test_lnpl_enforcement_reports_shared_cache_scope(self):
        self.assertEqual(
            RedisCacheDriver.lnpl_enforcement, {"cache_scope": "shared"})


if __name__ == "__main__":
    unittest.main()
