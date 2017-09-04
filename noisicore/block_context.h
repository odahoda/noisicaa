// -*- mode: c++ -*-

#ifndef _NOISICORE_BLOCK_CONTEXT_H
#define _NOISICORE_BLOCK_CONTEXT_H

#include <stdint.h>

namespace noisicaa {

struct BlockContext {
  uint32_t block_size;
  uint32_t sample_pos;
};

}  // namespace noisicaa

#endif
