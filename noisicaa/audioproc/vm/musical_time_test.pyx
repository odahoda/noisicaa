# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

from .musical_time cimport *
from . import musical_time_pb2

import fractions
import unittest


class MusicalDurationTest(unittest.TestCase):
    def test_constructor(self):
        cdef MusicalDuration t
        self.assertEqual(t.numerator(), 0)
        self.assertEqual(t.denominator(), 1)

    def test_set(self):
        cdef MusicalDuration t

        t.set(MusicalDuration(3, 4))
        self.assertEqual(t.numerator(), 3)
        self.assertEqual(t.denominator(), 4)

        t = MusicalDuration(4, 5)
        self.assertEqual(t.numerator(), 4)
        self.assertEqual(t.denominator(), 5)

        t = MusicalDuration(-2)
        self.assertEqual(t.numerator(), -2)
        self.assertEqual(t.denominator(), 1)

    def test_add(self):
        cdef MusicalDuration t
        for n in range(-100, 100):
            for d in range(1, 100):
                expected = fractions.Fraction(1, 1) + fractions.Fraction(n, d)

                t = MusicalDuration(1, 1)
                t += MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalDuration(1, 1) + MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

    def test_sub(self):
        cdef MusicalDuration t
        for n in range(-100, 100):
            for d in range(1, 100):
                expected = fractions.Fraction(1, 1) - fractions.Fraction(n, d)

                t = MusicalDuration(1, 1)
                t.sub(MusicalDuration(n, d))
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalDuration(1, 1)
                t -= MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalDuration(1, 1) - MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

    def test_mul(self):
        cdef MusicalDuration t
        for n in range(-100, 100):
            for d in range(1, 100):
                expected = fractions.Fraction(2, 3) * fractions.Fraction(n, d)

                t = MusicalDuration(2, 3)
                t.mul(MusicalDuration(n, d))
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalDuration(2, 3)
                t *= MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalDuration(2, 3) * MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

    def test_div(self):
        cdef MusicalDuration t
        for n in range(-100, 100):
            if n == 0:
                continue
            for d in range(1, 100):
                expected = fractions.Fraction(2, 3) / fractions.Fraction(n, d)

                t = MusicalDuration(2, 3)
                t.div(MusicalDuration(n, d))
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalDuration(2, 3)
                t /= MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalDuration(2, 3) / MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

    def test_cmp(self):
        self.assertTrue(MusicalDuration(1, 2) == MusicalDuration(2, 4))
        self.assertFalse(MusicalDuration(1, 2) == MusicalDuration(3, 4))

        self.assertTrue(MusicalDuration(1, 2) != MusicalDuration(3, 4))
        self.assertFalse(MusicalDuration(1, 2) != MusicalDuration(2, 4))

        self.assertTrue(MusicalDuration(1, 2) < MusicalDuration(3, 4))
        self.assertFalse(MusicalDuration(3, 4) < MusicalDuration(1, 2))

        self.assertTrue(MusicalDuration(1, 2) <= MusicalDuration(3, 4))
        self.assertTrue(MusicalDuration(1, 2) <= MusicalDuration(2, 4))
        self.assertFalse(MusicalDuration(3, 4) <= MusicalDuration(1, 2))

        self.assertTrue(MusicalDuration(3, 2) > MusicalDuration(3, 4))
        self.assertFalse(MusicalDuration(3, 4) > MusicalDuration(3, 2))

        self.assertTrue(MusicalDuration(3, 4) >= MusicalDuration(1, 2))
        self.assertTrue(MusicalDuration(2, 4) >= MusicalDuration(1, 2))
        self.assertFalse(MusicalDuration(1, 2) >= MusicalDuration(3, 4))


class MusicalTimeTest(unittest.TestCase):
    def test_constructor(self):
        cdef MusicalTime t
        self.assertEqual(t.numerator(), 0)
        self.assertEqual(t.denominator(), 1)

    def test_set(self):
        cdef MusicalTime t

        t.set(MusicalTime(3, 4))
        self.assertEqual(t.numerator(), 3)
        self.assertEqual(t.denominator(), 4)

        t = MusicalTime(4, 5)
        self.assertEqual(t.numerator(), 4)
        self.assertEqual(t.denominator(), 5)

        t = MusicalTime(-2)
        self.assertEqual(t.numerator(), -2)
        self.assertEqual(t.denominator(), 1)

    def test_add(self):
        cdef MusicalTime t
        for n in range(-100, 100):
            for d in range(1, 100):
                expected = fractions.Fraction(1, 1) + fractions.Fraction(n, d)

                t = MusicalTime(1, 1)
                t += MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalTime(1, 1) + MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

    def test_sub(self):
        cdef MusicalTime t
        for n in range(-100, 100):
            for d in range(1, 100):
                expected = fractions.Fraction(1, 1) - fractions.Fraction(n, d)

                t = MusicalTime(1, 1)
                t.sub(MusicalDuration(n, d))
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalTime(1, 1)
                t -= MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalTime(1, 1) - MusicalDuration(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

    def test_mul(self):
        cdef MusicalTime t
        for n in range(-100, 100):
            for d in range(1, 100):
                expected = fractions.Fraction(2, 3) * fractions.Fraction(n, d)

                t = MusicalTime(2, 3)
                t.mul(MusicalTime(n, d))
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalTime(2, 3)
                t *= MusicalTime(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalTime(2, 3) * MusicalTime(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

    def test_div(self):
        cdef MusicalTime t
        for n in range(-100, 100):
            if n == 0:
                continue
            for d in range(1, 100):
                expected = fractions.Fraction(2, 3) / fractions.Fraction(n, d)

                t = MusicalTime(2, 3)
                t.div(MusicalTime(n, d))
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalTime(2, 3)
                t /= MusicalTime(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

                t = MusicalTime(2, 3) / MusicalTime(n, d)
                self.assertEqual(fractions.Fraction(t.numerator(), t.denominator()), expected)

    def test_cmp(self):
        self.assertTrue(MusicalTime(1, 2) == MusicalTime(2, 4))
        self.assertFalse(MusicalTime(1, 2) == MusicalTime(3, 4))

        self.assertTrue(MusicalTime(1, 2) != MusicalTime(3, 4))
        self.assertFalse(MusicalTime(1, 2) != MusicalTime(2, 4))

        self.assertTrue(MusicalTime(1, 2) < MusicalTime(3, 4))
        self.assertFalse(MusicalTime(3, 4) < MusicalTime(1, 2))

        self.assertTrue(MusicalTime(1, 2) <= MusicalTime(3, 4))
        self.assertTrue(MusicalTime(1, 2) <= MusicalTime(2, 4))
        self.assertFalse(MusicalTime(3, 4) <= MusicalTime(1, 2))

        self.assertTrue(MusicalTime(3, 2) > MusicalTime(3, 4))
        self.assertFalse(MusicalTime(3, 4) > MusicalTime(3, 2))

        self.assertTrue(MusicalTime(3, 4) >= MusicalTime(1, 2))
        self.assertTrue(MusicalTime(2, 4) >= MusicalTime(1, 2))
        self.assertFalse(MusicalTime(1, 2) >= MusicalTime(3, 4))


class PyMusicalDurationTest(unittest.TestCase):
    def test_constructor(self):
        t = PyMusicalDuration(0)
        self.assertEqual(t.numerator, 0)
        self.assertEqual(t.denominator, 1)

        t = PyMusicalDuration(1, 2)
        self.assertEqual(t.numerator, 1)
        self.assertEqual(t.denominator, 2)

        t = PyMusicalDuration(2)
        self.assertEqual(t.numerator, 2)
        self.assertEqual(t.denominator, 1)

        t = PyMusicalDuration(PyMusicalDuration(1, 2))
        self.assertEqual(t.numerator, 1)
        self.assertEqual(t.denominator, 2)

        t = PyMusicalDuration(fractions.Fraction(1, 2))
        self.assertEqual(t.numerator, 1)
        self.assertEqual(t.denominator, 2)

    def test_proto(self):
        self.assertEqual(
            PyMusicalDuration.from_proto(
                musical_time_pb2.MusicalDuration(numerator=2, denominator=3)),
            PyMusicalDuration(2, 3))

        self.assertEqual(
            PyMusicalDuration(2, 3).to_proto(),
            musical_time_pb2.MusicalDuration(numerator=2, denominator=3))

    def test_cmp(self):
        self.assertTrue(PyMusicalDuration(1, 2) == PyMusicalDuration(2, 4))
        self.assertFalse(PyMusicalDuration(1, 2) == PyMusicalDuration(3, 4))
        with self.assertRaises(TypeError):
            PyMusicalDuration(1, 2) == 1

        self.assertTrue(PyMusicalDuration(1, 2) != PyMusicalDuration(3, 4))
        self.assertFalse(PyMusicalDuration(1, 2) != PyMusicalDuration(2, 4))
        with self.assertRaises(TypeError):
            PyMusicalDuration(1, 2) != 1

        self.assertTrue(PyMusicalDuration(1, 2) < PyMusicalDuration(3, 4))
        self.assertFalse(PyMusicalDuration(3, 4) < PyMusicalDuration(1, 2))
        with self.assertRaises(TypeError):
            PyMusicalDuration(1, 2) < 1

        self.assertTrue(PyMusicalDuration(1, 2) <= PyMusicalDuration(3, 4))
        self.assertTrue(PyMusicalDuration(1, 2) <= PyMusicalDuration(2, 4))
        self.assertFalse(PyMusicalDuration(3, 4) <= PyMusicalDuration(1, 2))
        with self.assertRaises(TypeError):
            PyMusicalDuration(1, 2) <= 1

        self.assertTrue(PyMusicalDuration(3, 2) > PyMusicalDuration(3, 4))
        self.assertFalse(PyMusicalDuration(3, 4) > PyMusicalDuration(3, 2))
        with self.assertRaises(TypeError):
            PyMusicalDuration(1, 2) > 1

        self.assertTrue(PyMusicalDuration(3, 4) >= PyMusicalDuration(1, 2))
        self.assertTrue(PyMusicalDuration(2, 4) >= PyMusicalDuration(1, 2))
        self.assertFalse(PyMusicalDuration(1, 2) >= PyMusicalDuration(3, 4))
        with self.assertRaises(TypeError):
            PyMusicalDuration(1, 2) >= 1

    def test_bool(self):
        self.assertTrue(PyMusicalDuration(1, 1))
        self.assertFalse(PyMusicalDuration(0, 1))

    def test_str(self):
        self.assertEqual(str(PyMusicalDuration(1, 2)), 'MusicalDuration(1, 2)')
        self.assertEqual(repr(PyMusicalDuration(1, 2)), 'MusicalDuration(1, 2)')

    def test_add(self):
        self.assertEqual(PyMusicalDuration(1, 2) + PyMusicalDuration(2, 3), PyMusicalDuration(7, 6))

        a = PyMusicalDuration(1, 2)
        a += PyMusicalDuration(2, 3)
        self.assertEqual(a, PyMusicalDuration(7, 6))

    def test_sub(self):
        self.assertEqual(PyMusicalDuration(1, 2) - PyMusicalDuration(2, 3), PyMusicalDuration(-1, 6))

        a = PyMusicalDuration(1, 2)
        a -= PyMusicalDuration(2, 3)
        self.assertEqual(a, PyMusicalDuration(-1, 6))

    def test_mul(self):
        self.assertEqual(PyMusicalDuration(1, 2) * PyMusicalDuration(2, 3), PyMusicalDuration(1, 3))
        self.assertEqual(PyMusicalDuration(1, 2) * fractions.Fraction(2, 3), PyMusicalDuration(1, 3))

        a = PyMusicalDuration(1, 2)
        a *= PyMusicalDuration(2, 3)
        self.assertEqual(a, PyMusicalDuration(1, 3))

    def test_div(self):
        self.assertEqual(PyMusicalDuration(1, 2) / PyMusicalDuration(2, 3), PyMusicalDuration(3, 4))
        self.assertEqual(PyMusicalDuration(1, 2) / fractions.Fraction(2, 3), PyMusicalDuration(3, 4))

        a = PyMusicalDuration(1, 2)
        a /= PyMusicalDuration(2, 3)
        self.assertEqual(a, PyMusicalDuration(3, 4))


class PyMusicalTimeTest(unittest.TestCase):
    def test_constructor(self):
        t = PyMusicalTime()
        self.assertEqual(t.numerator, 0)
        self.assertEqual(t.denominator, 1)

        t = PyMusicalTime(1, 2)
        self.assertEqual(t.numerator, 1)
        self.assertEqual(t.denominator, 2)

        t = PyMusicalTime(2)
        self.assertEqual(t.numerator, 2)
        self.assertEqual(t.denominator, 1)

        t = PyMusicalTime(PyMusicalTime(1, 2))
        self.assertEqual(t.numerator, 1)
        self.assertEqual(t.denominator, 2)

        t = PyMusicalTime(fractions.Fraction(1, 2))
        self.assertEqual(t.numerator, 1)
        self.assertEqual(t.denominator, 2)

    def test_proto(self):
        self.assertEqual(
            PyMusicalTime.from_proto(
                musical_time_pb2.MusicalTime(numerator=2, denominator=3)),
            PyMusicalTime(2, 3))

        self.assertEqual(
            PyMusicalTime(2, 3).to_proto(),
            musical_time_pb2.MusicalTime(numerator=2, denominator=3))

    def test_cmp(self):
        self.assertTrue(PyMusicalTime(1, 2) == PyMusicalTime(2, 4))
        self.assertFalse(PyMusicalTime(1, 2) == PyMusicalTime(3, 4))
        with self.assertRaises(TypeError):
            PyMusicalTime(1, 2) == 1

        self.assertTrue(PyMusicalTime(1, 2) != PyMusicalTime(3, 4))
        self.assertFalse(PyMusicalTime(1, 2) != PyMusicalTime(2, 4))
        with self.assertRaises(TypeError):
            PyMusicalTime(1, 2) != 1

        self.assertTrue(PyMusicalTime(1, 2) < PyMusicalTime(3, 4))
        self.assertFalse(PyMusicalTime(3, 4) < PyMusicalTime(1, 2))
        with self.assertRaises(TypeError):
            PyMusicalTime(1, 2) < 1

        self.assertTrue(PyMusicalTime(1, 2) <= PyMusicalTime(3, 4))
        self.assertTrue(PyMusicalTime(1, 2) <= PyMusicalTime(2, 4))
        self.assertFalse(PyMusicalTime(3, 4) <= PyMusicalTime(1, 2))
        with self.assertRaises(TypeError):
            PyMusicalTime(1, 2) <= 1

        self.assertTrue(PyMusicalTime(3, 2) > PyMusicalTime(3, 4))
        self.assertFalse(PyMusicalTime(3, 4) > PyMusicalTime(3, 2))
        with self.assertRaises(TypeError):
            PyMusicalTime(1, 2) > 1

        self.assertTrue(PyMusicalTime(3, 4) >= PyMusicalTime(1, 2))
        self.assertTrue(PyMusicalTime(2, 4) >= PyMusicalTime(1, 2))
        self.assertFalse(PyMusicalTime(1, 2) >= PyMusicalTime(3, 4))
        with self.assertRaises(TypeError):
            PyMusicalTime(1, 2) >= 1

    def test_bool(self):
        self.assertTrue(PyMusicalTime(1, 1))
        self.assertFalse(PyMusicalTime(0, 1))

    def test_str(self):
        self.assertEqual(str(PyMusicalTime(1, 2)), 'MusicalTime(1, 2)')
        self.assertEqual(repr(PyMusicalTime(1, 2)), 'MusicalTime(1, 2)')

    def test_add(self):
        self.assertEqual(PyMusicalTime(1, 2) + PyMusicalDuration(2, 3), PyMusicalTime(7, 6))

        a = PyMusicalTime(1, 2)
        a += PyMusicalDuration(2, 3)
        self.assertEqual(a, PyMusicalTime(7, 6))

    def test_sub(self):
        self.assertEqual(PyMusicalTime(1, 2) - PyMusicalDuration(2, 3), PyMusicalTime(-1, 6))
        self.assertEqual(PyMusicalTime(1, 2) - PyMusicalTime(2, 3), PyMusicalDuration(-1, 6))

        a = PyMusicalTime(1, 2)
        a -= PyMusicalDuration(2, 3)
        self.assertEqual(a, PyMusicalTime(-1, 6))

    def test_mul(self):
        self.assertEqual(PyMusicalTime(1, 2) * PyMusicalTime(2, 3), PyMusicalTime(1, 3))
        self.assertEqual(PyMusicalTime(1, 2) * fractions.Fraction(2, 3), PyMusicalTime(1, 3))
        self.assertEqual(PyMusicalTime(1, 2) * 3, PyMusicalTime(3, 2))
        # TODO: Can't get this to work, even if implementing __rmul__
        #self.assertEqual(3 * PyMusicalTime(1, 2), PyMusicalTime(3, 2))

        a = PyMusicalTime(1, 2)
        a *= PyMusicalTime(2, 3)
        self.assertEqual(a, PyMusicalTime(1, 3))

    def test_div(self):
        self.assertEqual(PyMusicalTime(1, 2) / PyMusicalTime(2, 3), PyMusicalTime(3, 4))
        self.assertEqual(PyMusicalTime(1, 2) / fractions.Fraction(2, 3), PyMusicalTime(3, 4))

        a = PyMusicalTime(1, 2)
        a /= PyMusicalTime(2, 3)
        self.assertEqual(a, PyMusicalTime(3, 4))
