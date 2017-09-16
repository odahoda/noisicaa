// -*- mode: c++ -*-

#ifndef _NOISICAA_CORE_PERF_STATS_H
#define _NOISICAA_CORE_PERF_STATS_H

#include <memory>
#include <string>
#include <vector>
#include <stdint.h>

namespace noisicaa {

using namespace std;

class PerfStats {
public:
  struct Span {
    uint64_t id;
    string name;
    uint64_t parent_id;
    uint64_t start_time_nsec;
    uint64_t end_time_nsec;
  };

  typedef uint64_t (*clock_func_t)(void*);

  PerfStats();
  PerfStats(clock_func_t clock, void* clock_data);

  void reset();

  void start_span(const string& name, uint64_t parent_id);
  void start_span(const string& name);
  void end_span();
  void append_span(const Span& span);

  uint64_t current_span_id() const;
  int num_spans() const { return _spans.size(); }
  Span span(int idx) const { return _spans[idx]; }

private:
  clock_func_t _clock;
  void* _clock_data;
  uint64_t get_time_nsec() const;

  vector<int> _stack;
  vector<Span> _spans;
};

class PerfTracker {
public:
  PerfTracker(PerfStats* stats, const string& name)
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
