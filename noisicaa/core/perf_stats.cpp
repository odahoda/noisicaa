#include <chrono>
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

}  // namespace noisicaa
