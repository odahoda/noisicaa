#include "processor_null.h"

namespace noisicaa {

ProcessorNull::ProcessorNull() {}
ProcessorNull::~ProcessorNull() {}

Status ProcessorNull::setup(const ProcessorSpec* spec) {
  return Processor::setup(spec);
}

void ProcessorNull::cleanup() {
  Processor::cleanup();
}

Status ProcessorNull::connect_port(uint32_t port_idx, BufferPtr buf) {
  return Status::Ok();
}

Status ProcessorNull::run(BlockContext* ctxt) {
  return Status::Ok();
}

}
