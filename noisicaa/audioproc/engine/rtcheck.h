// -*- mode: c -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_RTCHECK_H
#define _NOISICAA_AUDIOPROC_ENGINE_RTCHECK_H

#ifdef __cplusplus
extern "C" {
#endif

void enable_rt_checker(int);
int rt_checker_enabled();
int rt_checker_violations();
void reset_rt_checker_violations();
void rt_checker_violation_found();

#ifdef __cplusplus
}  // extern "C"

namespace noisicaa {

class RTUnsafe {
 public:
  RTUnsafe() {
    _was_enabled = rt_checker_enabled();
    enable_rt_checker(0);
  }

  ~RTUnsafe() {
    enable_rt_checker(_was_enabled);
  }

 private:
  int _was_enabled;
};

class RTSafe {
 public:
  RTSafe() {
    _was_enabled = rt_checker_enabled();
    enable_rt_checker(1);
  }

  ~RTSafe() {
    enable_rt_checker(_was_enabled);
  }

 private:
  int _was_enabled;
};

}
#endif

#endif
