#ifndef _NOISICORE_VM_H
#define _NOISICORE_VM_H

#include <memory>
#include <string>
#include <vector>
#include <stdint.h>

#include "spec.h"
#include "status.h"

using std::unique_ptr;
using std::string;
using std::vector;

namespace noisicaa {

class Program {
 public:
  Status setup(const Spec* spec);

  unique_ptr<const Spec> spec;
  vector<unique_ptr<Buffer>> buffers;
};

class VM {
 public:
  VM();
  ~VM();

  Status setup();
  Status cleanup();

  Status set_spec(const Spec* spec);
  Status process_frame();

  Buffer* get_buffer(const string& name);

 private:
  unique_ptr<Program> _program;
};

}  // namespace noisicaa

#endif
