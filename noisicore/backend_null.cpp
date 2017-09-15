#include "noisicore/backend_null.h"

namespace noisicaa {

NullBackend::NullBackend(const BackendSettings& settings)
  : Backend(settings) {}
NullBackend::~NullBackend() {}

Status NullBackend::setup(VM* vm) {
  return Backend::setup(vm);
}

void NullBackend::cleanup() {
  Backend::cleanup();
}

Status NullBackend::begin_block(BlockContext* ctxt) {
  return Status::Ok();
}

Status NullBackend::end_block() {
  return Status::Ok();
}

Status NullBackend::output(const string& channel, BufferPtr samples) {
  return Status::Ok();
}

}  // namespace noisicaa
