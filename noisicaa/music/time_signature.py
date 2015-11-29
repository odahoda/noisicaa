#!/usr/bin/python3

class TimeSignature(object):
    def __init__(self, upper=4, lower=4):
        if upper < 1 or upper > 99:
            raise ValueError("Bad time signature %r/%r" % (upper, lower))
        if lower < 1 or lower > 99:
            raise ValueError("Bad time signature %r/%r" % (upper, lower))

        self._upper = upper
        self._lower = lower

    def __repr__(self):
        return 'TimeSignature(%d/%d)' % (self.upper, self.lower)

    def __eq__(self, other):
        if other is None:
            return False

        if not isinstance(other, TimeSignature):
            raise TypeError(
                "Can't compare %s to %s" % (
                    type(self).__name__, type(other).__name__))

        return self.value == other.value

    @property
    def value(self):
        return (self._upper, self._lower)

    @property
    def upper(self):
        return self._upper

    @property
    def lower(self):
        return self._lower
