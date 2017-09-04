#include "backend.h"
#include "backend_ipc.h"
#include "backend_null.h"
#include "backend_portaudio.h"

namespace noisicaa {

Backend::Backend(const BackendSettings& settings)
  : _settings(settings) {}

Backend::~Backend() {
  cleanup();
}

Backend* Backend::create(const string& name, const BackendSettings& settings) {
  if (name == "portaudio") {
    return new PortAudioBackend(settings);
  } else if (name == "ipc") {
    return new IPCBackend(settings);
  } else if (name == "null") {
    return new NullBackend(settings);
  } else {
    return nullptr;
  }
}

Status Backend::setup(VM* vm) {
  _vm = vm;
  return Status::Ok();
}

void Backend::cleanup() {
}

}  // namespace noisicaa
