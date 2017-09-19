// -*- mode: c++ -*-

#ifndef _NOISICAA_CORE_PERF_STATS_H
#define _NOISICAA_CORE_PERF_STATS_H

#include <functional>
#include <memory>
#include <vector>
#include <assert.h>
#include <stdint.h>
#include <string.h>

namespace noisicaa {

using namespace std;

class PerfStats {
public:
  static const size_t NAME_LENGTH = 128;

  struct Span {
    Span() {
      this->id = 0;
      memset(this->name, 0, NAME_LENGTH);
      this->parent_id = 0;
      this->start_time_nsec = 0;
      this->end_time_nsec = 0;
    };

    Span(uint64_t id, const char* name, uint64_t parent_id, uint64_t start_time_nsec, uint64_t end_time_nsec) {
      this->id = id;
      assert(strlen(name) < NAME_LENGTH);
      strncpy(this->name, name, NAME_LENGTH);
      this->parent_id = parent_id;
      this->start_time_nsec = start_time_nsec;
      this->end_time_nsec = end_time_nsec;
    };

    uint64_t id;
    char name[NAME_LENGTH];
    uint64_t parent_id;
    uint64_t start_time_nsec;
    uint64_t end_time_nsec;
  };

  typedef function<uint64_t()> clock_func_t;

  PerfStats();
  PerfStats(clock_func_t clock);

  void reset();

  void start_span(const char* name, uint64_t parent_id);
  void start_span(const char* name);
  void end_span();
  void append_span(const Span& span);

  uint64_t current_span_id() const;
  int num_spans() const { return _spans.size(); }
  Span span(int idx) const { return _spans[idx]; }

private:
  clock_func_t _clock;
  uint64_t get_time_nsec() const;

  vector<int> _stack;
  vector<Span> _spans;
};

class PerfTracker {
public:
  PerfTracker(PerfStats* stats, const char* name)
    : _stats(stats) {
    _stats->start_span(name);
  }
  ~PerfTracker() {
    _stats->end_span();
  }

private:
  PerfStats* _stats;
};

}  // namespace noisicaa

#endif
