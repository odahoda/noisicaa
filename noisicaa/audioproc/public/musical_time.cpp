/*
 * @begin:license
 *
 * Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

#include "noisicaa/audioproc/public/musical_time.h"

namespace noisicaa {

void Fraction::mod(int64_t n, int64_t d) {
  assert(n != 0);
  int64_t t = _r.denominator();
  int64_t a = (n * _r.denominator());
  _r.assign(((_r.numerator() * d) % a + a) % a, t * d);
}

int Fraction::cmp(int64_t n, int64_t d) const {
  assert(d > 0);
  int64_t c = _r.numerator() * d - _r.denominator() * n;
  if (c > 0) { return 1; }
  if (c < 0) { return -1; }
  return 0;
}

}
