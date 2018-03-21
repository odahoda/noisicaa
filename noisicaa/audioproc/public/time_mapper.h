// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_PUBLIC_TIME_MAPPER_H
#define _NOISICAA_AUDIOPROC_PUBLIC_TIME_MAPPER_H

#include <stdlib.h>
#include <iterator>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/public/musical_time.h"

namespace noisicaa {

class TimeMapper {
public:
  TimeMapper(uint32_t sample_rate);

  Status setup();
  void cleanup();

  void set_bpm(uint32_t bpm) { _bpm = bpm; }
  uint32_t bpm() const { return _bpm; }

  void set_duration(MusicalDuration duration) { _duration = duration; }
  MusicalDuration duration() const { return _duration; }
  MusicalTime end_time() const { return MusicalTime(0, 1) + _duration; }
  uint64_t num_samples() const { return musical_to_sample_time(end_time()); }

  MusicalTime sample_to_musical_time(uint64_t sample_time) const;
  uint64_t musical_to_sample_time(MusicalTime musical_time) const;

  class iterator: public std::iterator<
    std::input_iterator_tag,   // iterator_category
    MusicalTime,               // value_type
    long,                      // difference_type
    const MusicalTime*,        // pointer
    MusicalTime                // reference
    >{
  public:
    iterator() {}
    iterator(const iterator& i)
      : _tmap(i._tmap),
	_sample_time(i._sample_time) {}
    explicit iterator(const TimeMapper* tmap, uint64_t sample_time)
      : _tmap(tmap),
	_sample_time(sample_time) {}

    bool valid() const { return _tmap != nullptr; }
    bool is_owned_by(TimeMapper* tmap) const { return _tmap == tmap; }

    iterator& operator++() {
      ++_sample_time;
      return *this;
    }

    iterator operator++(int) {
      iterator retval = *this;
      ++(*this);
      return retval;
    }

    bool operator==(iterator other) const {
      return _tmap == other._tmap && _sample_time == other._sample_time;
    }
    bool operator!=(iterator other) const { return !(*this == other); }

    reference operator*() const {
      return _tmap->sample_to_musical_time(_sample_time);
    }

  private:
    const TimeMapper* _tmap = nullptr;
    uint64_t _sample_time = 0;
  };

  iterator begin() { return iterator(this, 0); }
  iterator find(MusicalTime t) { return iterator(this, musical_to_sample_time(t)); }

private:
  uint32_t _bpm = 120;
  uint32_t _sample_rate;
  MusicalDuration _duration = MusicalDuration(4, 1);
};

}  // namespace noisicaa

#endif
