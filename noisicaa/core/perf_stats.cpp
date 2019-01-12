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

#include "stdlib.h"
#include <chrono>
#include <memory>
#include <random>
#include "noisicaa/core/perf_stats.h"

namespace noisicaa {

PerfStats::PerfStats()
  : PerfStats(nullptr) {}

PerfStats::PerfStats(clock_func_t clock)
  : _clock(clock) {
  // preallocate enough space, so we generally won't do any
  // memory allocations when using the PerfStats instance.
  _spans.reserve(1000);
  _stack.reserve(20);
}

void PerfStats::reset() {
  _spans.clear();
  _stack.clear();
}

void PerfStats::start_span(const char* name) {
  start_span(name, current_span_id());
}

void PerfStats::start_span(const char* name, uint64_t parent_id) {
  static mt19937_64 rand(time(0));
  uint64_t id = rand();

  _stack.push_back(_spans.size());
  _spans.emplace_back(Span{id, name, parent_id, get_time_nsec(), 0});
}

void PerfStats::end_span() {
  _spans[_stack.back()].end_time_nsec = get_time_nsec();
  _stack.pop_back();
}

void PerfStats::append_span(const Span& span) {
  _spans.emplace_back(span);
}

uint64_t PerfStats::current_span_id() const {
  if (_stack.size() > 0) {
    return _spans[_stack.back()].id;
  } else {
    return 0;
  }
}

uint64_t PerfStats::get_time_nsec() const {
  if (_clock != nullptr) {
    return _clock();
  }

  auto now = chrono::high_resolution_clock::now();
  auto ns = chrono::time_point_cast<std::chrono::nanoseconds>(now);
  auto epoch = ns.time_since_epoch();
  auto value = chrono::duration_cast<std::chrono::nanoseconds>(epoch);
  return value.count();
}

size_t PerfStats::serialized_size() const {
  return sizeof(size_t) + _spans.size() * sizeof(Span);
}

void PerfStats::serialize_to(char* buf) const {
  char* p = buf;
  *((size_t*)p) = _spans.size();
  p += sizeof(size_t);
  for (const auto& span : _spans) {
    *((Span*)p) = span;
    p += sizeof(Span);
  }

  assert(p - buf == serialized_size());
}

void PerfStats::deserialize(const string& data) {
  assert(_spans.size() == 0);

  const char* p = data.c_str();
  size_t num_spans = *((size_t*)p);
  p += sizeof(size_t);
  assert(data.size() == sizeof(size_t) + num_spans * sizeof(Span));
  for (size_t i = 0 ; i < num_spans ; ++i) {
    _spans.emplace_back(*((Span*)p));
    p += sizeof(Span);
  }
}

}  // namespace noisicaa
