"""Redis CacheDriver factory for lnpl.caches entry-point registration."""

__all__ = ["make_cache"]


def make_cache(arg):
    from .driver import RedisCacheDriver

    return RedisCacheDriver(url=arg)
