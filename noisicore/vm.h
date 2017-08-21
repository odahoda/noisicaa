#ifndef _NOISICORE_VM_H
#define _NOISICORE_VM_H

#include <atomic>
#include <memory>
#include <string>
#include <vector>
#include <stdint.h>

#include "spec.h"
#include "status.h"

using std::atomic;
using std::unique_ptr;
using std::string;
using std::vector;

namespace noisicaa {

class Program {
 public:
  Status setup(const Spec* spec, uint32_t block_size);

  unique_ptr<const Spec> spec;
  uint32_t block_size;
  vector<unique_ptr<Buffer>> buffers;
};

class VM {
 public:
  VM();
  ~VM();

  Status setup();
  void cleanup();

  Status set_block_size(uint32_t block_size);
  Status set_spec(const Spec* spec);
  Status process_block();

  Buffer* get_buffer(const string& name);

 private:
  atomic<uint32_t> _block_size;
  unique_ptr<Program> _program;
};

}  // namespace noisicaa

#endif
