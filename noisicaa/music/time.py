#!/usr/bin/python3

import fractions


class Duration(fractions.Fraction):
    tick_duration = fractions.Fraction(1, 32 * 15)

    @property
    def ticks(self):
        ticks = self / self.tick_duration
        assert ticks.denominator == 1, (self, ticks)
        return ticks.numerator
