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

#include "noisicaa/audioproc/public/time_mapper.h"

namespace noisicaa {

TimeMapper::TimeMapper(uint32_t sample_rate)
  : _sample_rate(sample_rate) {}

Status TimeMapper::setup() {
  return Status::Ok();
}

void TimeMapper::cleanup() {
}

MusicalTime TimeMapper::sample_to_musical_time(uint64_t sample_time) const {
  return MusicalTime(_bpm * sample_time, 4 * 60 * _sample_rate);
}

uint64_t TimeMapper::musical_to_sample_time(MusicalTime musical_time) const {
  return 4 * 60 * _sample_rate * musical_time.numerator() / (_bpm * musical_time.denominator());
}

}
