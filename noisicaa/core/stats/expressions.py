#!/usr/bin/python3

import collections
import logging

from . import stats

logger = logging.getLogger(__name__)


class InvalidExpressionError(ValueError):
    pass

class Builder(object):
    def __init__(self, **labels):
        name = stats.StatName(**labels)
        self.__code = [('SELECT', name)]

    def get_code(self):
        return self.__code

    def RATE(self):
        self.__code.append(('RATE',))
        return self


def compile_expression(expr):
    try:
        builder = eval(expr, {'SELECT': Builder})
    except Exception as exc:
        raise InvalidExpressionError(str(exc))
    return builder.get_code()
