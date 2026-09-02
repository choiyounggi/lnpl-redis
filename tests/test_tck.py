import time
import unittest

from lnpl.testing import CacheDriverTCK
from testcontainers.community.redis import RedisContainer

from lnpl_redis.driver import RedisCacheDriver


class RedisTCKTest(CacheDriverTCK, unittest.TestCase):
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

    def setUp(self):
        self._container.get_client().flushall()
        super().setUp()

    def make_cache(self):
        return RedisCacheDriver(url=self._url)

    def advance(self, ms):
        time.sleep(ms / 1000 + 0.05)


if __name__ == "__main__":
    unittest.main()
