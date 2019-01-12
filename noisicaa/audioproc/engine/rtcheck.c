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

static _Thread_local int __enable_rt_checker = 0;
static _Thread_local int __rt_checker_violations = 0;

extern void enable_rt_checker(int enabled) {
  __enable_rt_checker = enabled;
}

extern int rt_checker_enabled() {
  return __enable_rt_checker;
}

extern int rt_checker_violations() {
  return __rt_checker_violations;
}

extern void reset_rt_checker_violations() {
  __rt_checker_violations = 0;
}

extern void rt_checker_violation_found() {
  __rt_checker_violations++;
}
