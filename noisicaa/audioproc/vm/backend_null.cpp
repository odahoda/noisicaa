#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/backend_null.h"
#include "noisicaa/audioproc/vm/block_context.h"
#include "noisicaa/audioproc/vm/vm.h"

namespace noisicaa {

NullBackend::NullBackend(const BackendSettings& settings)
  : Backend("noisicaa.audioproc.vm.backend.null", settings),
    _new_block_size(settings.block_size) {}
NullBackend::~NullBackend() {}

Status NullBackend::setup(VM* vm) {
  Status status = Backend::setup(vm);
  if (status.is_error()) { return status; }

  if (_settings.block_size == 0) {
   return Status::Error("Invalid block_size %d", _settings.block_size);
  }

  vm->set_block_size(_settings.block_size);
  return Status::Ok();
}

void NullBackend::cleanup() {
  Backend::cleanup();
}

Status NullBackend::set_block_size(uint32_t block_size) {
  if (block_size == 0) {
   return Status::Error("Invalid block_size %d", block_size);
  }

  _new_block_size = block_size;
  return Status::Ok();
}

Status NullBackend::begin_block(BlockContext* ctxt) {
  assert(ctxt->perf->current_span_id() == 0);
  ctxt->perf->start_span("frame");

  if (_new_block_size != _settings.block_size) {
    _settings.block_size = _new_block_size;
    _vm->set_block_size(_settings.block_size);
  }

  return Status::Ok();
}

Status NullBackend::end_block(BlockContext* ctxt) {
  ctxt->perf->end_span();
  assert(ctxt->perf->current_span_id() == 0);
  return Status::Ok();
}

Status NullBackend::output(BlockContext* ctxt, const string& channel, BufferPtr samples) {
  return Status::Ok();
}

}  // namespace noisicaa
