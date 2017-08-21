#include "processor.h"

#include "processor_ladspa.h"

namespace noisicaa {

Processor::Processor() {
}

Processor::~Processor() {
  cleanup();
}

Processor* Processor::create(const string& name) {
  if (name == "ladspa") {
    return new ProcessorLadspa();
  } else {
    return nullptr;
  }
}

Status Processor::setup() {
  return Status::Ok();
}

void Processor::cleanup() {
}

}  // namespace noisicaa
