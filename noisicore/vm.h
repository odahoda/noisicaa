#ifndef _NOISICORE_VM_H
#define _NOISICORE_VM_H

#include "spec.h"
#include "status.h"

namespace noisicaa {

class VM {
 public:
  VM();
  ~VM();

  Status setup();
  Status cleanup();

  Status set_spec(const Spec& spec);
  Status process_frame();

 private:
  Spec _spec;
  const Spec *_current_spec;
};

}  // namespace noisicaa

#endif
