/*
 * @begin:license
 *
 * Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * @end:license
 */

#include "noisicaa/audioproc/vm/musical_time.h"

namespace {

int64_t gcd(int64_t a, int64_t b) {
  assert(a > 0);
  assert(b > 0);
  while ( a != 0 ) {
    int64_t c = a;
    a = b % a;
    b = c;
  }
  return b;
}

}

namespace noisicaa {

void Fraction::reduce() {
  assert(_denominator != 0);

  if (_numerator == 0) {
    _denominator = 1;
    return;
  }

  if (_denominator < 0) {
    _numerator = -_numerator;
    _denominator = -_denominator;
  }

  int64_t c = gcd(abs(_numerator), _denominator);
  _numerator /= c;
  _denominator /= c;
}

void Fraction::add(int64_t n, int64_t d) {
  assert(d > 0);
  _numerator = _numerator * d + _denominator * n;
  _denominator = _denominator * d;
  reduce();
}

void Fraction::sub(int64_t n, int64_t d) {
  assert(d > 0);
  _numerator = _numerator * d - _denominator * n;
  _denominator = _denominator * d;
  reduce();
}

void Fraction::mul(int64_t n, int64_t d) {
  assert(d != 0);
  _numerator *= n;
  _denominator *= d;
  reduce();
}

void Fraction::div(int64_t n, int64_t d) {
  assert(n != 0);
  _numerator *= d;
  _denominator *= n;
  reduce();
}

int Fraction::cmp(int64_t n, int64_t d) const {
  assert(d > 0);
  int64_t c = _numerator * d - _denominator * n;
  if (c > 0) { return 1; }
  if (c < 0) { return -1; }
  return 0;
}

}
