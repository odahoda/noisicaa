// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_PUBLIC_MUSICAL_TIME_H
#define _NOISICAA_AUDIOPROC_PUBLIC_MUSICAL_TIME_H

#include <assert.h>
#include <stdlib.h>
#include <boost/rational.hpp>
#include <noisicaa/audioproc/public/musical_time.pb.h>

namespace noisicaa {

class Fraction {
public:
  Fraction() : _r(0) {}
  Fraction(int64_t n, int64_t d) : _r(n, d) {}
  Fraction(const Fraction& t) : _r(t._r) {}

  int64_t numerator() const { return _r.numerator(); }
  int64_t denominator() const { return _r.denominator(); }
  double to_double() const { return (double)_r.numerator() / _r.denominator(); }
  float to_float() const { return (float)_r.numerator() / _r.denominator(); }

protected:
  void set(int64_t n, int64_t d) {
    _r.assign(n, d);
  }
  int cmp(int64_t n, int64_t d) const;
  void add(int64_t n, int64_t d) {_r += boost::rational<int64_t>(n, d); }
  void add(const Fraction& t) { _r += t._r; }
  void sub(int64_t n, int64_t d) { _r -= boost::rational<int64_t>(n, d); }
  void sub(const Fraction& t) { _r -= t._r; }
  void mul(int64_t n, int64_t d) { _r *= boost::rational<int64_t>(n, d); }
  void mul(const Fraction& t) { _r *= t._r; }
  void div(int64_t n, int64_t d) { _r /= boost::rational<int64_t>(n, d); }
  void div(const Fraction& t) { _r /= t._r; }
  void mod(int64_t n, int64_t d);

private:
  boost::rational<int64_t> _r;
};

class MusicalDuration : public Fraction {
public:
  MusicalDuration() : Fraction(0, 1) {}
  MusicalDuration(int64_t n) : Fraction(n, 1) {}
  MusicalDuration(int64_t n, int64_t d) : Fraction(n, d) {}
  MusicalDuration(const MusicalDuration& t) : Fraction(t.numerator(), t.denominator()) {}
  MusicalDuration(const pb::MusicalDuration& pb) : Fraction(pb.numerator(), pb.denominator()) {}

  void set_proto(pb::MusicalDuration* pb) const {
    pb->set_numerator(numerator());
    pb->set_denominator(denominator());
  }

  void set(const MusicalDuration& t) { Fraction::set(t.numerator(), t.denominator()); }
  int cmp(const MusicalDuration& t) const { return Fraction::cmp(t.numerator(), t.denominator()); }
  void add(const MusicalDuration& t) { Fraction::add(t); }
  void sub(const MusicalDuration& t) { Fraction::sub(t); }
  void mul(const Fraction& t) { Fraction::mul(t); }
  void div(const Fraction& t) { Fraction::div(t); }

  MusicalDuration& operator+=(const MusicalDuration& t) { add(t); return *this; }
  MusicalDuration& operator-=(const MusicalDuration& t) { sub(t); return *this; }
  MusicalDuration& operator*=(const Fraction& t) { mul(t); return *this; }
  MusicalDuration& operator/=(const Fraction& t) { div(t); return *this; }

  friend MusicalDuration operator+(MusicalDuration a, const MusicalDuration& b) {
    a.add(b);
    return a;
  }
  friend MusicalDuration operator-(MusicalDuration a, const MusicalDuration& b) {
    a.sub(b);
    return a;
  }
  friend MusicalDuration operator*(MusicalDuration a, const Fraction& b) {
    a.mul(b);
    return a;
  }
  friend MusicalDuration operator/(MusicalDuration a, const Fraction& b) {
    a.div(b);
    return a;
  }

  friend bool operator==(const MusicalDuration& a, const MusicalDuration& b) {
    return a.cmp(b) == 0;
  }
  friend bool operator!=(const MusicalDuration& a, const MusicalDuration& b) {
    return a.cmp(b) != 0;
  }
  friend bool operator<(const MusicalDuration& a, const MusicalDuration& b) {
    return a.cmp(b) < 0;
  }
  friend bool operator>(const MusicalDuration& a, const MusicalDuration& b) {
    return a.cmp(b) > 0;
  }
  friend bool operator<=(const MusicalDuration& a, const MusicalDuration& b) {
    return a.cmp(b) <= 0;
  }
  friend bool operator>=(const MusicalDuration& a, const MusicalDuration& b) {
    return a.cmp(b) >= 0;
  }
};

class MusicalTime : public Fraction {
public:
  MusicalTime() : Fraction(0, 1) {}
  MusicalTime(int64_t n) : Fraction(n, 1) {}
  MusicalTime(int64_t n, int64_t d) : Fraction(n, d) {}
  MusicalTime(const MusicalTime& t) : Fraction(t.numerator(), t.denominator()) {}
  MusicalTime(const pb::MusicalTime& pb) : Fraction(pb.numerator(), pb.denominator()) {}

  void set_proto(pb::MusicalTime* pb) const {
    pb->set_numerator(numerator());
    pb->set_denominator(denominator());
  }

  void set(const MusicalTime& t) { Fraction::set(t.numerator(), t.denominator()); }
  int cmp(const MusicalTime& t) const { return Fraction::cmp(t.numerator(), t.denominator()); }
  void add(const MusicalDuration& t) { Fraction::add(t); }
  void sub(const MusicalDuration& t) { Fraction::sub(t); }
  void mul(const Fraction& t) { Fraction::mul(t); }
  void div(const Fraction& t) { Fraction::div(t); }
  void mod(const Fraction& t) { Fraction::mod(t.numerator(), t.denominator()); }

  MusicalTime& operator+=(const MusicalDuration& t) { add(t); return *this; }
  MusicalTime& operator-=(const MusicalDuration& t) { sub(t); return *this; }
  MusicalTime& operator*=(const Fraction& t) { mul(t); return *this; }
  MusicalTime& operator/=(const Fraction& t) { div(t); return *this; }

  friend MusicalTime operator+(MusicalTime a, const MusicalDuration& b) { a.add(b); return a; }
  friend MusicalTime operator-(MusicalTime a, const MusicalDuration& b) { a.sub(b); return a; }
  friend MusicalDuration operator-(const MusicalTime& a, const MusicalTime& b) {
    MusicalDuration d(a.numerator(), a.denominator());
    d.sub(MusicalDuration(b.numerator(), b.denominator()));
    return d;
  }
  friend MusicalTime operator*(MusicalTime a, const Fraction& b) { a.mul(b); return a; }
  friend MusicalTime operator/(MusicalTime a, const Fraction& b) { a.div(b); return a; }
  friend MusicalTime operator%(MusicalTime a, const Fraction& b) { a.mod(b); return a; }

  friend bool operator==(const MusicalTime& a, const MusicalTime& b) { return a.cmp(b) == 0; }
  friend bool operator!=(const MusicalTime& a, const MusicalTime& b) { return a.cmp(b) != 0; }
  friend bool operator<(const MusicalTime& a, const MusicalTime& b) { return a.cmp(b) < 0; }
  friend bool operator>(const MusicalTime& a, const MusicalTime& b) { return a.cmp(b) > 0; }
  friend bool operator<=(const MusicalTime& a, const MusicalTime& b) { return a.cmp(b) <= 0; }
  friend bool operator>=(const MusicalTime& a, const MusicalTime& b) { return a.cmp(b) >= 0; }
};

}  // namespace noisicaa

#endif
