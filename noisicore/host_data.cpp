#include "host_data.h"

#include <assert.h>

namespace noisicaa {

HostData::~HostData() {
  cleanup();
}

Status HostData::setup() {
  Status status;

  status = setup_lilv();
  if (status.is_error()) { return status; }

  status = setup_lv2();
  if (status.is_error()) { return status; }

  return Status::Ok();
}

Status HostData::setup_lilv() {
  assert(lilv_world == nullptr);

  lilv_world = lilv_world_new();
  if (lilv_world == nullptr) {
    return Status::Error("Failed to create lilv world.");
  }

  lilv_world_load_all(lilv_world);

  return Status::Ok();
}

Status HostData::setup_lv2() {
  return Status::Ok();
}

void HostData::cleanup() {
  if (lilv_world != nullptr) {
    lilv_world_free(lilv_world);
    lilv_world = nullptr;
  }
}

}  // namespace noisicaa
