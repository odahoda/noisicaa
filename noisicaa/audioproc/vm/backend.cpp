#include "capnp/serialize.h"
#include "noisicaa/core/message.capnp.h"
#include "noisicaa/audioproc/vm/backend.h"
#include "noisicaa/audioproc/vm/backend_ipc.h"
#include "noisicaa/audioproc/vm/backend_null.h"
#include "noisicaa/audioproc/vm/backend_portaudio.h"

namespace noisicaa {

Backend::Backend(const char* logger_name, const BackendSettings& settings)
  : _logger(LoggerRegistry::get_logger(logger_name)),
    _settings(settings) {}

Backend::~Backend() {
  cleanup();
}

StatusOr<Backend*> Backend::create(const string& name, const BackendSettings& settings) {
  if (name == "portaudio") {
    return new PortAudioBackend(settings);
  } else if (name == "ipc") {
    return new IPCBackend(settings);
  } else if (name == "null") {
    return new NullBackend(settings);
  }

  return Status::Error("Invalid backend name '%s'", name.c_str());
}

Status Backend::setup(VM* vm) {
  _vm = vm;
  _stopped = false;
  return Status::Ok();
}

void Backend::cleanup() {
}

Status Backend::send_message(const string& msg_bytes) {
  lock_guard<mutex> lock(_msg_queue_mutex);
  _msg_queue.emplace_back(msg_bytes);
  return Status::Ok();
}

}  // namespace noisicaa
