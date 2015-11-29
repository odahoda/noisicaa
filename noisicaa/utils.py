#/usr/bin/python3

import functools


memoize = functools.lru_cache(maxsize=None, typed=True)

