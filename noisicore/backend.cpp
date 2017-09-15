#include "noisicore/backend.h"
#include "noisicore/backend_ipc.h"
#include "noisicore/backend_null.h"
#include "noisicore/backend_portaudio.h"
#include "noisicore/misc.h"

namespace noisicaa {

Backend::Backend(const BackendSettings& settings)
  : _settings(settings) {}

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

  return Status::Error(sprintf("Invalid backend name '%s'", name.c_str()));
}

Status Backend::setup(VM* vm) {
  _vm = vm;
  return Status::Ok();
}

void Backend::cleanup() {
}

}  // namespace noisicaa
