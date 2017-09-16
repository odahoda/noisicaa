// -*- mode: c++ -*-

#ifndef _NOISICORE_BLOCK_CONTEXT_H
#define _NOISICORE_BLOCK_CONTEXT_H

#include <map>
#include <memory>
#include <string>
#include <stdint.h>
#include "noisicore/buffers.h"

namespace noisicaa {

class PerfStats;

using namespace std;

struct BlockContext {
  uint32_t block_size = 0;
  uint32_t sample_pos = 0;

  unique_ptr<PerfStats> perf;

  struct Buffer {
    size_t size;
    const BufferPtr data;
  };
  map<string, Buffer> buffers;
};

}  // namespace noisicaa

#endif
