#!/usr/bin/python3


class Pos2F(object):
    def __init__(self, x, y):
        self._x = float(x)
        self._y = float(y)

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    def __eq__(self, other):
        if not isinstance(other, Pos2F):
            return False

        return (self._x == other._x and self._y == other._y)

    def __add__(self, other):
        if not isinstance(other, Pos2F):
            raise TypeError(
                "Expected Pos2F, got %s" % type(other).__name__)

        return self.__class__(self._x + other._x, self._y + other._y)

    def __sub__(self, other):
        if not isinstance(other, Pos2F):
            raise TypeError(
                "Expected Pos2F, got %s" % type(other).__name__)

        return self.__class__(self._x - other._x, self._y - other._y)
